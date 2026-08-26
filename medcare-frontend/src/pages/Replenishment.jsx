import { useState, useEffect, useCallback } from 'react';
import {
  Download, Boxes, Clock, ArrowRight,
  ChevronLeft, ChevronRight, Check, X, Info, Sparkles, ArrowRightLeft, CheckCircle2, Search, History
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
import { formatDate, formatDateTime } from '../utils/dateUtils';

const priorityTone = { critical: 'critical', high: 'warning', medium: 'medium', low: 'good' };
const priorityLabel = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };
const poStatusTone = { Draft: 'neutral', Sent: 'medium', Received: 'good', Approved: 'good', Completed: 'good', Executed: 'good' };

const TABS = [
  'Replenishment Recommendations',
  'Transfers & FEFO Balancing',
  'FEFO Transfer History',
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

  // Independent search states for each of the 4 sections
  const [recSearch, setRecSearch] = useState('');
  const [transferSearch, setTransferSearch] = useState('');
  const [historySearch, setHistorySearch] = useState('');
  const [poSearch, setPoSearch] = useState('');

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
  const purchase_orders = data?.purchase_orders || [];
  const fefo_transfer_history = data?.fefo_transfer_history || data?.completed_demands || [];

  // Filtered lists for each independent search bar
  const filteredRecommendations = recommendations.filter((rec) => {
    if (!recSearch) return true;
    const q = recSearch.toLowerCase().trim();
    return (
      (rec.name || '').toLowerCase().includes(q) ||
      (rec.sku || '').toLowerCase().includes(q) ||
      (rec.warehouse || '').toLowerCase().includes(q) ||
      (rec.supplier || '').toLowerCase().includes(q) ||
      (rec.priority || '').toLowerCase().includes(q)
    );
  });

  const filteredTransfers = transfer_opportunities.filter((t) => {
    if (!transferSearch) return true;
    const q = transferSearch.toLowerCase().trim();
    return (
      (t.product || '').toLowerCase().includes(q) ||
      (t.sku || '').toLowerCase().includes(q) ||
      (t.from || '').toLowerCase().includes(q) ||
      (t.to || '').toLowerCase().includes(q) ||
      (t.reason || '').toLowerCase().includes(q)
    );
  });

  const filteredHistory = fefo_transfer_history.filter((h) => {
    if (!historySearch) return true;
    const q = historySearch.toLowerCase().trim();
    return (
      (h.product || h.name || '').toLowerCase().includes(q) ||
      (h.sku || '').toLowerCase().includes(q) ||
      (h.from || h.sourceWarehouse || '').toLowerCase().includes(q) ||
      (h.to || h.warehouse || h.destinationWarehouse || '').toLowerCase().includes(q) ||
      (h.id || h.referenceId || '').toLowerCase().includes(q) ||
      (h.batchId || '').toLowerCase().includes(q)
    );
  });

  const filteredPurchaseOrders = purchase_orders.filter((po) => {
    if (!poSearch) return true;
    const q = poSearch.toLowerCase().trim();
    return (
      (po.id || '').toLowerCase().includes(q) ||
      (po.supplier || '').toLowerCase().includes(q) ||
      (po.sku || '').toLowerCase().includes(q) ||
      (po.warehouse || '').toLowerCase().includes(q) ||
      (po.status || '').toLowerCase().includes(q)
    );
  });

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

      {/* Section 1: Replenishment Recommendations */}
      {tab === 'Replenishment Recommendations' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
            <div className="xl:col-span-3 bg-white rounded-lg border border-ink-100 shadow-card">
              <div className="p-3.5 border-b border-ink-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h3 className="text-[15px] font-semibold text-ink-900">Explainable Replenishment Recommendations</h3>
                  <span className="text-[11px] text-ink-500 font-medium">Recommended Qty = ML Forecasted Demand − Current Stock</span>
                </div>
                <div className="relative max-w-xs w-full">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
                  <input
                    type="text"
                    placeholder="Search recommendations by SKU, product, DC..."
                    value={recSearch}
                    onChange={(e) => setRecSearch(e.target.value)}
                    className="w-full pl-8 pr-3 py-1.5 text-[12px] rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
                  />
                </div>
              </div>

              {filteredRecommendations.length === 0 ? (
                <EmptyState
                  title={recommendations.length === 0 ? "No Active Replenishment Triggers" : "No Matching Recommendations"}
                  description={recommendations.length === 0 ? "All warehouses currently meet target days-of-cover." : "Try adjusting your search keywords."}
                />
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
                      {filteredRecommendations.map((rec) => (
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
                          <td className="py-2.5 px-3 font-bold text-forest-800">
                            {Number(rec.recommendedQty !== undefined ? rec.recommendedQty : Math.max(0, (rec.forecastDemand || 0) - (rec.currentStock || 0))).toLocaleString()}
                          </td>
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

      {/* Section 2: Transfers & FEFO Balancing */}
      {tab === 'Transfers & FEFO Balancing' && (
        <div className="space-y-5">
          <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
              <div>
                <h3 className="text-[15px] font-semibold text-ink-900">Inter-DC FEFO Balancing Opportunities</h3>
                <p className="text-[11.5px] text-ink-500">Rebalance excess inventory towards deficit DCs to avoid procurement spend and prevent expiry.</p>
              </div>
              <div className="relative max-w-xs w-full">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
                <input
                  type="text"
                  placeholder="Search transfers by SKU, DC..."
                  value={transferSearch}
                  onChange={(e) => setTransferSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-[12px] rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
                />
              </div>
            </div>

            {filteredTransfers.length === 0 ? (
              <EmptyState
                title={transfer_opportunities.length === 0 ? "No Inter-DC Transfer Opportunities" : "No Matching Transfers"}
                description={transfer_opportunities.length === 0 ? "No excess-shortage imbalance detected across DCs." : "Try adjusting your search criteria."}
              />
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
                    {filteredTransfers.map((t) => (
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

      {/* Section 3: FEFO Transfer History */}
      {tab === 'FEFO Transfer History' && (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-ink-100 pb-3">
            <div>
              <h3 className="text-[15px] font-bold text-ink-900 flex items-center gap-1.5">
                <History size={16} className="text-forest-700" /> FEFO Transfer & Balancing History
              </h3>
              <p className="text-[11.5px] text-ink-500">Historical database audit log of executed FEFO inter-DC stock balancing movements.</p>
            </div>
            <div className="relative max-w-xs w-full">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
              <input
                type="text"
                placeholder="Search transfer history..."
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-[12px] rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
              />
            </div>
          </div>

          {filteredHistory.length === 0 ? (
            <EmptyState
              title="No Transfer History Found"
              description="Executed FEFO balancing transfers and completed actions will appear in this database log."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12px]">
                <thead className="bg-cream-200/60 text-ink-600 font-semibold border-b border-ink-100 text-[11px] uppercase">
                  <tr>
                    <th className="py-2.5 px-3">Transfer / Action ID</th>
                    <th className="py-2.5 px-3">Product Name & SKU</th>
                    <th className="py-2.5 px-3">From DC</th>
                    <th className="py-2.5 px-3">To DC</th>
                    <th className="py-2.5 px-3 text-right">Quantity Transferred</th>
                    <th className="py-2.5 px-3">Batch ID</th>
                    <th className="py-2.5 px-3 text-right">Est. Savings</th>
                    <th className="py-2.5 px-3">Execution Time</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {filteredHistory.map((h, hIdx) => (
                    <tr key={h.id || hIdx} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-2.5 px-3 font-mono font-bold text-forest-800">{h.id || h.referenceId || `TRF-${hIdx + 1}`}</td>
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-ink-900">{h.product || h.name}</div>
                        <div className="text-[10px] text-ink-400 font-mono">{h.sku}</div>
                      </td>
                      <td className="py-2.5 px-3 font-mono font-medium text-amber-800">{h.from || h.sourceWarehouse || 'MUM-01'}</td>
                      <td className="py-2.5 px-3 font-mono font-medium text-forest-800">{h.to || h.warehouse || h.destinationWarehouse || 'PAT-01'}</td>
                      <td className="py-2.5 px-3 text-right font-bold text-ink-900">{Number(h.quantity || h.qty || 0).toLocaleString()} units</td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-ink-600">{h.batchId || 'BAT-AUTO-FEFO'}</td>
                      <td className="py-2.5 px-3 text-right font-semibold text-forest-700">{h.savings || '₹0.5 L'}</td>
                      <td className="py-2.5 px-3 text-ink-500 text-[11.5px]">{h.date || h.completedDate || 'Recent'}</td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="px-2 py-0.5 rounded text-[10.5px] font-bold bg-forest-100 text-forest-800">
                          {h.status || 'Executed'}
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

      {/* Section 4: Purchase Orders */}
      {tab === 'Purchase Orders' && (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-ink-100 pb-3">
            <div>
              <h3 className="text-[15px] font-semibold text-ink-900">Supplier Purchase Orders</h3>
              <p className="text-[11.5px] text-ink-500">Live procurement orders issued to pharmaceutical manufacturers & suppliers.</p>
            </div>
            <div className="relative max-w-xs w-full">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
              <input
                type="text"
                placeholder="Search purchase orders..."
                value={poSearch}
                onChange={(e) => setPoSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-[12px] rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
              />
            </div>
          </div>

          {filteredPurchaseOrders.length === 0 ? (
            <EmptyState
              title={purchase_orders.length === 0 ? "No Purchase Orders" : "No Matching Purchase Orders"}
              description={purchase_orders.length === 0 ? "Approved replenishment orders will generate supplier POs." : "Try adjusting your search criteria."}
            />
          ) : (
            <div className="overflow-x-auto">
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
                  {filteredPurchaseOrders.map((po) => (
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
                <span className="font-bold text-forest-800">
                  {Number(reviewItem.recommendedQty !== undefined ? reviewItem.recommendedQty : Math.max(0, (reviewItem.forecastDemand || 0) - (reviewItem.currentStock || 0))).toLocaleString()} units
                </span>
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

            {/* FEFO Batch Allocation Breakdown inside Modal */}
            <div className="border-t border-ink-100 pt-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-ink-900">Live FEFO Batch Allocation</span>
                <span className="text-[11px] text-ink-500 font-medium">Earliest valid expiry prioritized</span>
              </div>

              {loadingFefo ? (
                <div className="py-4 text-center text-ink-400 text-[11.5px]">Loading live batch allocations from PostgreSQL...</div>
              ) : fefoBatches.length === 0 ? (
                <div className="p-2.5 rounded bg-amber-50 text-amber-900 text-[11px] border border-amber-200">
                  No near-expiry source batches available in network. Procurement purchase order recommended.
                </div>
              ) : (
                <div className="max-h-36 overflow-y-auto border border-ink-100 rounded">
                  <table className="w-full text-left text-[11.5px]">
                    <thead className="bg-cream-200/80 text-ink-500 font-semibold sticky top-0">
                      <tr>
                        <th className="py-1.5 px-2">Batch #</th>
                        <th className="py-1.5 px-2">DC</th>
                        <th className="py-1.5 px-2">Expiry</th>
                        <th className="py-1.5 px-2 text-right">Allocated Qty</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-100">
                      {fefoBatches.map((b) => (
                        <tr key={b.batch_id} className="hover:bg-cream-100">
                          <td className="py-1.5 px-2 font-mono font-medium">{b.batch_id}</td>
                          <td className="py-1.5 px-2 font-mono text-ink-600">{b.warehouse_id}</td>
                          <td className="py-1.5 px-2 text-ink-700">{b.expiry_date}</td>
                          <td className="py-1.5 px-2 text-right font-bold text-forest-700">{b.allocated_quantity?.toLocaleString()} units</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-ink-100">
              <button
                onClick={() => setReviewItem(null)}
                className="px-3 py-1.5 text-[12px] border border-ink-200 rounded text-ink-700 hover:bg-cream-200 font-medium cursor-pointer"
              >
                Close
              </button>
              <button
                onClick={() => handleReject(reviewItem.id)}
                disabled={actionProcessing}
                className="px-3 py-1.5 text-[12px] border border-brick-600/30 text-brick-700 bg-brick-50 hover:bg-brick-100 rounded font-medium cursor-pointer disabled:opacity-50"
              >
                Reject
              </button>
              <button
                onClick={() => handleApprove(reviewItem.id)}
                disabled={actionProcessing}
                className="px-3.5 py-1.5 text-[12px] bg-forest-700 hover:bg-forest-600 text-white rounded font-medium shadow-xs cursor-pointer disabled:opacity-50"
              >
                Approve & Execute
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}