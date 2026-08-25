import { useState, useEffect, useCallback } from 'react';
import {
  Download, Boxes, Clock, ArrowRight,
  ChevronLeft, ChevronRight, Check, X, Info, Sparkles, ArrowRightLeft
} from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import Tabs from '../components/ui/Tabs';
import Modal from '../components/ui/Modal';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';

const priorityTone = { critical: 'critical', high: 'warning', medium: 'medium', low: 'good' };
const priorityLabel = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };
const requestStatusTone = { Pending: 'medium', Approved: 'good', Rejected: 'critical' };
const poStatusTone = { Draft: 'neutral', Sent: 'medium', Received: 'good', Approved: 'good' };

const TABS = ['Replenishment Recommendations', 'Transfers & FEFO Balancing', 'Replenishment Requests', 'Approved Orders', 'Purchase Orders'];

export default function Replenishment() {
  const { selectedWarehouse, refreshKey, triggerRefresh } = useControlTower();
  const [tab, setTab] = useState(TABS[0]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reviewItem, setReviewItem] = useState(null);
  const [fefoBatches, setFefoBatches] = useState([]);
  const [loadingFefo, setLoadingFefo] = useState(false);
  const [fefoExplorerSku, setFefoExplorerSku] = useState('P-1042');
  const [fefoExplorerWh, setFefoExplorerWh] = useState('MUM-01');
  const [explorerBatches, setExplorerBatches] = useState([]);
  const [loadingExplorer, setLoadingExplorer] = useState(false);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionProcessing, setActionProcessing] = useState(false);

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
  const replenishment_requests = data?.replenishment_requests || [];
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

            {/* Sidebar Summary */}
            <div className="space-y-5">
              <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
                <h4 className="text-[14px] font-bold text-ink-900 mb-3">Replenishment by Category</h4>
                <div className="space-y-2 text-[12px]">
                  {replenishment_by_category.map((cat, i) => (
                    <div key={i} className="flex justify-between py-1 border-b border-ink-100 last:border-0">
                      <span className="text-ink-600">{cat.category}</span>
                      <span className="font-semibold text-ink-900">{cat.value} ({cat.pct}%)</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
                <h4 className="text-[14px] font-bold text-ink-900 mb-3">Top Contracted Suppliers</h4>
                <div className="space-y-2.5 text-[11.5px]">
                  {top_suppliers.map((s, i) => (
                    <div key={i} className="p-2 rounded bg-cream-100/60 border border-ink-100">
                      <div className="font-semibold text-ink-900">{s.name}</div>
                      <div className="flex justify-between text-ink-500 mt-1">
                        <span>Lead Time: {s.leadTime}</span>
                        <span>OTIF: {s.otif}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Transfers & FEFO Balancing */}
      {tab === 'Transfers & FEFO Balancing' && (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-[15px] font-semibold text-ink-900">Inter-DC FEFO Balancing Opportunities</h3>
              <p className="text-[11.5px] text-ink-500">Transfers near-expiry stock from low-velocity metros to high-demand Tier-2 DCs, eliminating stockouts without new purchase orders.</p>
            </div>
          </div>

          {transfer_opportunities.length === 0 ? (
            <EmptyState title="No Inter-DC Transfers Required" description="All regional warehouse inventories are currently balanced." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12px]">
                <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                  <tr>
                    <th className="py-2.5 px-3">Transfer Route</th>
                    <th className="py-2.5 px-3">SKU & Product</th>
                    <th className="py-2.5 px-3">Quantity</th>
                    <th className="py-2.5 px-3">Estimated Cost</th>
                    <th className="py-2.5 px-3">Emergency Purchase Saved</th>
                    <th className="py-2.5 px-3">Rationale</th>
                    <th className="py-2.5 px-3 text-right">Execution</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {transfer_opportunities.map((trf) => (
                    <tr key={trf.id} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-3 px-3">
                        <div className="font-semibold text-ink-900 flex items-center gap-1.5">
                          <span>{trf.from}</span>
                          <ArrowRight size={13} className="text-forest-700" />
                          <span className="text-forest-800">{trf.to}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-semibold text-ink-900">{trf.product}</div>
                        <div className="text-[10.5px] text-ink-400 font-mono">{trf.sku}</div>
                      </td>
                      <td className="py-3 px-3 font-bold text-forest-800">{trf.quantity?.toLocaleString()} units</td>
                      <td className="py-3 px-3 text-ink-600">{trf.cost}</td>
                      <td className="py-3 px-3 font-semibold text-forest-700">{trf.savings}</td>
                      <td className="py-3 px-3 text-[11px] text-ink-600 max-w-xs">{trf.reason}</td>
                      <td className="py-3 px-3 text-right">
                        {trf.status === 'COMPLETED' ? (
                          <Badge tone="good">Completed</Badge>
                        ) : (
                          <button
                            onClick={() => handleExecuteTransfer(trf.id)}
                            disabled={actionProcessing}
                            className="px-3 py-1.5 text-[11.5px] bg-forest-700 hover:bg-forest-600 text-white rounded font-medium shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                          >
                            Execute Transfer
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Live FEFO Batch Priority Explorer */}
          <div className="mt-5 bg-white rounded-lg border border-ink-100 shadow-card p-4">
            <div className="flex items-center justify-between flex-wrap gap-3 pb-3 border-b border-ink-100">
              <div>
                <h4 className="text-[14px] font-bold text-ink-900 flex items-center gap-1.5">
                  <Sparkles size={15} className="text-forest-700" />
                  <span>Live FEFO Batch Priority & Expiry Allocation Explorer</span>
                </h4>
                <p className="text-[11.5px] text-ink-500">Live PostgreSQL batch ordering based on strict First-Expiry-First-Out criteria (excluding expired & zero-quantity batches).</p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={fefoExplorerSku}
                  onChange={(e) => setFefoExplorerSku(e.target.value)}
                  className="px-2.5 py-1 text-[12px] bg-cream-100 border border-ink-200 rounded font-medium text-ink-800"
                >
                  <option value="P-1042">Paracetamol 500mg (P-1042)</option>
                  <option value="AZ-3391">Azithromycin 500mg (AZ-3391)</option>
                  <option value="C-5562">Ceftriaxone 1g (C-5562)</option>
                  <option value="INS-100">Human Insulin 100IU (INS-100)</option>
                  <option value="FEFO-TEST-001">FEFO-TEST-001 (Dedicated Test SKU)</option>
                </select>
                <select
                  value={fefoExplorerWh}
                  onChange={(e) => setFefoExplorerWh(e.target.value)}
                  className="px-2.5 py-1 text-[12px] bg-cream-100 border border-ink-200 rounded font-medium text-ink-800"
                >
                  <option value="All">All Warehouses</option>
                  <option value="MUM-01">MUM-01 (Mumbai)</option>
                  <option value="DEL-02">DEL-02 (Delhi)</option>
                  <option value="PAT-01">PAT-01 (Patna)</option>
                  <option value="WH-TEST-01">WH-TEST-01 (Test DC 1)</option>
                  <option value="WH-TEST-02">WH-TEST-02 (Test DC 2)</option>
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

      {/* Tab 3: Replenishment Requests */}
      {tab === 'Replenishment Requests' && (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
          <h3 className="text-[15px] font-semibold text-ink-900 mb-3">Active Replenishment Requests</h3>
          <table className="w-full text-left text-[12.5px]">
            <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
              <tr>
                <th className="py-2.5 px-3">Request ID</th>
                <th className="py-2.5 px-3">Product Name</th>
                <th className="py-2.5 px-3">DC Location</th>
                <th className="py-2.5 px-3">Quantity</th>
                <th className="py-2.5 px-3">Requester</th>
                <th className="py-2.5 px-3">Date</th>
                <th className="py-2.5 px-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {replenishment_requests.map((r) => (
                <tr key={r.id} className="hover:bg-cream-100/60 transition-colors">
                  <td className="py-2.5 px-3 font-mono font-medium text-forest-700">{r.id}</td>
                  <td className="py-2.5 px-3 font-semibold text-ink-900">{r.name}</td>
                  <td className="py-2.5 px-3 font-mono text-ink-700">{r.warehouse}</td>
                  <td className="py-2.5 px-3 font-medium">{r.qty?.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-ink-600">{r.requestedBy}</td>
                  <td className="py-2.5 px-3 text-ink-500">{r.date}</td>
                  <td className="py-2.5 px-3 text-right">
                    <Badge tone={requestStatusTone[r.status] || 'medium'}>{r.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 4: Approved Orders */}
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

      {/* Tab 5: Purchase Orders */}
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