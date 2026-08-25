import { useState, useEffect, useMemo, useCallback } from 'react';
import React from 'react';
import {
  Search, Plus, Download, Package, Boxes, AlertOctagon, PackageX,
  ShoppingCart, ArrowRightLeft, History, ChevronDown, ChevronRight,
  Layers, Trash2, HelpCircle, Calendar, Sparkles, Clock
} from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import TransactionModal from '../components/transactions/TransactionModal';
import AddProductModal from '../components/inventory/AddProductModal';
import RecordSaleModal from '../components/inventory/RecordSaleModal';
import { riskTone, riskLabel } from '../data/riskTone';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';

const quickFilters = [
  { key: 'all', label: 'All Items', test: () => true },
  { key: 'low', label: 'Low Stock', test: (p) => p.status === 'Low Stock' || p.status === 'LOW_STOCK' || (Number(p.currentStock || 0) < Number(p.reorderPoint || 0) && Number(p.currentStock || 0) > 0) },
  { key: 'out', label: 'Out of Stock', test: (p) => p.status === 'Out of Stock' || p.status === 'OUT_OF_STOCK' || p.status === 'CRITICAL' || Number(p.currentStock || 0) === 0 },
  { key: 'expiring', label: 'Expiring Soon (<60d)', test: (p) => Number(p.daysToExpiry || 999) <= 60 || (p.batches && p.batches.some(b => Number(b.daysToExpiry) <= 60)) },
  { key: 'slow', label: 'Overstock', test: (p) => p.status === 'OVERSTOCK' || p.status === 'Overstock' || Number(p.currentStock || 0) > Number(p.reorderPoint || 0) * 1.8 },
];

