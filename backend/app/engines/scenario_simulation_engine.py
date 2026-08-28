from datetime import timedelta, datetime, timezone
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.app.models.inventory import Inventory
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.models.batch import Batch
from backend.app.models.scenario import Scenario, ScenarioResult
from backend.app.ml.predict import PredictionService
from backend.app.config import settings
from backend.app.utils.timezone import get_today_ist


class ScenarioSimulationEngine:
    """
    Parametric What-If Scenario Simulation Engine.
    Simulates demand surges, supplier lead time delays, and capacity constraints
    dynamically computed against live PostgreSQL baseline state and ML forecasts.
    """

    HOLDING_COST_ANNUAL_RATE = 0.18

    @staticmethod
    def _format_currency(val_inr: float) -> str:
        if val_inr >= 10000000.0:
            return f"₹{val_inr / 10000000.0:.2f} Cr"
        elif val_inr >= 100000.0:
            return f"₹{val_inr / 100000.0:.2f} Lakhs"
        else:
            return f"₹{val_inr:,.0f}"

    @staticmethod
    async def run_simulation(
        session: AsyncSession,
        name: str = "What-If Scenario",
        demand_change_pct: float = 20.0,
        lead_time_change_days: int = 3,
        starting_inventory_change_pct: float = 0.0,
        capacity_constraint_pct: float = 0.0,
        distributor_demand_change_pct: float = 0.0,
        category_filter: str = "All Categories",
        warehouse_filter: str = "All Warehouses"
    ) -> Dict[str, Any]:
        """
        Executes deterministic multi-node simulation under parametric stress against live DB baseline.
        """
        today = get_today_ist()
        prods_res = await session.execute(select(Product).where(Product.is_active != False))
        products = {p.sku: p for p in prods_res.scalars().all()}

        whs_res = await session.execute(select(Warehouse).where(Warehouse.is_active != False))
        warehouses = {w.id: w for w in whs_res.scalars().all()}

        inv_res = await session.execute(select(Inventory))
        inventories = inv_res.scalars().all()

        # Query real batch near-expiry risk
        b_res = await session.execute(
            select(func.sum(Batch.quantity * Product.unit_cost))
            .join(Product, Batch.sku == Product.sku)
            .where(Batch.expiry_date <= today + timedelta(days=90), Batch.quantity > 0)
        )
        base_expiry_risk_inr = float(b_res.scalar() or 0.0)

        # Authoritative ML baseline forecasts
        all_forecasts = await PredictionService.predict_all_demands(session, settings.FORECAST_HORIZON_DAYS)

        # Compute dynamic live baseline from DB & ML Forecasts
        base_stockout_count = 0
        base_stockout_val = 0.0
        base_replenish_val = 0.0
        base_total_inv_val = 0.0
        base_fillable_demand = 0.0
        base_expected_demand = 0.0

        filtered_inventories = []

        for inv in inventories:
            prod = products.get(inv.sku)
            if not prod:
                continue
            if category_filter != "All Categories" and getattr(prod, "category", "") != category_filter:
                continue
            if warehouse_filter != "All Warehouses" and inv.warehouse_id != warehouse_filter:
                continue

            filtered_inventories.append(inv)
            prod_cost = float(getattr(prod, "unit_cost", 0.0) or 50.0)
            inv_curr = int(getattr(inv, "current_stock", 0) or 0)
            inv_inbound = int(getattr(inv, "inbound_stock", 0) or 0)
            inv_safety = int(getattr(inv, "safety_stock", 0) or 0)

            inv_val = inv_curr * prod_cost
            base_total_inv_val += inv_val

            wh = warehouses.get(inv.warehouse_id)
            base_lead_time = wh.lead_time_days if (wh and wh.lead_time_days) else 5

            f_data = all_forecasts.get(f"{inv.sku}_{inv.warehouse_id}")
            if f_data and "sensed_daily" in f_data:
                base_daily_demand = float(f_data["sensed_daily"])
                base_30d_demand = float(f_data.get("forecast_demand_next_30d", base_daily_demand * 30.0))
            else:
                default_rop = getattr(prod, "default_reorder_point", 200) or 200
                base_daily_demand = float(default_rop / 30.0) if default_rop > 0 else 10.0
                base_30d_demand = base_daily_demand * 30.0

            base_expected_demand += base_30d_demand

            base_deficit = (inv_curr + inv_inbound) - base_30d_demand
            if base_deficit < 0:
                base_stockout_count += 1
                base_stockout_val += abs(base_deficit) * prod_cost
                base_fillable_demand += max(0.0, float(inv_curr + inv_inbound))
            else:
                base_fillable_demand += base_30d_demand

            # Base replenishment
            base_lead_time_demand = base_daily_demand * (base_lead_time + settings.LEAD_TIME_BUFFER_DAYS)
            base_target = base_lead_time_demand + inv_safety
            base_rep_qty = max(0.0, base_target - (inv_curr + inv_inbound))
            base_replenish_val += base_rep_qty * prod_cost

        base_service_level = round((base_fillable_demand / max(1.0, base_expected_demand)) * 100.0, 1)
        base_service_level = min(100.0, max(0.0, base_service_level))
        base_holding_val = base_total_inv_val * ScenarioSimulationEngine.HOLDING_COST_ANNUAL_RATE

        # -------------------------------------------------------------
        # Execute Simulated Parametric Stress Run
        # -------------------------------------------------------------
        demand_mult = max(0.0, 1.0 + (demand_change_pct + distributor_demand_change_pct) / 100.0)
        inv_start_mult = max(0.0, 1.0 + (starting_inventory_change_pct / 100.0))
        effective_capacity_mult = max(0.05, 1.0 - (capacity_constraint_pct / 100.0))

        sim_stockout_count = 0
        sim_stockout_val = 0.0
        sim_replenish_val = 0.0
        sim_fillable_demand = 0.0
        sim_expected_demand = 0.0
        affected_skus = []

        for inv in filtered_inventories:
            prod = products.get(inv.sku)
            if not prod:
                continue

            prod_cost = float(getattr(prod, "unit_cost", 0.0) or 50.0)
            inv_curr = int(getattr(inv, "current_stock", 0) or 0)
            inv_inbound = int(getattr(inv, "inbound_stock", 0) or 0)
            inv_safety = int(getattr(inv, "safety_stock", 0) or 0)

            wh = warehouses.get(inv.warehouse_id)
            base_lead_time = wh.lead_time_days if (wh and wh.lead_time_days) else 5

            f_data = all_forecasts.get(f"{inv.sku}_{inv.warehouse_id}")
            if f_data and "sensed_daily" in f_data:
                base_daily_demand = float(f_data["sensed_daily"])
            else:
                default_rop = getattr(prod, "default_reorder_point", 200) or 200
                base_daily_demand = float(default_rop / 30.0) if default_rop > 0 else 10.0

            sim_current_stock = inv_curr * inv_start_mult
            sim_daily_demand = base_daily_demand * demand_mult

            # Effective lead time
            sim_lead_time = max(1, base_lead_time + lead_time_change_days)
            lead_time_demand = sim_daily_demand * (sim_lead_time + settings.LEAD_TIME_BUFFER_DAYS)

            total_30d_demand = sim_daily_demand * 30.0
            sim_expected_demand += total_30d_demand

            # Stock balance over 30 days constrained by fulfillment throughput capacity
            effective_available = (sim_current_stock + inv_inbound) * effective_capacity_mult
            deficit = effective_available - total_30d_demand
            if deficit < 0:
                stockout_units = int(abs(deficit))
                sim_stockout_count += 1
                stockout_val = stockout_units * prod_cost
                sim_stockout_val += stockout_val
                fillable = max(0.0, effective_available)
                sim_fillable_demand += fillable

                curr_stockout_est = max(0, int(base_daily_demand * 30.0 - (inv_curr + inv_inbound)))
                affected_skus.append({
                    "sku": prod.sku,
                    "name": prod.name,
                    "warehouse": inv.warehouse_id,
                    "scenarioStockout": stockout_units,
                    "currentStockout": curr_stockout_est,
                    "risk": "critical" if stockout_units > 1000 else "warning"
                })
            else:
                sim_fillable_demand += total_30d_demand

            # Replenishment requirement
            target_stock = lead_time_demand + (inv_safety * demand_mult)
            sim_replenish_qty = max(0.0, target_stock - (sim_current_stock + inv_inbound))
            sim_replenish_val += sim_replenish_qty * prod_cost

        # Overall Simulated Service Level (unconstrained by artificial floors)
        sim_service_level = round((sim_fillable_demand / max(1.0, sim_expected_demand)) * 100.0, 1)
        sim_service_level = min(100.0, max(0.0, sim_service_level))

        sim_holding_val = (base_total_inv_val * inv_start_mult) * ScenarioSimulationEngine.HOLDING_COST_ANNUAL_RATE * (1.0 + demand_change_pct * 0.005)
        sim_expiry_val = base_expiry_risk_inr * max(0.2, 1.0 + (lead_time_change_days * 0.1) - (demand_change_pct * 0.005))

        # Generate 16-Week Projected Impact Trajectory
        impact_trend = []
        net_stock = sum(int(getattr(i, "current_stock", 0) or 0) for i in filtered_inventories) * inv_start_mult
        weekly_sim_demand = sim_expected_demand / 4.0
        weekly_sim_replenish = sim_replenish_val / 4.0
        curr_proj_stock = net_stock

        for w in range(1, 17):
            t_date = today + timedelta(weeks=w)
            w_label = f"Wk +{w} ({t_date.strftime('%d %b')})"

            sim_weekly_stockout_val = (sim_stockout_val / 4.0) * min(2.5, 0.7 + (w * 0.05))
            base_weekly_stockout_val = (base_stockout_val / 4.0)

            sim_weekly_rep_val = (sim_replenish_val / 4.0) * min(2.5, 0.7 + (w * 0.05))
            base_weekly_rep_val = (base_replenish_val / 4.0)

            # Roll forward projected stock
            curr_proj_stock = max(0.0, curr_proj_stock - (weekly_sim_demand * 0.25) + (weekly_sim_replenish * 0.25))

            impact_trend.append({
                "date": w_label,
                "scenarioStockout": round(sim_weekly_stockout_val / 100000.0, 2),
                "currentStockout": round(base_weekly_stockout_val / 100000.0, 2),
                "scenarioReplenish": round(sim_weekly_rep_val / 100000.0, 2),
                "currentReplenish": round(base_weekly_rep_val / 100000.0, 2),
                "projected_stock": int(curr_proj_stock),
                "unit": "₹ Lakhs"
            })

        # Structured Side-by-Side Comparison Table
        stockout_diff = sim_stockout_val - base_stockout_val
        replenish_diff = sim_replenish_val - base_replenish_val
        sl_diff = round(sim_service_level - base_service_level, 1)

        fmt = ScenarioSimulationEngine._format_currency

        comparison = [
            {
                "metric": "Projected Stockout SKUs",
                "tooltip": "Number of SKU-DC node pairs that will deplete stock before customer orders are fully fulfilled.",
                "baseline": f"{base_stockout_count} SKUs",
                "simulated": f"{sim_stockout_count} SKUs",
                "delta": f"{'+' if sim_stockout_count >= base_stockout_count else ''}{sim_stockout_count - base_stockout_count} SKUs",
                "isAdverse": sim_stockout_count > base_stockout_count
            },
            {
                "metric": "Stockout Financial Loss",
                "tooltip": "Estimated unfulfilled prescription revenue and contractual SLA penalty risk.",
                "baseline": fmt(base_stockout_val),
                "simulated": fmt(sim_stockout_val),
                "delta": f"{'+' if stockout_diff >= 0 else '-'}{fmt(abs(stockout_diff))}",
                "isAdverse": stockout_diff > 0
            },
            {
                "metric": "Network Customer Service Level (OTIF %)",
                "tooltip": "Percentage of prescription demand fulfilled on-time and in-full across hospitals and pharmacies.",
                "baseline": f"{base_service_level}%",
                "simulated": f"{sim_service_level}%",
                "delta": f"{'+' if sl_diff >= 0 else ''}{sl_diff}%",
                "isAdverse": sl_diff < 0
            },
            {
                "metric": "Replenishment Capital Needed",
                "tooltip": "Capital expenditure required to replenish network stock to target safety buffers.",
                "baseline": fmt(base_replenish_val),
                "simulated": fmt(sim_replenish_val),
                "delta": f"{'+' if replenish_diff >= 0 else '-'}{fmt(abs(replenish_diff))}",
                "isAdverse": replenish_diff > 0
            },
            {
                "metric": "Annual Inventory Holding Cost",
                "tooltip": "Carrying cost of capital, cold-chain electricity, warehousing, and insurance.",
                "baseline": fmt(base_holding_val),
                "simulated": fmt(sim_holding_val),
                "delta": f"{'+' if sim_holding_val >= base_holding_val else '-'}{fmt(abs(sim_holding_val - base_holding_val))}",
                "isAdverse": sim_holding_val > base_holding_val
            },
            {
                "metric": "Batch Expiry / Scrap Exposure",
                "tooltip": "Estimated inventory value subject to shelf-life risk under modified lead times.",
                "baseline": fmt(base_expiry_risk_inr),
                "simulated": fmt(sim_expiry_val),
                "delta": f"{'+' if sim_expiry_val >= base_expiry_risk_inr else '-'}{fmt(abs(sim_expiry_val - base_expiry_risk_inr))}",
                "isAdverse": sim_expiry_val > base_expiry_risk_inr
            }
        ]

        impact_summary = {
            "projected_stockout_skus": sim_stockout_count,
            "stockout_value": fmt(sim_stockout_val),
            "stockout_delta": f"{'+' if stockout_diff >= 0 else '-'}{fmt(abs(stockout_diff))}",
            "service_level": f"{sim_service_level}%",
            "service_level_delta": f"{'+' if sl_diff >= 0 else ''}{sl_diff}%",
            "replenishment_need": fmt(sim_replenish_val),
            "replenishment_delta": f"{'+' if replenish_diff >= 0 else '-'}{fmt(abs(replenish_diff))}"
        }

        # Persist Scenario in Database
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        scenario = Scenario(
            name=name,
            description=f"Demand: {demand_change_pct:+}%, Lead Time: {lead_time_change_days:+}d, Scope: {warehouse_filter}",
            demand_change_pct=demand_change_pct,
            lead_time_change_days=lead_time_change_days,
            starting_inventory_change_pct=starting_inventory_change_pct,
            capacity_constraint_pct=capacity_constraint_pct,
            created_at=now_utc
        )
        session.add(scenario)
        await session.flush()

        result = ScenarioResult(
            scenario_id=scenario.id,
            projected_stockout_skus=sim_stockout_count,
            stockout_value_inr=sim_stockout_val,
            stockout_value_formatted=fmt(sim_stockout_val),
            avg_service_level_pct=sim_service_level,
            total_replenishment_need_inr=sim_replenish_val,
            total_replenishment_formatted=fmt(sim_replenish_val),
            calculated_at=now_utc
        )
        session.add(result)
        await session.flush()

        affected_skus.sort(key=lambda x: x["scenarioStockout"], reverse=True)

        results_alias = {
            "projected_service_level": sim_service_level,
            "weekly_trajectory": impact_trend,
            "current_inventory_units": sum(int(getattr(i, "current_stock", 0) or 0) for i in filtered_inventories),
            "stockout_skus": sim_stockout_count,
            "stockout_value": sim_stockout_val,
            "replenishment_need": sim_replenish_val
        }

        return {
            "scenario_id": scenario.id,
            "name": name,
            "status": "Completed",
            "service_level": f"{sim_service_level}%",
            "impact_summary": impact_summary,
            "comparison": comparison,
            "impact_trend": impact_trend,
            "affected_skus": affected_skus[:8],
            "results": results_alias
        }
