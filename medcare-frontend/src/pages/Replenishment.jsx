import { useState, useEffect, useCallback } from 'react';
import {
  Download, Boxes, Clock, ArrowRight,
  ChevronLeft, ChevronRight, Check, X, Info, Sparkles, ArrowRightLeft, CheckCircle2, FileCheck2
} from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import Tabs from '../components/ui/Tabs';
import Modal from '../components/ui/Modal';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';
import { formatDate, formatDateTime } from '../utils/dateUtils';

const priorityTone = { critical: 'critical', high: 'warning', medium: 'medium', low: 'good' };
const priorityLabel = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };
const requestStatusTone = { Pending: 'medium', Acknowledged: 'warning', In_progress: 'warning', Approved: 'good', Completed: 'good', Rejected: 'critical' };
const poStatusTone = { Draft: 'neutral', Sent: 'medium', Received: 'good', Approved: 'good', Completed: 'good' };

const TABS = [
  'Replenishment Recommendations',
  'Active Demands',
  'Completed Demands',
  'Transfers & FEFO Balancing',
  'Approved Orders',
  'Purchase Orders'
];

export default function Replenishment() {
  const { selectedWarehouse, refreshKey, triggerRefresh } = useControlTower();
  const [tab, setTab] = useState(TABS[0]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reviewItem, setReviewItem] = useState(null);
  const [fefoBatches, setFefoBatches] = useState([]);
  const [loadingFefo, setLoadingFefo] = useState(false);
  const [fefoExplorerSku, setFefoExplorerSku] = useState('P-1065');
  const [fefoExplorerWh, setFefoExplorerWh] = useState('MUM-01');
  const [explorerBatches, setExplorerBatches] = useState([]);
  const [loadingExplorer, setLoadingExplorer] = useState(false);
  const [products, setProducts] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionProcessing, setActionProcessing] = useState(false);

  useEffect(() => {
    async function loadMeta() {
      try {
        const [prods, whs] = await Promise.all([
          api.getProducts(),
          api.getWarehouses()
        ]);
        const prodList = Array.isArray(prods) ? prods : [];
        setProducts(prodList);
        const whList = Array.isArray(whs) ? whs : (whs?.overview || []);
        setWarehouses(whList);
        if (prodList.length > 0 && (!fefoExplorerSku || !prodList.some(p => p.sku === fefoExplorerSku))) {
          setFefoExplorerSku(prodList[0].sku);
        }
      } catch (err) {
        console.warn('Failed to load replenishment meta:', err);
      }
    }
    loadMeta();
  }, []);

  const loadReplenishment = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getReplenishmentOverview({
        warehouse: selectedWarehouse !== 'All' ? selectedWarehouse : undefined
      });
      if (res) {
        setData(res);
      } else {
        throw new Error('Failed to load replenishment data');
      }
    } catch (err) {
      console.error('Replenishment load error:', err);
      setError(err.message || 'Unable to connect to Replenishment engine.');
    } finally {
      setLoading(false);
    }
  }, [selectedWarehouse]);

  useEffect(() => {
    loadReplenishment();
  }, [loadReplenishment, refreshKey]);

  useEffect(() => {
    if (!reviewItem) {
      setFefoBatches([]);
      return;
    }
    let isMounted = true;
    setLoadingFefo(true);
    api.getFefoBatches({
      sku: reviewItem.sku,
      warehouse_id: reviewItem.warehouse !== 'Network' ? reviewItem.warehouse : undefined,
      required_qty: reviewItem.recommendedQty
    })
      .then(res => {
        if (isMounted) setFefoBatches(res?.allocations || []);
      })
      .catch(err => console.error('FEFO load error:', err))
      .finally(() => {
        if (isMounted) setLoadingFefo(false);
      });
    return () => { isMounted = false; };
  }, [reviewItem]);

  const loadExplorerBatches = useCallback(async () => {
    setLoadingExplorer(true);
    try {
      const res = await api.getFefoBatches({
        sku: fefoExplorerSku,
        warehouse_id: fefoExplorerWh !== 'All' ? fefoExplorerWh : undefined
      });
      setExplorerBatches(res?.allocations || []);
    } catch (err) {
      console.error('Explorer FEFO error:', err);
    } finally {
      setLoadingExplorer(false);
    }
  }, [fefoExplorerSku, fefoExplorerWh]);

  useEffect(() => {
    if (tab === 'Transfers & FEFO Balancing') {
      loadExplorerBatches();
    }
  }, [tab, loadExplorerBatches, refreshKey]);

  async function handleApprove(id) {
    setActionProcessing(true);
    setActionError(null);
    try {
      const res = await api.approveRecommendation(id);
      setActionSuccess(res.message || `Recommendation ${id} approved! PO / Transfer scheduled in PostgreSQL.`);
      setReviewItem(null);
      triggerRefresh();
      await loadReplenishment();
      setTimeout(() => {
        setActionSuccess(null);
      }, 3000);
    } catch (err) {
      setActionError(`Approval failed: ${err.message}`);
    } finally {
      setActionProcessing(false);
    }
  }

  async function handleReject(id) {
    setActionProcessing(true);
    setActionError(null);
    try {
      const res = await api.rejectRecommendation(id);
      setActionSuccess(res.message || `Recommendation ${id} rejected.`);
      setReviewItem(null);
      triggerRefresh();
      await loadReplenishment();
      setTimeout(() => {
        setActionSuccess(null);
      }, 3000);
    } catch (err) {
      setActionError(`Rejection failed: ${err.message}`);
    } finally {
      setActionProcessing(false);
    }
  }

  async function handleAcknowledgeDemand(id) {
    setActionProcessing(true);
    setActionError(null);
    try {
      const res = await api.acknowledgeDemand(id);
      setActionSuccess(res.message || `Demand ${id} acknowledged in PostgreSQL.`);
      triggerRefresh();
      await loadReplenishment();
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err) {
      setActionError(`Acknowledgment failed: ${err.message}`);
    } finally {
      setActionProcessing(false);
    }
  }

  async function handleCompleteDemand(id) {
    setActionProcessing(true);
    setActionError(null);
    try {
      const res = await api.completeDemand(id);
      setActionSuccess(res.message || `Demand ${id} successfully completed and archived in PostgreSQL.`);
      triggerRefresh();
      await loadReplenishment();
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err) {
      setActionError(`Demand completion failed: ${err.message}`);
    } finally {
      setActionProcessing(false);
    }
  }

  async function handleExecuteTransfer(transferId) {
    setActionProcessing(true);
    setActionError(null);
    try {
      await api.executeTransfer(transferId);
      setActionSuccess(`Transfer ${transferId} executed! Stock synchronized across DCs in database.`);
      triggerRefresh();
      await loadReplenishment();
      setTimeout(() => {
        setActionSuccess(null);
      }, 3000);
    } catch (err) {
      setActionError(`Transfer execution failed: ${err.message}`);
    } finally {
      setActionProcessing(false);
    }
  }

  if (loading && !data) {
    return <LoadingState message="Calculating network-wide safety stocks, EOQ, and FEFO transfer opportunities..." />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={loadReplenishment} />;
  }

  const recommendations = data?.recommendations || [];
  const transfer_opportunities = data?.transfer_opportunities || [];
  const top_suppliers = data?.top_suppliers || [];
  const replenishment_by_category = data?.replenishment_by_category || [];
  const active_demands = data?.active_demands || data?.replenishment_requests || [];
  const completed_demands = data?.completed_demands || [];
  const approved_orders = data?.approved_orders || [];
  const purchase_orders = data?.purchase_orders || [];

  return (
    <div className="space-y-5">
      {/* Tab Navigation */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {actionError && (
        <div className="p-3 rounded-md bg-brick-100 text-brick-700 text-[12.5px] font-medium flex items-center gap-2 border border-brick-600/30 animate-fadeIn">
          <X size={16} className="shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {actionSuccess && (
        <div className="p-3 rounded-md bg-forest-100 text-forest-800 text-[13px] font-semibold flex items-center gap-2 border border-forest-600/30 animate-fadeIn">
          <Check size={16} className="shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Tab 1: Replenishment Recommendations */}
      {tab === 'Replenishment Recommendations' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
            <div className="xl:col-span-3 bg-white rounded-lg border border-ink-100 shadow-card">
              <div className="p-3.5 border-b border-ink-100 flex items-center justify-between">
                <h3 className="text-[15px] font-semibold text-ink-900">Explainable Replenishment Recommendations</h3>
                <span className="text-[11px] text-ink-500 font-medium">Dynamically computed from ML forecasts & lead-time buffers</span>
              </div>

              {recommendations.length === 0 ? (
                <EmptyState title="No Active Replenishment Triggers" description="All warehouses currently meet target days-of-cover." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[12px]">
                    <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                      <tr>
                        <th className="py-2.5 px-3">Priority</th>
                        <th className="py-2.5 px-3">SKU & Product</th>
                        <th className="py-2.5 px-3">Warehouse</th>
                        <th className="py-2.5 px-3">Current Stock</th>
                        <th className="py-2.5 px-3">ML Forecast Demand</th>
                        <th className="py-2.5 px-3">Recommended Qty</th>
                        <th className="py-2.5 px-3">Decision Source</th>
                        <th className="py-2.5 px-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-100">
                      {recommendations.map((rec) => (
                        <tr key={rec.id} className="hover:bg-cream-100/60 transition-colors">
                          <td className="py-2.5 px-3">
                            <Badge tone={priorityTone[rec.priority] || 'warning'}>
                              {priorityLabel[rec.priority] || 'High'}
                            </Badge>
                          </td>
                          <td className="py-2.5 px-3">
                            <div className="font-semibold text-ink-900">{rec.name}</div>
                            <div className="text-[10.5px] text-ink-400 font-mono">{rec.sku}</div>
                          </td>
                          <td className="py-2.5 px-3 font-mono font-medium text-ink-700">{rec.warehouse}</td>
                          <td className="py-2.5 px-3 font-medium text-ink-800">{Number(rec.currentStock || 0).toLocaleString()}</td>
                          <td className="py-2.5 px-3 text-ink-600">{Number(rec.forecastDemand || 0).toLocaleString()}</td>
                          <td className="py-2.5 px-3 font-bold text-forest-800">{Number(rec.recommendedQty || 0).toLocaleString()}</td>
                          <td className="py-2.5 px-3">
                            <span className="text-[11px] px-2 py-0.5 rounded bg-cream-200 text-ink-800 font-medium">
                              {rec.decisionType === 'TRANSFER' || rec.decisionType === 'TRANSFER_FIRST' ? 'FEFO Transfer' : 'Procurement PO'}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            {rec.status === 'APPROVED' ? (
                              <Badge tone="good">Approved</Badge>
                            ) : rec.status === 'REJECTED' ? (
                              <Badge tone="critical">Rejected</Badge>
                            ) : (
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => setReviewItem(rec)}
                                  className="px-2 py-1 text-[11px] border border-ink-200 rounded hover:bg-cream-200 font-medium cursor-pointer"
                                >
                                  Review Why
                                </button>
                                <button
                                  onClick={() => handleApprove(rec.id)}
                                  disabled={actionProcessing}
                                  className="px-2.5 py-1 text-[11px] bg-forest-700 hover:bg-forest-600 text-white rounded font-medium shadow-xs cursor-pointer disabled:opacity-50"
                                >
                                  Approve
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Quick Summary Widgets */}
            <div className="space-y-4">
              <div className="bg-white p-4 rounded-lg border border-ink-100 shadow-card">
                <h4 className="text-[13.5px] font-bold text-ink-900 mb-2">Replenishment by Category</h4>
                <div className="space-y-2">
                  {replenishment_by_category.slice(0, 5).map((cat) => (
                    <div key={cat.category} className="space-y-0.5">
                      <div className="flex justify-between text-[11.5px]">
                        <span className="text-ink-700 font-medium">{cat.category}</span>
                        <span className="text-ink-900 font-bold">{cat.value}</span>
                      </div>
                      <div className="w-full bg-cream-200 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-forest-600 h-full rounded-full" style={{ width: `${Math.min(100, cat.pct)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white p-4 rounded-lg border border-ink-100 shadow-card">
                <h4 className="text-[13.5px] font-bold text-ink-900 mb-2">Top Supplier Fulfillment</h4>
                <div className="space-y-2">
                  {top_suppliers.slice(0, 4).map((s) => (
                    <div key={s.name} className="flex items-center justify-between text-[12px] border-b border-ink-100 pb-1.5 last:border-0">
                      <div>
                        <div className="font-semibold text-ink-900">{s.name}</div>
                        <div className="text-[10px] text-ink-400">OTIF: {s.otif} • LT: {s.leadTime}</div>
                      </div>
                      <span className="font-bold text-forest-800">{s.spend}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Active Demands */}
      {tab === 'Active Demands' && (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-ink-100 pb-2.5">
            <div>
              <h3 className="text-[15px] font-bold text-ink-900">Active Replenishment Demands & Tasks</h3>
              <p className="text-[11.5px] text-ink-500">Live operational demands awaiting acknowledgment, allocation, or fulfillment.</p>
            </div>
            <span className="text-[11px] bg-amber-100 text-amber-900 px-2 py-0.5 rounded font-bold">
              {active_demands.length} Active {active_demands.length === 1 ? 'Demand' : 'Demands'}
            </span>
          </div>

          {active_demands.length === 0 ? (
            <EmptyState title="No Active Demands Pending" description="All replenishment demands have been successfully fulfilled or marked completed." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12px] border-collapse">
                <thead className="bg-cream-200/60 text-ink-600 font-semibold border-b border-ink-100 text-[11px] uppercase">
                  <tr>
                    <th className="py-2.5 px-3">Demand ID</th>
                    <th className="py-2.5 px-3">Product Name & SKU</th>
                    <th className="py-2.5 px-3">Destination DC</th>
                    <th className="py-2.5 px-3 text-right">Quantity</th>
                    <th className="py-2.5 px-3">Source / Supplier</th>
                    <th className="py-2.5 px-3">Requested Date</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                    <th className="py-2.5 px-3 text-right">Lifecycle Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {active_demands.map((d) => (
                    <tr key={d.id} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-2.5 px-3 font-mono font-bold text-forest-800">{d.demandId || d.id}</td>
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-ink-900">{d.name}</div>
                        <div className="text-[10px] text-ink-400 font-mono">{d.sku}</div>
                      </td>
                      <td className="py-2.5 px-3 font-mono font-medium text-ink-700">{d.warehouse || d.destinationWarehouse}</td>
                      <td className="py-2.5 px-3 text-right font-bold text-ink-900">{Number(d.quantity || d.qty || 0).toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-ink-600 font-medium">{d.sourceWarehouse || 'Central Supplier'}</td>
                      <td className="py-2.5 px-3 text-ink-500 text-[11.5px]">{d.requestedDate || d.date}</td>
                      <td className="py-2.5 px-3 text-center">
                        <Badge tone={requestStatusTone[d.status] || 'medium'}>{d.status}</Badge>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {d.rawStatus !== 'ACKNOWLEDGED' && (
                            <button
                              onClick={() => handleAcknowledgeDemand(d.id)}
                              disabled={actionProcessing}
                              className="px-2 py-1 text-[11px] font-medium border border-ink-200 rounded hover:bg-cream-200 text-ink-700 cursor-pointer disabled:opacity-50"
                              title="Acknowledge Receipt of Demand"
                            >
                              Acknowledge
                            </button>
                          )}
                          <button
                            onClick={() => handleCompleteDemand(d.id)}
                            disabled={actionProcessing}
                            className="px-2.5 py-1 text-[11px] font-bold bg-forest-700 hover:bg-forest-600 text-white rounded shadow-xs cursor-pointer disabled:opacity-50"
                            title="Mark Demand as Completed in PostgreSQL"
                          >
                            Mark Completed
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Completed Demands */}
      {tab === 'Completed Demands' && (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-ink-100 pb-2.5">
            <div>
              <h3 className="text-[15px] font-bold text-ink-900 flex items-center gap-1.5">
                <CheckCircle2 size={16} className="text-forest-700" /> Completed & Fulfilled Replenishment Demands
              </h3>
              <p className="text-[11.5px] text-ink-500">Historical database audit log of completed replenishment demands and fulfilled transfers.</p>
            </div>
            <span className="text-[11px] bg-forest-100 text-forest-900 px-2 py-0.5 rounded font-bold">
              {completed_demands.length} Completed {completed_demands.length === 1 ? 'Record' : 'Records'}
            </span>
          </div>

          {completed_demands.length === 0 ? (
            <EmptyState title="No Completed Demands Yet" description="Demands marked completed or fulfilled will appear in this database log." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12px] border-collapse">
                <thead className="bg-cream-200/60 text-ink-600 font-semibold border-b border-ink-100 text-[11px] uppercase">
                  <tr>
                    <th className="py-2.5 px-3">Demand ID</th>
                    <th className="py-2.5 px-3">Product Name & SKU</th>
                    <th className="py-2.5 px-3">Destination DC</th>
                    <th className="py-2.5 px-3 text-right">Fulfilled Quantity</th>
                    <th className="py-2.5 px-3">Source / Supplier</th>
                    <th className="py-2.5 px-3">Requested Date</th>
                    <th className="py-2.5 px-3">Completion Date</th>
                    <th className="py-2.5 px-3">Reference ID</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {completed_demands.map((cd, cdIdx) => (
                    <tr key={cd.id || cdIdx} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-2.5 px-3 font-mono font-bold text-ink-800">{cd.demandId || cd.id}</td>
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-ink-900">{cd.name}</div>
                        <div className="text-[10px] text-ink-400 font-mono">{cd.sku}</div>
                      </td>
                      <td className="py-2.5 px-3 font-mono font-medium text-ink-700">{cd.warehouse || cd.destinationWarehouse}</td>
                      <td className="py-2.5 px-3 text-right font-bold text-forest-800">{Number(cd.quantity || cd.qty || 0).toLocaleString()} units</td>
                      <td className="py-2.5 px-3 text-ink-600 font-medium">{cd.sourceWarehouse || 'Supplier'}</td>
                      <td className="py-2.5 px-3 text-ink-500 text-[11px]">{cd.requestedDate || cd.date}</td>
                      <td className="py-2.5 px-3 text-forest-900 font-medium text-[11px]">{cd.completedDate || cd.requestedDate || '-'}</td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-ink-500">{cd.referenceId || '-'}</td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="px-2 py-0.5 rounded text-[10.5px] font-bold bg-forest-100 text-forest-800">
                          {cd.status || 'Completed'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Transfers & FEFO Balancing */}
      {tab === 'Transfers & FEFO Balancing' && (
        <div className="space-y-5">
          <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
            <h3 className="text-[15px] font-semibold text-ink-900 mb-3">Inter-DC FEFO Balancing Opportunities</h3>
            {transfer_opportunities.length === 0 ? (
              <EmptyState title="No Inter-DC Transfer Opportunities" description="No excess-shortage imbalance detected across DCs." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[12.5px]">
                  <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                    <tr>
                      <th className="py-2.5 px-3">Product</th>
                      <th className="py-2.5 px-3">From DC</th>
                      <th className="py-2.5 px-3">To DC</th>
                      <th className="py-2.5 px-3 text-right">Quantity</th>
                      <th className="py-2.5 px-3 text-right">Est. Savings</th>
                      <th className="py-2.5 px-3">Strategic Rationale</th>
                      <th className="py-2.5 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100">
                    {transfer_opportunities.map((t) => (
                      <tr key={t.id} className="hover:bg-cream-100/60 transition-colors">
                        <td className="py-2.5 px-3 font-semibold text-ink-900">{t.product} ({t.sku})</td>
                        <td className="py-2.5 px-3 font-mono font-medium text-amber-800">{t.from}</td>
                        <td className="py-2.5 px-3 font-mono font-medium text-forest-800">{t.to}</td>
                        <td className="py-2.5 px-3 text-right font-bold">{t.quantity?.toLocaleString()}</td>
                        <td className="py-2.5 px-3 text-right font-semibold text-forest-700">{t.savings}</td>
                        <td className="py-2.5 px-3 text-ink-600 max-w-xs truncate">{t.reason}</td>
                        <td className="py-2.5 px-3 text-right">
                          <button
                            onClick={() => handleExecuteTransfer(t.id)}
                            disabled={actionProcessing}
                            className="px-2.5 py-1 text-[11px] font-medium bg-forest-700 hover:bg-forest-600 text-white rounded shadow-xs cursor-pointer disabled:opacity-50"
                          >
                            Execute Transfer
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Live FEFO Batch Priority Explorer */}
          <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
            <div className="flex items-center justify-between flex-wrap gap-3 pb-3 border-b border-ink-100">
              <div>
                <h4 className="text-[14px] font-bold text-ink-900 flex items-center gap-1.5">
                  <Sparkles size={15} className="text-forest-700" />
                  <span>Live FEFO Batch Priority & Expiry Allocation Explorer</span>
                </h4>
                <p className="text-[11.5px] text-ink-500">Live PostgreSQL batch ordering based on strict First-Expiry-First-Out criteria.</p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={fefoExplorerSku}
                  onChange={(e) => setFefoExplorerSku(e.target.value)}
                  className="px-2.5 py-1 text-[12px] bg-cream-100 border border-ink-200 rounded font-medium text-ink-800"
                >
                  {products.map((p) => (
                    <option key={p.sku} value={p.sku}>{p.name} ({p.sku})</option>
                  ))}
                </select>
                <select
                  value={fefoExplorerWh}
                  onChange={(e) => setFefoExplorerWh(e.target.value)}
                  className="px-2.5 py-1 text-[12px] bg-cream-100 border border-ink-200 rounded font-medium text-ink-800"
                >
                  <option value="All">All Warehouses</option>
                  {warehouses.map((w) => (
                    <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
                  ))}
                </select>
              </div>
            </div>

            {loadingExplorer ? (
              <div className="py-6 text-center text-ink-400 text-[12px]">Loading live batch allocations...</div>
            ) : explorerBatches.length === 0 ? (
              <div className="py-6 text-center text-ink-400 text-[12px]">No active valid batches found for this SKU & location in PostgreSQL.</div>
            ) : (
              <div className="overflow-x-auto mt-3">
                <table className="w-full text-left text-[12px]">
                  <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                    <tr>
                      <th className="py-2 px-3">FEFO Priority</th>
                      <th className="py-2 px-3">Batch Number</th>
                      <th className="py-2 px-3">Warehouse</th>
                      <th className="py-2 px-3">Expiry Date</th>
                      <th className="py-2 px-3">Days to Expiry</th>
                      <th className="py-2 px-3 text-right">Available Qty</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100">
                    {explorerBatches.map((b) => (
                      <tr key={b.batch_id} className="hover:bg-cream-100/60 transition-colors">
                        <td className="py-2 px-3">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${b.priority === 1 ? 'bg-forest-100 text-forest-800 border border-forest-600/30' : 'bg-cream-200 text-ink-700'}`}>
                            Priority {b.priority} {b.priority === 1 ? '★ Next to Dispatch' : ''}
                          </span>
                        </td>
                        <td className="py-2 px-3 font-mono font-bold text-ink-900">{b.batch_id}</td>
                        <td className="py-2 px-3 font-mono text-ink-700">{b.warehouse_id}</td>
                        <td className="py-2 px-3 font-medium text-ink-800">{b.expiry_date}</td>
                        <td className="py-2 px-3">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${b.days_to_expiry <= 30 ? 'bg-brick-100 text-brick-700' : b.days_to_expiry <= 60 ? 'bg-amber-100 text-amber-800' : 'bg-cream-200 text-ink-700'}`}>
                            {b.days_to_expiry} days remaining
                          </span>
                        </td>
                        <td className="py-2 px-3 font-bold text-right text-forest-800">{b.available_quantity?.toLocaleString()} units</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 5: Approved Orders */}
      {tab === 'Approved Orders' && (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
          <h3 className="text-[15px] font-semibold text-ink-900 mb-3">Approved Orders</h3>
          <table className="w-full text-left text-[12.5px]">
            <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
              <tr>
                <th className="py-2.5 px-3">PO Number</th>
                <th className="py-2.5 px-3">Product SKU</th>
                <th className="py-2.5 px-3">Warehouse</th>
                <th className="py-2.5 px-3">Quantity</th>
                <th className="py-2.5 px-3">Value</th>
                <th className="py-2.5 px-3">Approved On</th>
                <th className="py-2.5 px-3 text-right">Expected ETA</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {approved_orders.map((o) => (
                <tr key={o.id} className="hover:bg-cream-100/60 transition-colors">
                  <td className="py-2.5 px-3 font-mono font-medium text-forest-700">{o.id}</td>
                  <td className="py-2.5 px-3 font-semibold text-ink-900">{o.sku || o.name}</td>
                  <td className="py-2.5 px-3 font-mono text-ink-700">{o.warehouse}</td>
                  <td className="py-2.5 px-3 font-medium">{o.qty?.toLocaleString()}</td>
                  <td className="py-2.5 px-3 font-semibold text-ink-900">{o.value}</td>
                  <td className="py-2.5 px-3 text-ink-600">{o.approvedOn}</td>
                  <td className="py-2.5 px-3 text-right font-medium text-forest-700">{o.eta}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 6: Purchase Orders */}
      {tab === 'Purchase Orders' && (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
          <h3 className="text-[15px] font-semibold text-ink-900 mb-3">Supplier Purchase Orders</h3>
          <table className="w-full text-left text-[12.5px]">
            <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
              <tr>
                <th className="py-2.5 px-3">PO Number</th>
                <th className="py-2.5 px-3">Supplier</th>
                <th className="py-2.5 px-3">SKU & Warehouse</th>
                <th className="py-2.5 px-3">Quantity</th>
                <th className="py-2.5 px-3">Total Value</th>
                <th className="py-2.5 px-3">Order Date</th>
                <th className="py-2.5 px-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {purchase_orders.map((po) => (
                <tr key={po.id} className="hover:bg-cream-100/60 transition-colors">
                  <td className="py-2.5 px-3 font-mono font-medium text-forest-700">{po.id}</td>
                  <td className="py-2.5 px-3 font-semibold text-ink-900">{po.supplier}</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-ink-600">{po.sku} @ {po.warehouse}</td>
                  <td className="py-2.5 px-3 font-bold text-ink-800">{po.quantity?.toLocaleString()}</td>
                  <td className="py-2.5 px-3 font-semibold text-ink-900">{po.value}</td>
                  <td className="py-2.5 px-3 text-ink-500">{po.date}</td>
                  <td className="py-2.5 px-3 text-right">
                    <Badge tone={poStatusTone[po.status] || 'neutral'}>{po.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Explainable Decision Review Modal */}
      {reviewItem && (
        <Modal open={Boolean(reviewItem)} onClose={() => setReviewItem(null)} title={`Replenishment Rationale: ${reviewItem.sku}`}>
          <div className="space-y-4 text-[12.5px]">
            <div className="p-3 bg-cream-200/80 rounded-md border border-ink-100 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-ink-500">Product:</span>
                <span className="font-semibold text-ink-900">{reviewItem.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-500">Destination DC:</span>
                <span className="font-semibold text-ink-900">{reviewItem.warehouse}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-500">Recommended Order:</span>
                <span className="font-bold text-forest-800">{reviewItem.recommendedQty?.toLocaleString()} units</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-500">Decision Policy:</span>
                <span className="font-semibold text-ink-900">{reviewItem.decisionType}</span>
              </div>
            </div>

            <div className="space-y-2 border-t border-ink-100 pt-3 text-[12px]">
              <div>
                <span className="font-bold text-ink-900 uppercase">WHAT:</span>
                <p className="text-ink-700">{reviewItem.reasonWhat}</p>
              </div>
              <div>
                <span className="font-bold text-ink-900 uppercase">WHY:</span>
                <p className="text-ink-700">{reviewItem.reasonWhy}</p>
              </div>
              <div>
                <span className="font-bold text-ink-900 uppercase">WHEN:</span>
                <p className="text-ink-700">{reviewItem.reasonWhen}</p>
              </div>
              <div>
                <span className="font-bold text-forest-800 uppercase">EXPECTED IMPACT:</span>
                <p className="text-forest-800 font-medium">{reviewItem.reasonImpact}</p>
              </div>
            </div>

            {/* Live FEFO Batches for this SKU */}
            <div className="border-t border-ink-100 pt-3">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-ink-900 uppercase text-[11.5px]">FEFO Batch Dispatch Priority:</span>
                <span className="text-[11px] text-ink-500 font-medium">Earliest valid expiry prioritized</span>
              </div>
              {loadingFefo ? (
                <div className="py-3 text-center text-ink-400 text-[11.5px]">Loading live batch schedule...</div>
              ) : fefoBatches.length === 0 ? (
                <div className="py-2 text-center text-ink-400 text-[11.5px] bg-cream-100 rounded">No active batches in PostgreSQL for this warehouse.</div>
              ) : (
                <div className="max-h-40 overflow-y-auto rounded border border-ink-100">
                  <table className="w-full text-left text-[11.5px]">
                    <thead className="bg-cream-200 text-ink-600 sticky top-0 font-semibold">
                      <tr>
                        <th className="py-1.5 px-2">Priority</th>
                        <th className="py-1.5 px-2">Batch</th>
                        <th className="py-1.5 px-2">Expiry</th>
                        <th className="py-1.5 px-2">Days Left</th>
                        <th className="py-1.5 px-2 text-right">Avail Qty</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-100">
                      {fefoBatches.map((b) => (
                        <tr key={b.batch_id} className="hover:bg-cream-100">
                          <td className="py-1 px-2">
                            <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${b.priority === 1 ? 'bg-forest-100 text-forest-800' : 'bg-cream-200 text-ink-700'}`}>
                              Rank {b.priority}
                            </span>
                          </td>
                          <td className="py-1 px-2 font-mono font-medium">{b.batch_id}</td>
                          <td className="py-1 px-2 text-ink-700">{b.expiry_date}</td>
                          <td className="py-1 px-2 text-ink-600">{b.days_to_expiry}d</td>
                          <td className="py-1 px-2 text-right font-bold text-forest-800">{b.available_quantity?.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2.5 pt-3 border-t border-ink-100">
              <button
                onClick={() => handleReject(reviewItem.id)}
                disabled={actionProcessing}
                className="px-3.5 py-1.5 border border-brick-600/40 text-brick-700 rounded-md hover:bg-brick-100 cursor-pointer disabled:opacity-50"
              >
                Reject
              </button>
              <button
                onClick={() => handleApprove(reviewItem.id)}
                disabled={actionProcessing}
                className="px-4 py-1.5 font-medium bg-forest-700 text-white rounded-md hover:bg-forest-600 shadow-sm cursor-pointer disabled:opacity-50"
              >
                Approve & Create PO
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}