export default function Inventory() {
  const { selectedWarehouse, setSelectedWarehouse, refreshKey, triggerRefresh } = useControlTower();
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [quickFilter, setQuickFilter] = useState('all');
  const [rollupView, setRollupView] = useState(true);
  const [expandedSkus, setExpandedSkus] = useState({});
  const [expandedTxIds, setExpandedTxIds] = useState({});

  // Modals State
  const [txModalOpen, setTxModalOpen] = useState(false);
  const [addProductOpen, setAddProductOpen] = useState(false);
  const [recordSaleOpen, setRecordSaleOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);

  const loadInventory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [items, cats, whs, txs] = await Promise.all([
        api.getInventory({
          warehouse: selectedWarehouse,
          category: categoryFilter,
          quick_filter: quickFilter,
          rollup: rollupView && selectedWarehouse === 'All'
        }),
        api.getCategories(),
        api.getWarehouses(),
        api.getTransactions({ warehouse: selectedWarehouse !== 'All' ? selectedWarehouse : undefined, limit: 12 })
      ]);
      setProducts(Array.isArray(items) ? items : []);
      setCategories(Array.isArray(cats) ? cats : []);
      setWarehouses(Array.isArray(whs) ? whs : (whs?.overview || []));
      setRecentTransactions(Array.isArray(txs) ? txs : []);
    } catch (err) {
      console.error('Failed to load inventory:', err);
      setError(err.message || 'Unable to connect to inventory backend service.');
    } finally {
      setLoading(false);
    }
  }, [selectedWarehouse, categoryFilter, quickFilter, rollupView]);

  useEffect(() => {
    loadInventory();
  }, [loadInventory, refreshKey]);

  const filtered = useMemo(() => {
    return products.filter((p) => {
      const pName = p.name || '';
      const pSku = p.sku || '';
      const matchesSearch =
        pName.toLowerCase().includes(search.toLowerCase()) ||
        pSku.toLowerCase().includes(search.toLowerCase());

      const activeQFilter = quickFilters.find((f) => f.key === quickFilter);
      const matchesQuick = activeQFilter ? activeQFilter.test(p) : true;

      return matchesSearch && matchesQuick;
    });
  }, [products, search, quickFilter]);

  // Derived Dynamic KPIs from Live Database Records for the current active filter context
  const totalUnits = useMemo(() => filtered.reduce((sum, p) => sum + Number(p.currentStock || 0), 0), [filtered]);
  const lowStockCount = useMemo(() => filtered.filter((p) => (p.status === 'Low Stock' || p.status === 'LOW_STOCK' || (Number(p.currentStock || 0) < Number(p.reorderPoint || 0) && Number(p.currentStock || 0) > 0))).length, [filtered]);
  const outOfStockCount = useMemo(() => filtered.filter((p) => Number(p.currentStock || 0) === 0 || p.status === 'Out of Stock' || p.status === 'OUT_OF_STOCK' || p.status === 'CRITICAL').length, [filtered]);

  function handleOpenTxModal(prod = null) {
    if (prod) {
      const isAggregateWh = !prod.warehouse || ['all', 'all warehouses', 'network', 'network rollup'].includes(String(prod.warehouse).toLowerCase());
      const normalizedWh = isAggregateWh
        ? (prod.warehouseBreakdown?.[0]?.warehouseId || (selectedWarehouse !== 'All' ? selectedWarehouse : 'MUM-01'))
        : prod.warehouse;
      setSelectedProduct({ ...prod, warehouse: normalizedWh, warehouse_id: normalizedWh });
    } else {
      const defaultWh = selectedWarehouse !== 'All' ? selectedWarehouse : 'MUM-01';
      setSelectedProduct({ warehouse: defaultWh, warehouse_id: defaultWh });
    }
    setTxModalOpen(true);
  }

  function handleOpenSaleModal(prod = null) {
    if (prod) {
      const isAggregateWh = !prod.warehouse || ['all', 'all warehouses', 'network', 'network rollup'].includes(String(prod.warehouse).toLowerCase());
      const normalizedWh = isAggregateWh
        ? (prod.warehouseBreakdown?.[0]?.warehouseId || (selectedWarehouse !== 'All' ? selectedWarehouse : 'MUM-01'))
        : prod.warehouse;
      setSelectedProduct({ ...prod, warehouse: normalizedWh, warehouse_id: normalizedWh });
    } else {
      const defaultWh = selectedWarehouse !== 'All' ? selectedWarehouse : 'MUM-01';
      setSelectedProduct({ warehouse: defaultWh, warehouse_id: defaultWh });
    }
    setRecordSaleOpen(true);
  }

  function toggleSkuExpand(sku) {
    setExpandedSkus((prev) => ({ ...prev, [sku]: !prev[sku] }));
  }

  function toggleTxExpand(txId) {
    setExpandedTxIds((prev) => ({ ...prev, [txId]: !prev[txId] }));
  }

  async function handleDeleteProduct(sku, name) {
    if (window.confirm(`Are you sure you want to delete product "${name}" (${sku}) from the database? All associated batches, transactions, and alerts will be permanently removed.`)) {
      try {
        await api.deleteProduct(sku);
        triggerRefresh();
        await loadInventory();
      } catch (err) {
        alert(`Failed to delete product: ${err.message}`);
      }
    }
  }

  function exportCSV() {
    if (!filtered.length) return;
    const headers = ['SKU', 'Name', 'Category', 'Warehouse', 'Current Stock', 'Reorder Point', 'Unit Cost', 'Days of Cover', 'Status'];
    const rows = filtered.map(p => [
      p.sku,
      `"${p.name}"`,
      p.category,
      p.warehouse,
      p.currentStock,
      p.reorderPoint,
      p.unitCost,
      p.daysOfCover,
      p.status
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `medcare_inventory_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  const isRollupMode = rollupView && selectedWarehouse === 'All';

  return (
    <div className="space-y-5">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3.5 rounded-lg border border-ink-100 shadow-card">
        <div>
          <h2 className="text-[16px] font-bold text-ink-900">Inventory Management & Stock Tracking</h2>
          <p className="text-[12px] text-ink-500">Live multi-echelon stock levels, FEFO batch expiry dates, and real-time inventory adjustments.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-ink-200 rounded-md text-[12px] font-medium text-ink-700 hover:bg-cream-200 transition-colors cursor-pointer"
          >
            <Download size={14} /> Export CSV
          </button>
          <button
            onClick={() => handleOpenSaleModal()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-forest-100 border border-forest-600/30 text-forest-900 rounded-md text-[12px] font-semibold hover:bg-forest-200 transition-colors cursor-pointer shadow-xs"
          >
            <ShoppingCart size={14} className="text-forest-700" /> Record Sale
          </button>
          <button
            onClick={() => setAddProductOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-forest-600 text-forest-800 rounded-md text-[12px] font-semibold hover:bg-forest-50 transition-colors cursor-pointer"
          >
            <Plus size={14} /> Add New Product
          </button>
          <button
            onClick={() => handleOpenTxModal()}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[12px] font-semibold transition-colors shadow-sm cursor-pointer"
          >
            <Plus size={15} /> Record Stock Tx
          </button>
        </div>
      </div>

      {/* Dynamic KPI Cards - Context Aware for Active Tab */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Boxes}
          tone="forest"
          label="Tracked SKUs"
          value={filtered.length}
          delta={quickFilter === 'all' ? 'Active database catalog' : `Filtered: ${quickFilters.find(f => f.key === quickFilter)?.label}`}
          deltaPositive={true}
        />
        <StatCard
          icon={Package}
          tone="gold"
          label="Total Units in Stock"
          value={totalUnits.toLocaleString()}
          delta={selectedWarehouse === 'All' ? 'Across all regional DCs' : `In DC ${selectedWarehouse}`}
          deltaPositive={true}
        />
        <StatCard
          icon={AlertOctagon}
          tone="brick"
          label="Low Stock SKUs"
          value={lowStockCount}
          delta="Below dynamic reorder point"
          deltaPositive={lowStockCount === 0}
        />
        <StatCard
          icon={PackageX}
          tone="brick"
          label="Stockout Incidents"
          value={outOfStockCount}
          delta="Zero available inventory"
          deltaPositive={outOfStockCount === 0}
        />
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-3.5 rounded-lg border border-ink-100 shadow-card space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1 max-w-md">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
            <input
              type="text"
              placeholder="Search by SKU or Product Name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-[12.5px] rounded-md border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
            />
          </div>

          {/* Select Dropdowns & View Toggle */}
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={selectedWarehouse}
              onChange={(e) => setSelectedWarehouse(e.target.value)}
              className="text-[12px] px-2.5 py-1.5 rounded-md border border-ink-200 bg-white text-ink-700 focus:outline-none focus:border-forest-600"
            >
              <option value="All">🌐 All Warehouses</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
              ))}
            </select>

            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="text-[12px] px-2.5 py-1.5 rounded-md border border-ink-200 bg-white text-ink-700 focus:outline-none focus:border-forest-600"
            >
              <option value="All">All Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>

            {selectedWarehouse === 'All' && (
              <button
                onClick={() => setRollupView(!rollupView)}
                className={`px-3 py-1.5 rounded-md text-[11.5px] font-medium border transition-colors flex items-center gap-1 cursor-pointer ${
                  rollupView
                    ? 'bg-forest-100 border-forest-600/40 text-forest-900 font-semibold'
                    : 'bg-white border-ink-200 text-ink-600 hover:bg-cream-100'
                }`}
                title="Toggle consolidated SKU view with expandable DC breakdown"
              >
                <Layers size={13} />
                {rollupView ? 'Consolidated Stock View' : 'All Warehouse Rows'}
              </button>
            )}
          </div>
        </div>

        {/* Quick Filter Tabs */}
        <div className="flex items-center gap-1.5 border-t border-ink-100 pt-2.5 overflow-x-auto">
          {quickFilters.map((qf) => (
            <button
              key={qf.key}
              onClick={() => setQuickFilter(qf.key)}
              className={`px-3 py-1 text-[11.5px] rounded-full font-medium transition-colors whitespace-nowrap cursor-pointer ${
                quickFilter === qf.key
                  ? 'bg-forest-700 text-white shadow-xs'
                  : 'bg-cream-200/80 text-ink-600 hover:bg-cream-200'
              }`}
            >
              {qf.label}
            </button>
          ))}
        </div>
      </div>

      {/* Inventory Items Table with Pure Table Cell Alignment */}
      {loading ? (
        <LoadingState message="Loading live inventory records from PostgreSQL..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadInventory} />
      ) : filtered.length === 0 ? (
        <EmptyState title="No Inventory Items Found" description="No SKU records match your active search and filter criteria." />
      ) : (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12px] border-collapse">
              <thead className="bg-cream-200/70 text-ink-600 font-semibold border-b border-ink-100 text-[11.5px] uppercase tracking-wider">
                <tr>
                  {isRollupMode && <th className="w-9 py-3 pl-3 pr-1 text-center"></th>}
                  <th className="py-3 px-3 text-left">SKU & Product</th>
                  <th className="py-3 px-3 text-left w-28">Category</th>
                  <th className="py-3 px-3 text-left w-32">Warehouse Scope</th>
                  <th className="py-3 px-3 text-right w-28">Total Stock</th>
                  <th className="py-3 px-3 text-right w-24">Reorder Point</th>
                  <th className="py-3 px-3 text-right w-24">Days of Cover</th>
                  <th className="py-3 px-3 text-center w-28">Health Status</th>
                  <th className="py-3 px-3 text-right w-36">Quick Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {filtered.map((item, idx) => {
                  const currentStock = Number(item.currentStock || 0);
                  const reorderPoint = Number(item.reorderPoint || 0);
                  const daysCover = Number(item.daysOfCover || 0);
                  const hasBreakdown = item.warehouseBreakdown && item.warehouseBreakdown.length > 0;
                  const itemBatches = item.batches || [];
                  const isExpanded = expandedSkus[item.sku];

                  return (
                    <React.Fragment key={item.sku || idx}>
                      {/* Main Summary Row */}
                      <tr className={`hover:bg-cream-100/60 transition-colors ${isExpanded ? 'bg-cream-50/70' : ''}`}>
                        {isRollupMode && (
                          <td className="w-9 py-3 pl-3 pr-1 text-center align-middle">
                            {hasBreakdown && (
                              <button
                                onClick={() => toggleSkuExpand(item.sku)}
                                className="text-ink-400 hover:text-forest-700 p-1 rounded hover:bg-cream-200 transition-colors cursor-pointer inline-flex items-center justify-center"
                                title="View DC & Batch Breakdown"
                              >
                                {isExpanded ? <ChevronDown size={15} className="text-forest-700" /> : <ChevronRight size={15} />}
                              </button>
                            )}
                          </td>
                        )}
                        <td className="py-3 px-3 text-left align-middle">
                          <div className="font-semibold text-ink-900 leading-snug">{item.name}</div>
                          <div className="text-[10.5px] text-ink-400 font-mono">{item.sku}</div>
                        </td>
                        <td className="py-3 px-3 text-left align-middle text-ink-600 font-medium">
                          {item.category}
                        </td>
                        <td className="py-3 px-3 text-left align-middle font-mono font-medium text-ink-700">
                          {item.warehouse}
                        </td>
                        <td className="py-3 px-3 text-right align-middle">
                          <div className="font-bold text-ink-900">{currentStock.toLocaleString()}</div>
                          <div className="text-[10px] text-ink-400 font-normal">{item.unit || 'Units'}</div>
                        </td>
                        <td className="py-3 px-3 text-right align-middle text-ink-600 font-mono">
                          {reorderPoint.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right align-middle">
                          <span className={`font-semibold ${daysCover <= 5 ? 'text-brick-600' : daysCover <= 12 ? 'text-amber-600' : 'text-forest-700'}`}>
                            {daysCover.toFixed(1)}d
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center align-middle">
                          <Badge tone={riskTone[item.risk] || (item.status === 'Healthy' ? 'good' : item.status === 'Low Stock' ? 'warning' : 'critical')}>
                            {item.status || riskLabel[item.risk] || 'Active'}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-right align-middle">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => handleOpenTxModal(item)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded border border-ink-200 text-ink-700 hover:bg-forest-50 hover:text-forest-700 hover:border-forest-600 transition-colors cursor-pointer shadow-xs"
                              title="Record Inventory Transaction (Sale, Receipt, Audit, Transfer)"
                            >
                              <Plus size={12} /> Stock Tx
                            </button>
                            <button
                              onClick={() => handleDeleteProduct(item.sku, item.name)}
                              className="inline-flex items-center gap-1 p-1 text-[11px] font-medium rounded border border-brick-600/30 text-brick-700 hover:bg-brick-100 transition-colors cursor-pointer"
                              title="Archive / Delete Product"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </td>
                      </tr>

                      {/* Collapsible Per-DC & Batch Breakdown View */}
                      {isExpanded && (
                        <tr className="bg-cream-100/40">
                          <td colSpan={isRollupMode ? 9 : 8} className="p-0">
                            <div className="border-t border-b border-ink-100/80 px-6 py-4 space-y-4 animate-fadeIn">
                              {/* 1. Regional DC Breakdown Table */}
                              {hasBreakdown && (
                                <div className="space-y-2">
                                  <div className="text-[12px] font-bold text-ink-800 flex items-center gap-1.5">
                                    <Layers size={14} className="text-forest-700" />
                                    <span>Regional DC Inventory Breakdown for {item.name} ({item.sku}):</span>
                                  </div>
                                  <table className="w-full text-left text-[11.5px] bg-white rounded-md border border-ink-100 shadow-xs">
                                    <thead className="bg-cream-200/60 text-ink-600 font-semibold border-b border-ink-100 text-[10.5px] uppercase">
                                      <tr>
                                        <th className="py-2 px-3">DC Location</th>
                                        <th className="py-2 px-3 text-right">
                                          <span className="inline-flex items-center gap-1 justify-end">
                                            Total Stock
                                            <span title="Physical stock count located on warehouse shelves" className="text-ink-400 cursor-help">
                                              <HelpCircle size={11} />
                                            </span>
                                          </span>
                                        </th>
                                        <th className="py-2 px-3 text-right">
                                          <span className="inline-flex items-center gap-1 justify-end text-forest-800">
                                            Available to Sell
                                            <span title="Available for orders and dispatch (Physical stock minus reserved units)" className="text-ink-400 cursor-help">
                                              <HelpCircle size={11} />
                                            </span>
                                          </span>
                                        </th>
                                        <th className="py-2 px-3 text-right">Reorder Point (ROP)</th>
                                        <th className="py-2 px-3 text-right">Days of Cover</th>
                                        <th className="py-2 px-3 text-center">Status</th>
                                        <th className="py-2 px-3 text-right">Action</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-ink-100">
                                      {item.warehouseBreakdown.map((wb, wIdx) => (
                                        <tr key={wIdx} className="hover:bg-cream-100/50">
                                          <td className="py-2 px-3 font-mono font-bold text-ink-800">{wb.warehouseId}</td>
                                          <td className="py-2 px-3 text-right font-bold text-ink-900">{Number(wb.currentStock).toLocaleString()}</td>
                                          <td className="py-2 px-3 text-right font-semibold text-forest-700">{Number(wb.availableStock).toLocaleString()}</td>
                                          <td className="py-2 px-3 text-right text-ink-500 font-mono">{Number(wb.reorderPoint).toLocaleString()}</td>
                                          <td className="py-2 px-3 text-right font-semibold text-forest-700">{Number(wb.daysOfCover).toFixed(1)}d</td>
                                          <td className="py-2 px-3 text-center">
                                            <Badge tone={riskTone[wb.risk] || 'good'}>{wb.status}</Badge>
                                          </td>
                                          <td className="py-2 px-3 text-right">
                                            <button
                                              onClick={() => handleOpenTxModal({ sku: item.sku, warehouse: wb.warehouseId, currentStock: wb.currentStock })}
                                              className="text-forest-700 hover:text-forest-900 hover:underline text-[11px] font-semibold cursor-pointer"
                                            >
                                              + Transact
                                            </button>
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}

                              {/* 2. Live Database Batch Expiry Details per Batch (Item #6 Fix) */}
                              <div className="space-y-2 pt-1">
                                <div className="text-[12px] font-bold text-ink-800 flex items-center justify-between">
                                  <span className="flex items-center gap-1.5">
                                    <Calendar size={14} className="text-forest-700" />
                                    <span>Individual Batch Expiry Schedule (Live FEFO Database Records):</span>
                                  </span>
                                  <span className="text-[11px] text-ink-400 font-normal">
                                    {itemBatches.length} active {itemBatches.length === 1 ? 'batch' : 'batches'} registered
                                  </span>
                                </div>

                                {itemBatches.length === 0 ? (
                                  <div className="p-3 bg-white rounded border border-ink-100 text-ink-400 text-[11.5px] text-center">
                                    No active batch records currently in database for this SKU.
                                  </div>
                                ) : (
                                  <table className="w-full text-left text-[11.5px] bg-white rounded-md border border-ink-100 shadow-xs">
                                    <thead className="bg-cream-200/60 text-ink-600 font-semibold border-b border-ink-100 text-[10.5px] uppercase">
                                      <tr>
                                        <th className="py-2 px-3">Batch Number</th>
                                        <th className="py-2 px-3">DC Warehouse</th>
                                        <th className="py-2 px-3 text-right">Batch Quantity</th>
                                        <th className="py-2 px-3 text-right">Available Qty</th>
                                        <th className="py-2 px-3">Expiry Date</th>
                                        <th className="py-2 px-3">Shelf Life Remaining</th>
                                        <th className="py-2 px-3 text-center">Batch Status</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-ink-100">
                                      {itemBatches.map((b, bIdx) => {
                                        const dExp = Number(b.daysToExpiry);
                                        return (
                                          <tr key={b.batchId || bIdx} className="hover:bg-cream-100/50">
                                            <td className="py-2 px-3 font-mono font-bold text-ink-900">{b.batchId}</td>
                                            <td className="py-2 px-3 font-mono text-ink-700">{b.warehouseId}</td>
                                            <td className="py-2 px-3 text-right font-medium text-ink-900">{Number(b.quantity || 0).toLocaleString()}</td>
                                            <td className="py-2 px-3 text-right font-semibold text-forest-800">{Number(b.availableQuantity || b.quantity || 0).toLocaleString()}</td>
                                            <td className="py-2 px-3 font-medium text-ink-800">{b.expiryDate}</td>
                                            <td className="py-2 px-3">
                                              <span className={`px-2 py-0.5 rounded text-[10.5px] font-medium ${
                                                dExp <= 30
                                                  ? 'bg-brick-100 text-brick-700 font-bold'
                                                  : dExp <= 60
                                                  ? 'bg-amber-100 text-amber-800 font-semibold'
                                                  : 'bg-cream-200 text-ink-700'
                                              }`}>
                                                {dExp} days ({dExp <= 30 ? 'Near Expiry' : dExp <= 60 ? 'Watchlist' : 'Safe'})
                                              </span>
                                            </td>
                                            <td className="py-2 px-3 text-center">
                                              <Badge tone={b.status === 'ACTIVE' ? 'good' : b.status === 'NEAR_EXPIRY' ? 'warning' : 'critical'}>
                                                {b.status}
                                              </Badge>
                                            </td>
                                          </tr>
                                        );
                                      })}
                                    </tbody>
                                  </table>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Inventory Transactions Live Audit Log (Item #7 Expand/Collapse & Real Timestamps) */}
      <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-[14.5px] font-bold text-ink-900 flex items-center gap-1.5">
            <History size={16} className="text-forest-700" /> Recent Inventory Transactions (Live PostgreSQL Log)
          </h3>
          <span className="text-[11px] text-ink-500 font-mono">Real-Time Inbound/Outbound Audit Ledger</span>
        </div>

        {recentTransactions.length === 0 ? (
          <p className="text-[12px] text-ink-400">No recent transactions recorded yet in PostgreSQL.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[11.5px] border-collapse">
              <thead className="bg-cream-200/60 text-ink-600 font-semibold border-b border-ink-100 text-[10.5px] uppercase">
                <tr>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">SKU & Product</th>
                  <th className="py-2.5 px-3">Warehouse</th>
                  <th className="py-2.5 px-3 text-right">Quantity</th>
                  <th className="py-2.5 px-3 text-center">Stock Delta</th>
                  <th className="py-2.5 px-3">Reason / Reference</th>
                  <th className="py-2.5 px-3 text-right">Server Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {recentTransactions.map((tx) => {
                  const isNeg = Number(tx.quantity) < 0 || ['SALE', 'CONSUMPTION', 'TRANSFER_OUT'].includes(tx.transactionType);
                  const isExpandedTx = expandedTxIds[tx.id];
                  const fullReason = tx.reason || tx.referenceId || '-';
                  const isLongReason = fullReason.length > 35;

                  // Clean display timestamp
                  const formattedTimeStr = tx.formattedTime || (tx.timestamp ? new Date(tx.timestamp).toLocaleString() : '-');

                  return (
                    <tr key={tx.id} className="hover:bg-cream-100/50 transition-colors">
                      <td className="py-2.5 px-3 font-semibold text-ink-800">
                        <span className={`px-2 py-0.5 rounded text-[10.5px] font-bold ${
                          tx.transactionType === 'RECEIPT' || tx.transactionType === 'TRANSFER_IN'
                            ? 'bg-forest-100 text-forest-800'
                            : tx.transactionType === 'SALE' || tx.transactionType === 'TRANSFER_OUT'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-cream-200 text-ink-700'
                        }`}>
                          {tx.transactionType}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-semibold text-ink-900">{tx.name || tx.sku}</span>
                        <span className="text-[10px] text-ink-400 font-mono block">{tx.sku}</span>
                      </td>
                      <td className="py-2.5 px-3 font-mono font-medium text-ink-700">{tx.warehouse}</td>
                      <td className="py-2.5 px-3 text-right font-bold">
                        <span className={isNeg ? 'text-brick-600' : 'text-forest-700'}>
                          {isNeg ? `${tx.quantity}` : `+${tx.quantity}`}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center text-ink-500 font-mono">
                        {tx.previousStock} → {tx.newStock}
                      </td>
                      <td className="py-2.5 px-3 text-ink-700 max-w-sm">
                        <div className="flex items-start gap-1">
                          <span className={isExpandedTx ? 'whitespace-normal break-words font-medium' : 'truncate'}>
                            {fullReason}
                          </span>
                          {isLongReason && (
                            <button
                              type="button"
                              onClick={() => toggleTxExpand(tx.id)}
                              className="text-forest-700 hover:text-forest-900 shrink-0 text-[10.5px] font-bold underline cursor-pointer ml-1"
                            >
                              {isExpandedTx ? 'Less' : 'More'}
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-ink-500 text-[11px]">
                        {formattedTimeStr}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Transaction Modal */}
      {txModalOpen && (
        <TransactionModal
          open={txModalOpen}
          onClose={() => setTxModalOpen(false)}
          defaultProduct={selectedProduct}
          onSuccess={() => {
            triggerRefresh();
            loadInventory();
          }}
        />
      )}

      {/* Add Product Modal */}
      {addProductOpen && (
        <AddProductModal
          open={addProductOpen}
          onClose={() => setAddProductOpen(false)}
          onProductAdded={() => {
            triggerRefresh();
            loadInventory();
          }}
        />
      )}

      {/* Record Sale Modal */}
      {recordSaleOpen && (
        <RecordSaleModal
          open={recordSaleOpen}
          onClose={() => setRecordSaleOpen(false)}
          defaultItem={selectedProduct}
          onSaleRecorded={() => {
            triggerRefresh();
            loadInventory();
          }}
        />
      )}
    </div>
  );
}