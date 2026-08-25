import { useState, useEffect, useCallback } from 'react';
import { Search, AlertTriangle, ShieldAlert, CheckCircle2, ArrowUpRight, Clock, UserCheck, ArrowUpCircle } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import Badge from '../components/ui/Badge';
import Tabs from '../components/ui/Tabs';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';
import { formatDateTime } from '../utils/dateUtils';

const catTone = { critical: 'critical', warning: 'warning', medium: 'medium', info: 'info', good: 'good' };
const catLabel = { critical: 'Critical', warning: 'High', medium: 'Medium', info: 'Info', good: 'Resolved' };
const statusTone = { New: 'critical', Acknowledged: 'medium', 'In Progress': 'warning', Resolved: 'good' };

export default function Alerts() {
  const { selectedWarehouse, refreshKey, triggerRefresh } = useControlTower();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('All Alerts');
  const [search, setSearch] = useState('');
  const [actionProcessing, setActionProcessing] = useState(false);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [actionError, setActionError] = useState(null);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getAlerts({
        category: tab,
        search,
        warehouse: selectedWarehouse !== 'All' ? selectedWarehouse : undefined
      });
      if (res) {
        setData(res);
      } else {
        throw new Error('Failed to load alerts');
      }
    } catch (err) {
      console.error('Alerts load error:', err);
      setError(err.message || 'Unable to connect to Alert engine.');
    } finally {
      setLoading(false);
    }
  }, [tab, search, selectedWarehouse]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts, refreshKey]);

  async function handleAction(alertId, action, notes = '') {
    setActionProcessing(true);
    setActionError(null);
    try {
      await api.handleAlertAction(alertId, action, notes);
      setActionSuccess(`Alert ${alertId} updated (${action}) successfully in PostgreSQL.`);
      triggerRefresh();
      await loadAlerts();
      setTimeout(() => {
        setActionSuccess(null);
      }, 3000);
    } catch (err) {
      setActionError(`Action failed: ${err.message}`);
    } finally {
      setActionProcessing(false);
    }
  }

  if (loading && !data) {
    return <LoadingState message="Connecting to MedCare Real-Time Alert & Escalation Engine..." />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={loadAlerts} />;
  }

  const counts = data?.counts || { total: 0, critical: 0, warning: 0, medium: 0, good: 0 };
  const alerts = data?.alerts || [];
  const alerts_by_type = data?.alerts_by_type || [];
  const top_critical_alerts = data?.top_critical_alerts || [];
  const recent_activity = data?.recent_activity || [];

  return (
    <div className="space-y-5">
      {actionError && (
        <div className="p-3 rounded-md bg-brick-100 text-brick-700 text-[12.5px] font-medium flex items-center gap-2 border border-brick-600/30 animate-fadeIn">
          <AlertTriangle size={16} className="shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {actionSuccess && (
        <div className="p-3 rounded-md bg-forest-100 text-forest-800 text-[13px] font-semibold flex items-center gap-2 border border-forest-600/30 animate-fadeIn">
          <CheckCircle2 size={16} className="shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}
      {/* Alert Severity Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg border border-ink-100 shadow-card flex items-center justify-between">
          <div>
            <span className="text-[12px] text-ink-500 font-medium">Critical Alerts (SLA 4h)</span>
            <div className="text-[22px] font-bold text-brick-600 mt-0.5">{counts.critical || 0}</div>
          </div>
          <div className="w-10 h-10 rounded-full bg-brick-100 flex items-center justify-center text-brick-600">
            <ShieldAlert size={20} />
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-ink-100 shadow-card flex items-center justify-between">
          <div>
            <span className="text-[12px] text-ink-500 font-medium">High Severity (SLA 24h)</span>
            <div className="text-[22px] font-bold text-amber-600 mt-0.5">{counts.warning || 0}</div>
          </div>
          <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-amber-600">
            <AlertTriangle size={20} />
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-ink-100 shadow-card flex items-center justify-between">
          <div>
            <span className="text-[12px] text-ink-500 font-medium">Medium / Watch</span>
            <div className="text-[22px] font-bold text-gold-700 mt-0.5">{counts.medium || 0}</div>
          </div>
          <div className="w-10 h-10 rounded-full bg-gold-100 flex items-center justify-center text-gold-700">
            <Clock size={20} />
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-ink-100 shadow-card flex items-center justify-between">
          <div>
            <span className="text-[12px] text-ink-500 font-medium">Resolved in DB</span>
            <div className="text-[22px] font-bold text-forest-700 mt-0.5">{counts.good || 0}</div>
          </div>
          <div className="w-10 h-10 rounded-full bg-forest-100 flex items-center justify-center text-forest-700">
            <CheckCircle2 size={20} />
          </div>
        </div>
      </div>

      {/* Main Grid: Alert Table & Breakdown Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left Column: Filter & Alert Table */}
        <div className="xl:col-span-2 space-y-4">
          <div className="bg-white p-3.5 rounded-lg border border-ink-100 shadow-card space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <Tabs
                tabs={['All Alerts', 'Critical', 'Warning', 'Medium', 'Resolved']}
                active={tab}
                onChange={setTab}
              />
              <div className="relative max-w-xs w-full">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
                <input
                  type="text"
                  placeholder="Search alert by SKU or reason..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-[12px] rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
                />
              </div>
            </div>
          </div>

          {alerts.length === 0 ? (
            <EmptyState title="No Active Alerts" description="No alerts found for the selected filter category." />
          ) : (
            <div className="bg-white rounded-lg border border-ink-100 shadow-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[12px]">
                  <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                    <tr>
                      <th className="py-2.5 px-3">Severity</th>
                      <th className="py-2.5 px-3">Alert Type</th>
                      <th className="py-2.5 px-3">Product / SKU</th>
                      <th className="py-2.5 px-3">Warehouse</th>
                      <th className="py-2.5 px-3">Condition & Detail</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3 text-right">Escalation Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100">
                    {alerts.map((a) => (
                      <tr key={a.id} className="hover:bg-cream-100/60 transition-colors">
                        <td className="py-2.5 px-3">
                          <Badge tone={catTone[a.category] || 'warning'}>{catLabel[a.category] || a.category}</Badge>
                        </td>
                        <td className="py-2.5 px-3 font-semibold text-ink-900">{a.type}</td>
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-ink-900">{a.product}</div>
                          <div className="text-[10.5px] text-ink-400 font-mono">{a.sku}</div>
                        </td>
                        <td className="py-2.5 px-3 font-mono font-medium text-ink-700">{a.warehouse}</td>
                        <td className="py-2.5 px-3 text-[11.5px] text-ink-600 max-w-xs">
                          <div>{a.detail}</div>
                          <div className="text-[10px] text-ink-400 font-mono mt-0.5 flex items-center gap-1">
                            <Clock size={11} className="text-ink-400" />
                            {formatDateTime(a.createdAtRaw || a.createdAt)}
                          </div>
                        </td>
                        <td className="py-2.5 px-3">
                          <Badge tone={statusTone[a.status] || 'neutral'}>{a.status}</Badge>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          {a.status === 'New' ? (
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => handleAction(a.id, 'acknowledge')}
                                disabled={actionProcessing}
                                className="px-2.5 py-1 text-[11px] bg-forest-700 hover:bg-forest-600 text-white rounded font-medium shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                              >
                                Acknowledge
                              </button>
                            </div>
                          ) : a.status === 'In Progress' || a.status === 'Acknowledged' ? (
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => handleAction(a.id, 'escalate')}
                                disabled={actionProcessing}
                                className="px-2 py-1 text-[10.5px] bg-cream-200 hover:bg-cream-300 text-ink-800 rounded font-medium cursor-pointer"
                                title="Escalate SLA Tier"
                              >
                                Escalate
                              </button>
                              <button
                                onClick={() => handleAction(a.id, 'resolve')}
                                disabled={actionProcessing}
                                className="px-2.5 py-1 text-[11px] bg-forest-100 hover:bg-forest-200 text-forest-800 border border-forest-600/30 rounded font-medium transition-colors cursor-pointer"
                              >
                                Mark Resolved
                              </button>
                            </div>
                          ) : (
                            <span className="text-[11px] text-ink-400 font-medium">Closed</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Breakdown & Activity Log */}
        <div className="space-y-5">
          {/* Alerts by Type Breakdown Pie Chart */}
          <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
            <h3 className="text-[14.5px] font-bold text-ink-900 mb-3">Alerts by Root Cause</h3>
            <div className="h-44">
              {alerts_by_type && alerts_by_type.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={alerts_by_type}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={65}
                      innerRadius={35}
                    >
                      {alerts_by_type.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color || '#177A5B'} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: 6, border: '1px solid #E2E5E1', fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-ink-400 text-[12px]">
                  No active root-cause alerts.
                </div>
              )}
            </div>
            <div className="space-y-1.5 text-[11.5px] mt-2">
              {alerts_by_type.map((item, i) => (
                <div key={i} className="flex items-center justify-between text-ink-700">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                    <span>{item.name}</span>
                  </div>
                  <span className="font-semibold text-ink-900">{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* SLA Escalation Log */}
          <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
            <h3 className="text-[14.5px] font-bold text-ink-900 mb-3 flex items-center gap-1.5">
              <Clock size={15} className="text-forest-700" /> Recent Escalation Activity (Live DB)
            </h3>
            <div className="space-y-2 text-[11.5px]">
              {recent_activity.length > 0 ? (
                recent_activity.map((act, i) => (
                  <div key={i} className="p-2.5 rounded bg-cream-100/60 border border-ink-100 space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-ink-900">{act.text}</span>
                      <span className="text-ink-400 font-mono text-[10.5px]">{act.time}</span>
                    </div>
                    {act.detail && (
                      <p className="text-[11px] text-ink-600">{act.detail}</p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-ink-400 text-[12px]">No recent escalation events logged.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}