import { useState, useEffect, useCallback } from 'react';
import {
  DollarSign, Package, AlertTriangle, Truck, ShieldAlert, Activity,
  ArrowRightLeft, Check, Sparkles, Layers, CheckCircle2, AlertCircle, Building
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer } from 'recharts';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import { riskTone, riskLabel } from '../data/riskTone';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';

const healthTone = (status) => (status === 'Healthy' ? 'good' : status === 'At Risk' ? 'critical' : 'warning');

export default function Dashboard() {
  const { selectedWarehouse, refreshKey, triggerRefresh } = useControlTower();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [transferExecuting, setTransferExecuting] = useState(false);
  const [transferSuccess, setTransferSuccess] = useState(false);
  const [actionError, setActionError] = useState(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDashboard({ warehouse: selectedWarehouse });
      if (res && res.kpis) {
        setData(res);
      } else {
        throw new Error('Invalid dashboard payload received from server');
      }
    } catch (err) {
      console.error('Failed to load live dashboard:', err);
      setError(err.message || 'Unable to connect to Control Tower backend server.');
    } finally {
      setLoading(false);
    }
  }, [selectedWarehouse]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard, refreshKey]);

  async function handleExecuteAction(rec) {
    if (!rec) return;
    setTransferExecuting(true);
    setActionError(null);
    try {
      if (rec.action_type === 'replenishment' || rec.recommendation_id) {
        await api.approveRecommendation(rec.recommendation_id || rec.id);
      } else {
        await api.executeTransfer(rec.transfer_id || rec.id);
      }
      setTransferSuccess(true);
      triggerRefresh();
      await loadDashboard();
      setTimeout(() => {
        setTransferSuccess(false);
      }, 3000);
    } catch (err) {
      setActionError(`Action execution failed: ${err.message}`);
      // Refresh dashboard state immediately so stale/invalid card is dynamically replaced
      triggerRefresh();
      await loadDashboard();
    } finally {
      setTransferExecuting(false);
    }
  }

  if (loading && !data) {
    return <LoadingState message={`Loading live MedCare SCM Control Tower metrics (${selectedWarehouse === 'All' ? 'All Warehouses' : selectedWarehouse})...`} />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={loadDashboard} />;
  }

  if (!data) {
    return <EmptyState title="No Dashboard Data" description="Unable to load supply chain metrics from database." />;
  }

  const kpis = data.kpis || {};
  const demand_trend = data.demand_trend || [];
  const executive_recommendation = data.executive_recommendation;
  const top_at_risk_skus = data.top_at_risk_skus || [];
  const warehouse_health = data.warehouse_health || [];
  const alert_summary = data.alert_summary || {};

  return (
    <div className="space-y-5">
      {/* Top Level Metric KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={DollarSign}
          tone="forest"
          label="Total Inventory Value"
          value={kpis.total_inventory_value || '₹0'}
          delta={`Physical Stock: ${kpis.total_inventory_units || 0} units`}
          deltaPositive={true}
        />
        <StatCard
          icon={AlertTriangle}
          tone="brick"
          label="Critical Out-of-Stock SKUs"
          value={kpis.critical_skus || 0}
          delta={kpis.critical_skus > 0 ? "Immediate rebalance needed" : "Zero stockouts in scope"}
          deltaPositive={kpis.critical_skus === 0}
        />
        <StatCard
          icon={Truck}
          tone="gold"
          label="Replenishment Orders Needed"
          value={kpis.replenishment_needed || '0 SKUs'}
          delta="Dynamic lead-time threshold"
          deltaPositive={false}
        />
        {/* <StatCard
          icon={ShieldAlert}
          tone="sage"
          label="Network Inventory Health"
          value={kpis.inventory_health || '100%'}
          delta={selectedWarehouse === 'All' ? '3 Active DC Nodes' : `${selectedWarehouse} DC Node`}
          deltaPositive={true}
        /> */}
      </div>

      {/* Main Grid: Demand Outlook Chart & Recommended Action */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left 2 Cols: Demand vs Inventory Outlook */}
        <div className="lg:col-span-2 bg-white rounded-lg border border-ink-100 shadow-card p-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
            <div>
              <h3 className="text-[15px] font-semibold text-ink-900">Demand vs Inventory Outlook (Units)</h3>
              <p className="text-[11.5px] text-ink-500">Comparing past 4-week sales velocity, 4-week forward ML projection, and available inventory.</p>
            </div>
            <span className="text-[11px] text-forest-700 font-mono font-medium">
              Scope: {selectedWarehouse === 'All' ? 'All Warehouses' : selectedWarehouse}
            </span>
          </div>

          <div className="h-72">
            {demand_trend && demand_trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={demand_trend} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E5E1" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#68716D' }} axisLine={{ stroke: '#E2E5E1' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#68716D' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 6, border: '1px solid #E2E5E1', fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12, color: '#68716D' }} />
                  <Line type="monotone" dataKey="actual" stroke="#177A5B" strokeWidth={2.5} dot={{ r: 3 }} name="Actual Weekly Sales" connectNulls={false} />
                  <Line type="monotone" dataKey="forecast" stroke="#D5A72C" strokeWidth={2.5} strokeDasharray="4 4" dot={{ r: 3 }} name="ML Projected Demand" connectNulls={false} />
                  <Line type="monotone" dataKey="inventory" stroke="#3B82F6" strokeWidth={2} dot={false} name="Projected Available Stock" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="No Demand Series" description="Historical demand data is not yet recorded in the database." />
            )}
          </div>
        </div>

        {/* Executive Decision Card */}
        <div className="bg-white rounded-lg border-2 border-forest-600/30 shadow-card p-4 flex flex-col justify-between">
          {executive_recommendation ? (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold tracking-wider text-forest-700 uppercase flex items-center gap-1.5">
                  <Sparkles size={13} className="text-forest-600" />
                  Recommended Action
                </span>
                {executive_recommendation.savings && (
                  <span className="text-[10.5px] px-2 py-0.5 rounded bg-forest-100 text-forest-800 font-medium">
                    Est. Impact: {executive_recommendation.savings}
                  </span>
                )}
              </div>

              <h4 className="text-[14.5px] font-bold text-ink-900 mb-1 leading-snug">
                {executive_recommendation.what}
              </h4>
              <div className="text-[12px] text-ink-500 mb-3 font-mono">
                {executive_recommendation.product}
              </div>

              {executive_recommendation.from && (
                <div className="flex items-center justify-between gap-2 p-2.5 rounded-md bg-cream-200/80 border border-ink-100 text-[12px] mb-3">
                  <div>
                    <span className="text-[10px] text-ink-500 uppercase block font-semibold">
                      {executive_recommendation.action_type === 'replenishment' ? 'Preferred Supplier' : 'Source DC'}
                    </span>
                    <span className="font-semibold text-ink-900">{executive_recommendation.from}</span>
                  </div>
                  <ArrowRightLeft size={16} className="text-forest-700 shrink-0" />
                  <div className="text-right">
                    <span className="text-[10px] text-ink-500 uppercase block font-semibold">
                      {executive_recommendation.action_type === 'replenishment' ? 'Receiving DC' : 'Destination DC'}
                    </span>
                    <span className="font-semibold text-ink-900">{executive_recommendation.to}</span>
                  </div>
                </div>
              )}

              <div className="text-[11.5px] text-ink-700 mb-2 leading-relaxed bg-cream-100 p-2.5 rounded border border-ink-100/60">
                <strong>Clinical Rationale:</strong> {executive_recommendation.why}
              </div>
              <div className="text-[11px] text-ink-500">
                <strong>Impact:</strong> {executive_recommendation.expected_impact}
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center p-4 space-y-2">
              <div className="w-10 h-10 rounded-full bg-forest-100 flex items-center justify-center text-forest-700">
                <CheckCircle2 size={22} />
              </div>
              <h4 className="text-[14px] font-bold text-ink-900">All Recommended Actions Completed</h4>
              <p className="text-[11.5px] text-ink-500">
                All inter-DC transfers and supplier purchase orders for this scope have been approved and synchronized in Database.
              </p>
            </div>
          )}

          {/* Action Button & Error Alert */}
          {executive_recommendation && (
            <div className="mt-4 pt-3 border-t border-ink-100 space-y-2">
              {actionError && (
                <div className="flex items-center gap-1.5 p-2 bg-brick-100 border border-brick-600/30 rounded text-brick-700 text-[11.5px] font-medium">
                  <AlertCircle size={14} className="shrink-0" />
                  <span>{actionError}</span>
                </div>
              )}

              {transferSuccess ? (
                <div className="w-full flex items-center justify-center gap-1.5 py-2 rounded-md bg-forest-100 text-forest-800 text-[12px] font-semibold animate-fadeIn">
                  <Check size={16} /> Action Executed & Stock Synchronized in DB
                </div>
              ) : (
                <button
                  onClick={() => handleExecuteAction(executive_recommendation)}
                  disabled={transferExecuting}
                  className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-md bg-forest-700 hover:bg-forest-600 text-white text-[12px] font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50"
                >
                  <ArrowRightLeft size={14} className={transferExecuting ? 'animate-spin' : ''} />
                  {transferExecuting
                    ? 'Executing Action...'
                    : executive_recommendation.action_type === 'replenishment'
                    ? 'Approve Replenishment PO (1-Click)'
                    : 'Approve Inter-DC Transfer (1-Click)'}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Grid: Critical SKUs & Warehouse Health */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* At-Risk SKUs Table */}
        <div className="xl:col-span-2 bg-white rounded-lg border border-ink-100 shadow-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-[15px] font-semibold text-ink-900">Critical SKUs Requiring Attention</h3>
              <p className="text-[11.5px] text-ink-500">Live risk scoring evaluating days of cover, velocity, and expiry date.</p>
            </div>
            <a href="/inventory" className="text-[11.5px] text-forest-700 font-semibold hover:underline">
              View Full Inventory →
            </a>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                <tr>
                  <th className="py-2.5 px-3">SKU & Product</th>
                  <th className="py-2.5 px-3">Warehouse</th>
                  <th className="py-2.5 px-3">Current Stock</th>
                  <th className="py-2.5 px-3">Days of Cover</th>
                  <th className="py-2.5 px-3">Reorder Point</th>
                  <th className="py-2.5 px-3">Risk Level</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {top_at_risk_skus && top_at_risk_skus.length > 0 ? (
                  top_at_risk_skus.map((item, idx) => (
                    <tr key={idx} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-ink-900">{item.name}</div>
                        <div className="text-[10.5px] text-ink-400 font-mono">{item.sku}</div>
                      </td>
                      <td className="py-2.5 px-3 font-mono font-medium text-ink-700">{item.warehouse}</td>
                      <td className="py-2.5 px-3 font-medium text-ink-800">{Number(item.currentStock || 0).toLocaleString()}</td>
                      <td className="py-2.5 px-3">
                        <span className={`font-semibold ${Number(item.daysOfCover) <= 5 ? 'text-brick-600' : 'text-amber-600'}`}>
                          {item.daysOfCover} Days
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-ink-600">{Number(item.reorderPoint || 0).toLocaleString()}</td>
                      <td className="py-2.5 px-3">
                        <Badge tone={riskTone[item.risk] || 'critical'}>
                          {riskLabel[item.risk] || item.status}
                        </Badge>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-ink-400">
                      No critical stockout risks detected across warehouses.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Warehouse Network Status */}
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[15px] font-semibold text-ink-900">Regional DC Status</h3>
          </div>

          <div className="space-y-2.5">
            {warehouse_health.map((wh) => (
              <div
                key={wh.id}
                className="flex items-center justify-between p-2.5 rounded-md border border-ink-100 hover:bg-cream-100/60 transition-colors"
              >
                <div>
                  <div className="font-semibold text-[13px] text-ink-900">{wh.name}</div>
                  <div className="text-[11px] text-ink-500">
                    <span className="font-mono">{wh.id}</span> • {wh.inventory}
                  </div>
                </div>
                <Badge tone={healthTone(wh.status)}>{wh.status}</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}