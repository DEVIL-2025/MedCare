from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from typing import List, Dict, Any, Optional
from datetime import date, timedelta

from backend.app.database import get_db
from backend.app.models.demand import DemandHistory, SeasonalEvent, Promotion, DistributorOrder
from backend.app.models.signal import DemandSignal
from backend.app.models.product import Product
from backend.app.models.warehouse import Warehouse
from backend.app.ml.model_registry import ModelRegistry
from backend.app.utils.timezone import get_today_ist

router = APIRouter(prefix="/api/demand", tags=["Demand"])


@router.get("/signals")
async def get_demand_signals(
    sku: Optional[str] = None,
    warehouse: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Returns active multi-factor demand signals from database (Surges, Promotions, Holidays, Weather, Price Changes).
    """
    query = select(DemandSignal).where(DemandSignal.is_active == True)

    conditions = []
    if sku:
        conditions.append(or_(DemandSignal.sku == sku, DemandSignal.sku.is_(None)))
    if warehouse and warehouse != "All":
        conditions.append(or_(DemandSignal.warehouse_id == warehouse, DemandSignal.warehouse_id.is_(None)))

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(DemandSignal.start_date.asc())
    res = await db.execute(query)
    signals = res.scalars().all()

    return [
        {
            "id": sig.id,
            "sku": sig.sku or "All Network",
            "warehouse": sig.warehouse_id or "All DCs",
            "signalType": sig.signal_type,
            "title": sig.title,
            "description": sig.description,
            "impactPct": sig.impact_pct,
            "confidencePct": sig.confidence_pct,
            "startDate": sig.start_date.strftime("%Y-%m-%d"),
            "endDate": sig.end_date.strftime("%Y-%m-%d"),
            "source": sig.source,
            "badgeColor": (
                "brick" if sig.impact_pct >= 50 else
                "amber" if sig.impact_pct >= 25 else
                "forest" if sig.signal_type == "PROMOTION" else "sage"
            )
        }
        for sig in signals
    ]


@router.get("/day-of-week")
async def get_day_of_week_pattern(
    sku: Optional[str] = "P-1042",
    warehouse: Optional[str] = "BLR-01",
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Returns dynamically aggregated average demand by day of week (Mon-Sun) from DB DemandHistory."""
    q = select(DemandHistory.date, DemandHistory.actual_sales).where(DemandHistory.sku == sku)
    if warehouse and warehouse != "All":
        q = q.where(DemandHistory.warehouse_id == warehouse)

    res = await db.execute(q)
    rows = res.all()

    day_sums = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    day_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for r_date, r_sales in rows:
        dow = r_date.weekday()
        day_sums[dow] += r_sales
        day_counts[dow] += 1

    results = []
    for dow in range(7):
        avg_units = int(day_sums[dow] / max(1, day_counts[dow])) if day_counts[dow] else 0
        results.append({
            "day": day_names[dow],
            "units": max(0, avg_units)
        })

    return results


@router.get("/heatmap")
async def get_demand_heatmap(
    sku: Optional[str] = "P-1042",
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Returns 4-week projected demand heatmap across key DCs from DB."""
    wh_res = await db.execute(select(Warehouse.id))
    warehouses = [w[0] for w in wh_res.all()]

    today = get_today_ist()
    weeks = [
        f"W1 ({today.strftime('%d %b')})",
        f"W2 ({(today + timedelta(days=7)).strftime('%d %b')})",
        f"W3 ({(today + timedelta(days=14)).strftime('%d %b')})",
        f"W4 ({(today + timedelta(days=21)).strftime('%d %b')})"
    ]
    rows = []

    # Check for active demand signals for this SKU
    sig_res = await db.execute(select(DemandSignal).where(DemandSignal.sku == sku, DemandSignal.is_active == True))
    signals = sig_res.scalars().all()
    surge_wh_map = {s.warehouse_id: s.impact_pct for s in signals if s.warehouse_id}

    for wh in warehouses[:6]:
        # Fetch last 30d baseline for this SKU-DC
        dh_res = await db.execute(
            select(func.avg(DemandHistory.actual_sales))
            .where(DemandHistory.sku == sku, DemandHistory.warehouse_id == wh)
        )
        base = int(dh_res.scalar() or 200)
        surge_pct = surge_wh_map.get(wh, 0.0)
        surge_factor = 1.0 + (surge_pct / 100.0)

        week_vals = [
            int(base * 7),
            int(base * 7 * (1.0 + (surge_pct * 0.3 / 100.0))),
            int(base * 7 * surge_factor),
            int(base * 7 * (1.0 + (surge_pct * 0.7 / 100.0)))
        ]
        rows.append({
            "location": wh,
            "values": week_vals
        })

    return {
        "weeks": weeks,
        "rows": rows
    }


@router.get("/drivers")
async def get_demand_drivers(
    sku: Optional[str] = "P-1042",
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, str]]:
    """Returns relative demand driver attribution rankings from active ML model features."""
    model_info = await ModelRegistry.get_model_info(db)
    metrics = model_info.get("metrics", {})
    feat_importances = metrics.get("feature_importances", [])

    if feat_importances:
        results = []
        for f in feat_importances[:6]:
            name_clean = f["feature"].replace("_", " ").title()
            impact = "High" if f["importance_pct"] >= 15 else ("Medium" if f["importance_pct"] >= 2 else "Low")
            results.append({
                "label": f"{name_clean} ({f['importance_pct']}%)",
                "impact": impact
            })
        return results

    return [
        {"label": "Time Lag Demand Velocity", "impact": "High"},
        {"label": "Seasonality (Flu Surge)", "impact": "High"},
        {"label": "Rolling 7-Day Average", "impact": "Medium"},
        {"label": "Distributor Order Pipeline", "impact": "Medium"},
        {"label": "Calendar Day-of-Week", "impact": "Low"},
    ]


@router.get("/events")
async def get_upcoming_events(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns upcoming seasonal events and promotional campaigns from DB."""
    res = await db.execute(select(DemandSignal).where(DemandSignal.is_active == True))
    signals = res.scalars().all()
    
    prod_cnt_res = await db.execute(select(func.count(Product.sku)))
    tot_products = prod_cnt_res.scalar() or 20

    results = []
    for sig in signals:
        results.append({
            "event": sig.title,
            "type": sig.signal_type.replace("_", " ").title(),
            "start": sig.start_date.strftime("%d %b %Y"),
            "end": sig.end_date.strftime("%d %b %Y"),
            "impact": "High" if abs(sig.impact_pct) >= 40 else ("Medium" if abs(sig.impact_pct) >= 20 else "Low"),
            "skus": 1 if sig.sku else tot_products,
            "expected": f"{'↑' if sig.impact_pct >= 0 else '↓'} {int(abs(sig.impact_pct))}%"
        })

    return results
