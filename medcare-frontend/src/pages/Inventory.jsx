import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import React from 'react';
import {
  Search, Plus, Download, Package, Boxes, AlertOctagon, PackageX,
  ArrowRightLeft, History, ChevronDown, ChevronRight,
  Layers, Trash2, HelpCircle, Calendar, Sparkles, Clock, X, Sliders, CheckCircle2, AlertCircle
} from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import TransactionModal from '../components/transactions/TransactionModal';
import AddProductModal from '../components/inventory/AddProductModal';
import EditInventoryModal from '../components/inventory/EditInventoryModal';
import { riskTone, riskLabel } from '../data/riskTone';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';
import { useAuth } from '../context/AuthContext';
import { formatDate, formatDateTime } from '../utils/dateUtils';

const quickFilters = [
  { key: 'all', label: 'All Items', test: () => true },
  {
    key: 'low',
    label: 'Low Stock',
    test: (p) =>
      Boolean(
        p &&
          (p.status === 'Low Stock' ||
            p.status === 'LOW_STOCK' ||
            p.status === 'Critical' ||
            p.status === 'CRITICAL' ||
            p.hasLowStock ||
            p.hasCritical ||
            Number(p.currentStock || 0) <= Number(p.reorderPoint || 0))
      ),
  },
  {
    key: 'out',
    label: 'Stockout / Critical',
    test: (p) =>
      Boolean(
        p &&
          (p.status === 'Out of Stock' ||
            p.status === 'OUT_OF_STOCK' ||
            p.status === 'Critical' ||
            p.status === 'CRITICAL' ||
            p.hasCritical ||
            Number(p.currentStock || 0) <= 0 ||
            Number(p.availableStock || 0) <= 0 ||
            p.risk === 'critical' ||
            (Array.isArray(p.warehouseBreakdown) &&
              p.warehouseBreakdown.some(
                (w) =>
                  w &&
                  (Number(w.currentStock || 0) <= 0 ||
                    w.status === 'Critical' ||
                    w.status === 'Out Of Stock' ||
                    w.status === 'CRITICAL' ||
                    w.status === 'OUT_OF_STOCK')
              )))
      ),
  },
  {
    key: 'expiring',
    label: 'Expiring Soon (<60d)',
    test: (p) =>
      Boolean(
        p &&
          (Number(p.daysToExpiry ?? 999) <= 60 ||
            Number(p.earliestExpiryDays ?? 999) <= 60 ||
            (Array.isArray(p.batches) &&
              p.batches.some((b) => b && Number(b.daysToExpiry ?? 999) <= 60)))
      ),
  },
  {
    key: 'slow',
    label: 'Overstock',
    test: (p) =>
      Boolean(
        p &&
          (p.status === 'OVERSTOCK' ||
            p.status === 'Overstock' ||
            Number(p.currentStock || 0) > Number(p.reorderPoint || 0) * 1.8)
      ),
  },
];

export default function Inventory() {
  const { selectedWarehouse, setSelectedWarehouse, refreshKey, triggerRefresh } = useControlTower();
  const { isAdmin, hasPermission } = useAuth();
  const canAddProduct = isAdmin || hasPermission('inventory.create_product');

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

  // History search and expansion states
  const [txSearch, setTxSearch] = useState('');
  const [txExpanded, setTxExpanded] = useState(false);
  const [txLoading, setTxLoading] = useState(false);

  // Modals State
  const [txModalOpen, setTxModalOpen] = useState(false);
  const [addProductOpen, setAddProductOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [editingItem, setEditingItem] = useState(null);

  // User Action Feedback
  const [actionSuccess, setActionSuccess] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Request tracking to prevent race conditions when rapidly switching filters
  const abortControllerRef = useRef(null);
  const requestIdRef = useRef(0);

  const loadInventory = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    const currentRequestId = ++requestIdRef.current;

    setLoading(true);
    setError(null);
    try {
      const [items, cats, whs] = await Promise.all([
        api.getInventory(
          {
            warehouse: selectedWarehouse,
            category: categoryFilter,
            quick_filter: quickFilter,
            rollup: rollupView && selectedWarehouse === 'All'
          },
          { signal: abortController.signal }
        ),
        api.getCategories({ signal: abortController.signal }),
        api.getWarehouses({ signal: abortController.signal })
      ]);

      if (currentRequestId === requestIdRef.current) {
        setProducts(Array.isArray(items) ? items : []);
        setCategories(Array.isArray(cats) ? cats : []);
        setWarehouses(Array.isArray(whs) ? whs : (whs?.overview || []));
        setLoading(false);
      }
    } catch (err) {
      if (err.name === 'AbortError' || err.message?.includes('aborted') || currentRequestId !== requestIdRef.current) {
        return; // Silently ignore stale or cancelled requests
      }
      console.error('Failed to load inventory:', err);
      setError(err.message || 'Unable to connect to inventory backend service.');
      setLoading(false);
    }
  }, [selectedWarehouse, categoryFilter, quickFilter, rollupView]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const loadTransactions = useCallback(async () => {
    setTxLoading(true);
    try {
      const txs = await api.getTransactions({
        warehouse: selectedWarehouse !== 'All' ? selectedWarehouse : undefined,
        search: txSearch.trim() || undefined,
        limit: txExpanded ? 100 : 10
      });
      setRecentTransactions(Array.isArray(txs) ? txs : []);
    } catch (err) {
      console.warn('Failed to load transactions:', err);
    } finally {
      setTxLoading(false);
    }
  }, [selectedWarehouse, txSearch, txExpanded]);

  useEffect(() => {
    loadInventory();
  }, [loadInventory, refreshKey]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions, refreshKey]);

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

  const lowStockCount = useMemo(() => filtered.filter((p) => {
    const st = (p.status || '').toLowerCase();
    const isLow = st === 'low stock' || p.hasLowStock || p.risk === 'high' ||
      (Array.isArray(p.warehouseBreakdown) && p.warehouseBreakdown.some(w => (w.status || '').toLowerCase() === 'low stock')) ||
      (Number(p.currentStock || 0) < Number(p.reorderPoint || 0) && Number(p.currentStock || 0) >= Number(p.safetyStock || 0) && Number(p.currentStock || 0) > 0);
    const isCrit = st === 'critical' || st === 'out of stock' || p.hasCritical || p.risk === 'critical' ||
      (Array.isArray(p.warehouseBreakdown) && p.warehouseBreakdown.some(w => ['critical', 'out of stock'].includes((w.status || '').toLowerCase())));
    return isLow && !isCrit;
  }).length, [filtered]);

  const outOfStockCount = useMemo(() => filtered.filter((p) => {
    const st = (p.status || '').toLowerCase();
    return st === 'critical' ||
      st === 'out of stock' ||
      p.hasCritical ||
      p.risk === 'critical' ||
      Number(p.currentStock || 0) <= 0 ||
      (Array.isArray(p.warehouseBreakdown) && p.warehouseBreakdown.some(w => ['critical', 'out of stock'].includes((w.status || '').toLowerCase()) || Number(w.currentStock || 0) <= 0));
  }).length, [filtered]);

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

  function handleOpenEditModal(item, targetWh = null) {
    const isAggregateWh = !item.warehouse || ['all', 'all warehouses', 'network', 'network rollup'].includes(String(item.warehouse).toLowerCase());
    const normalizedWh = targetWh || (isAggregateWh
      ? (item.warehouseBreakdown?.[0]?.warehouseId || (selectedWarehouse !== 'All' ? selectedWarehouse : 'MUM-01'))
      : item.warehouse);

    setEditingItem({
      ...item,
      warehouse: normalizedWh,
      warehouseId: normalizedWh
    });
    setEditModalOpen(true);
  }

  function toggleSkuExpand(sku) {
    setExpandedSkus((prev) => ({ ...prev, [sku]: !prev[sku] }));
  }

  function toggleTxExpand(txId) {
    setExpandedTxIds((prev) => ({ ...prev, [txId]: !prev[txId] }));
  }

  async function handleDeleteWarehouseInventory(sku, warehouseId, productName) {
    if (!warehouseId || ['all', 'all warehouses', 'network', 'network rollup'].includes(String(warehouseId).toLowerCase())) {
      alert("Please expand and select a specific warehouse location to remove its inventory tracking.");
      return;
    }
    if (window.confirm(`Are you sure you want to remove the inventory tracking and local batches for "${productName}" (${sku}) in warehouse ${warehouseId}?\n\nNote: The master product will remain in the catalog.`)) {
      try {
        const res = await api.deleteWarehouseInventory(warehouseId, sku);
        setActionSuccess(res.message || `Inventory tracking for ${sku} in ${warehouseId} removed from database.`);
        triggerRefresh();
        await loadInventory();
        setTimeout(() => setActionSuccess(null), 3000);
      } catch (err) {
        setActionError(`Failed to delete warehouse inventory: ${err.message}`);
        setTimeout(() => setActionError(null), 4000);
      }
    }
  }

  async function handleDeleteProduct(sku, name) {
    if (window.confirm(`Are you sure you want to delete product "${name}" (${sku}) from the master catalog? All associated warehouse inventory, batches, transactions, and alerts across all distribution centers will be permanently removed.`)) {
      try {
        await api.deleteProduct(sku);
        setActionSuccess(`Product "${name}" (${sku}) permanently deleted from master database.`);
        triggerRefresh();
        await loadInventory();
        setTimeout(() => setActionSuccess(null), 3000);
      } catch (err) {
        setActionError(`Failed to delete product: ${err.message}`);
        setTimeout(() => setActionError(null), 4000);
      }
    }
  }

  function exportCSV() {
    if (!filtered.length) return;
    const headers = ['SKU', 'Name', 'Category', 'Warehouse', 'Current Stock', 'Reorder Point', 'Safety Stock', 'Unit Cost', 'Days of Cover', 'Status'];
    const rows = filtered.map(p => [
      p.sku,
      `"${p.name}"`,
      p.category,
      p.warehouse,
      p.currentStock,
      p.reorderPoint,
      p.safetyStock || 0,
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
      {/* Action Notification Banners */}
      {actionSuccess && (
        <div className="p-3 bg-forest-100 border border-forest-600/30 text-forest-800 rounded-md font-semibold text-[13px] flex items-center gap-2 animate-fadeIn">
          <CheckCircle2 size={16} className="shrink-0 text-forest-700" />
          <span>{actionSuccess}</span>
        </div>
      )}
      {actionError && (
        <div className="p-3 bg-brick-100 border border-brick-600/30 text-brick-700 rounded-md font-semibold text-[13px] flex items-center gap-2 animate-fadeIn">
          <AlertCircle size={16} className="shrink-0 text-brick-600" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3.5 rounded-lg border border-ink-100 shadow-card">
        <div>
          <h2 className="text-[16px] font-bold text-ink-900">Inventory Management & Warehouse Settings</h2>
          <p className="text-[12px] text-ink-500">Warehouse-specific Reorder Points (ROP), Safety Stock buffers, live FEFO batches, and stock configuration.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => handleOpenTxModal()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-forest-800 text-white rounded-md text-[12.5px] font-semibold hover:bg-forest-700 transition-colors shadow-xs cursor-pointer"
            title="Record Stock Receipt, Sale, Adjustment, or Inter-DC Transfer"
          >
            <Plus size={14} /> Record Stock Tx
          </button>
          {canAddProduct && (
            <button
              onClick={() => setAddProductOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-ink-200 text-ink-700 rounded-md text-[12.5px] font-medium hover:bg-cream-200 transition-colors cursor-pointer"
            >
              <Package size={14} /> Add Product
            </button>
          )}
          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-ink-200 text-ink-700 rounded-md text-[12.5px] font-medium hover:bg-cream-200 transition-colors cursor-pointer"
            title="Export filtered inventory dataset to CSV"
          >
            <Download size={14} /> Export CSV
          </button>
        </div>
      </div>

      {/* Dynamic Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard
          label="Total Inventory Units"
          value={totalUnits.toLocaleString()}
          subtext={`Across ${warehouses.length} Active DCs`}
          icon={Boxes}
          tone="neutral"
          onClick={() => setQuickFilter('all')}
        />
        <StatCard
          label="Active SKU Count"
          value={filtered.length}
          subtext={`${categories.length} Categories Tracked`}
          icon={Package}
          tone="good"
          onClick={() => setQuickFilter('all')}
        />
        <StatCard
          label="Low Stock SKUs"
          value={lowStockCount}
          subtext="Below Reorder Point (ROP)"
          icon={AlertOctagon}
          tone={lowStockCount > 0 ? 'warning' : 'good'}
          onClick={() => setQuickFilter('low')}
        />
        <StatCard
          label="Stockout / Critical"
          value={outOfStockCount}
          subtext="Below Safety Stock / Stockout"
          icon={PackageX}
          tone={outOfStockCount > 0 ? 'critical' : 'good'}
          onClick={() => setQuickFilter('out')}
        />
      </div>

      {/* Filters and Search Bar */}
      <div className="bg-white p-3.5 rounded-lg border border-ink-100 shadow-card space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1 max-w-md">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
            <input
              type="text"
              placeholder="Search by SKU, Molecule Name, or Category..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 border border-ink-200 rounded-md text-[12.5px] focus:outline-none focus:ring-1 focus:ring-forest-600 bg-cream-100/40"
            />
          </div>

          {/* Filters Row */}
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Category Filter */}
            <div className="flex items-center gap-1.5 text-[12px]">
              <span className="text-ink-500 font-medium">Category:</span>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="border border-ink-200 rounded px-2.5 py-1 text-[12px] text-ink-800 bg-white focus:outline-none focus:ring-1 focus:ring-forest-600"
              >
                <option value="All">All Categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Warehouse Filter */}
            <div className="flex items-center gap-1.5 text-[12px]">
              <span className="text-ink-500 font-medium">DC Scope:</span>
              <select
                value={selectedWarehouse}
                onChange={(e) => setSelectedWarehouse(e.target.value)}
                className="border border-ink-200 rounded px-2.5 py-1 text-[12px] text-ink-800 bg-white focus:outline-none focus:ring-1 focus:ring-forest-600 font-mono"
              >
                <option value="All">All Warehouses (Network)</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
                ))}
              </select>
            </div>

            {/* Aggregate Rollup Switch */}
            {selectedWarehouse === 'All' && (
              <label className="flex items-center gap-1.5 text-[12px] text-ink-700 font-medium cursor-pointer ml-1 select-none">
                <input
                  type="checkbox"
                  checked={rollupView}
                  onChange={(e) => setRollupView(e.target.checked)}
                  className="rounded text-forest-700 focus:ring-forest-600 cursor-pointer"
                />
                <span>Rollup View</span>
              </label>
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

      {/* Inventory Items Table */}
      {loading ? (
        <LoadingState message="Loading live inventory records from Database..." />
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
                  <th className="py-3 px-3 text-left w-24">Category</th>
                  <th className="py-3 px-3 text-left w-28">{isRollupMode ? 'Warehouse Scope' : 'DC Location'}</th>
                  <th className="py-3 px-3 text-right w-24">Total Stock</th>
                  {!isRollupMode && (
                    <>
                      <th className="py-3 px-3 text-right w-24">Reorder Point</th>
                      <th className="py-3 px-3 text-right w-24">Safety Stock</th>
                      <th className="py-3 px-3 text-right w-24">Price (INR)</th>
                      <th className="py-3 px-3 text-right w-20">Days Cover</th>
                    </>
                  )}
                  <th className="py-3 px-3 text-center w-24">Health Status</th>
                  <th className="py-3 px-3 text-right w-36">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {filtered.map((item, idx) => {
                  const currentStock = Number(item.currentStock || 0);
                  const reorderPoint = Number(item.reorderPoint || 0);
                  const safetyStock = Number(item.safetyStock || 0);
                  const daysCover = Number(item.daysOfCover || 0);
                  const unitCost = Number(item.unitCost || item.price || 0);
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
                        {!isRollupMode && (
                          <>
                            <td className="py-3 px-3 text-right align-middle text-ink-600 font-mono">
                              {reorderPoint.toLocaleString()}
                            </td>
                            <td className="py-3 px-3 text-right align-middle text-ink-600 font-mono">
                              {safetyStock.toLocaleString()}
                            </td>
                            <td className="py-3 px-3 text-right align-middle font-semibold text-ink-900">
                              ₹{unitCost.toFixed(2)}
                            </td>
                            <td className="py-3 px-3 text-right align-middle">
                              <span className={`font-semibold ${daysCover <= 5 ? 'text-brick-600' : daysCover <= 12 ? 'text-amber-600' : 'text-forest-700'}`}>
                                {daysCover.toFixed(1)}d
                              </span>
                            </td>
                          </>
                        )}
                        <td className="py-3 px-3 text-center align-middle">
                          <Badge tone={riskTone[item.risk] || (item.status === 'Healthy' ? 'good' : item.status === 'Low Stock' ? 'warning' : 'critical')}>
                            {item.status || riskLabel[item.risk] || 'Active'}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-right align-middle">
                          <div className="flex items-center justify-end gap-1.5">
                            {!isRollupMode && (
                              <button
                                onClick={() => handleOpenEditModal(item)}
                                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded border border-ink-200 text-ink-700 hover:bg-forest-50 hover:text-forest-700 hover:border-forest-600 transition-colors cursor-pointer shadow-xs"
                                title="Edit Warehouse Settings (ROP, Safety Stock, Price)"
                              >
                                <Sliders size={12} /> Edit
                              </button>
                            )}
                            <button
                              onClick={() => handleOpenTxModal(item)}
                              className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded border border-ink-200 text-ink-700 hover:bg-forest-50 hover:text-forest-700 hover:border-forest-600 transition-colors cursor-pointer shadow-xs"
                              title="Record Stock Transaction"
                            >
                              <Plus size={12} /> Stock Tx
                            </button>
                            {selectedWarehouse !== 'All' ? (
                              <button
                                onClick={() => handleDeleteWarehouseInventory(item.sku, item.warehouse, item.name)}
                                className="inline-flex items-center gap-1 p-1 text-[11px] font-medium rounded border border-brick-600/30 text-brick-700 hover:bg-brick-100 transition-colors cursor-pointer"
                                title="Delete Warehouse Inventory Tracking"
                              >
                                <Trash2 size={13} />
                              </button>
                            ) : (
                              <button
                                onClick={() => handleDeleteProduct(item.sku, item.name)}
                                className="inline-flex items-center gap-1 p-1 text-[11px] font-medium rounded border border-brick-600/30 text-brick-700 hover:bg-brick-100 transition-colors cursor-pointer"
                                title="Permanently Delete Product Catalog Master Record"
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Collapsible Per-DC & Batch Breakdown View */}
                      {isExpanded && (
                        <tr className="bg-cream-100/40">
                          <td colSpan={isRollupMode ? 7 : 10} className="p-0">
                            <div className="border-t border-b border-ink-100/80 px-6 py-4 space-y-4 animate-fadeIn">
                              {/* 1. Regional DC Breakdown Table */}
                              {hasBreakdown && (
                                <div className="space-y-2">
                                  <div className="text-[12px] font-bold text-ink-800 flex items-center justify-between">
                                    <span className="flex items-center gap-1.5">
                                      <Layers size={14} className="text-forest-700" />
                                      <span>Regional DC Breakdown & Warehouse Settings for {item.name} ({item.sku}):</span>
                                    </span>
                                    <span className="text-[11px] text-ink-400 font-normal">
                                      {item.warehouseBreakdown.length} warehouses configured
                                    </span>
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
                                        <th className="py-2 px-3 text-right">Reorder Point (ROP)</th>
                                        <th className="py-2 px-3 text-right">Safety Stock</th>
                                        <th className="py-2 px-3 text-right">Unit Price</th>
                                        <th className="py-2 px-3 text-right">Days of Cover</th>
                                        <th className="py-2 px-3 text-center">Status</th>
                                        <th className="py-2 px-3 text-right">Actions</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-ink-100">
                                      {item.warehouseBreakdown.map((wb, wIdx) => (
                                        <tr key={wIdx} className="hover:bg-cream-100/50">
                                          <td className="py-2 px-3 font-mono font-bold text-ink-800">{wb.warehouseId}</td>
                                          <td className="py-2 px-3 text-right font-bold text-ink-900">{Number(wb.currentStock).toLocaleString()}</td>
                                          <td className="py-2 px-3 text-right text-ink-600 font-mono">{Number(wb.reorderPoint).toLocaleString()}</td>
                                          <td className="py-2 px-3 text-right text-ink-600 font-mono">{Number(wb.safetyStock || 0).toLocaleString()}</td>
                                          <td className="py-2 px-3 text-right font-semibold text-ink-800">₹{Number(wb.unitCost || item.unitCost || 0).toFixed(2)}</td>
                                          <td className="py-2 px-3 text-right font-semibold text-forest-700">{Number(wb.daysOfCover).toFixed(1)}d</td>
                                          <td className="py-2 px-3 text-center">
                                            <Badge tone={riskTone[wb.risk] || 'good'}>{wb.status}</Badge>
                                          </td>
                                          <td className="py-2 px-3 text-right">
                                            <div className="flex items-center justify-end gap-2">
                                              <button
                                                onClick={() => handleOpenEditModal({
                                                  sku: item.sku,
                                                  name: item.name,
                                                  category: item.category,
                                                  warehouse: wb.warehouseId,
                                                  warehouseId: wb.warehouseId,
                                                  reorderPoint: wb.reorderPoint,
                                                  safetyStock: wb.safetyStock,
                                                  currentStock: wb.currentStock,
                                                  unitCost: wb.unitCost || item.unitCost,
                                                  moq: wb.moq || item.moq,
                                                  unit: item.unit
                                                })}
                                                className="text-forest-700 hover:text-forest-900 hover:underline text-[11px] font-semibold cursor-pointer inline-flex items-center gap-0.5"
                                                title="Edit warehouse settings"
                                              >
                                                <Sliders size={11} /> Edit
                                              </button>
                                              <button
                                                onClick={() => handleOpenTxModal({ sku: item.sku, warehouse: wb.warehouseId, currentStock: wb.currentStock })}
                                                className="text-forest-700 hover:text-forest-900 hover:underline text-[11px] font-semibold cursor-pointer"
                                              >
                                                + Transact
                                              </button>
                                              <button
                                                onClick={() => handleDeleteWarehouseInventory(item.sku, wb.warehouseId, item.name)}
                                                className="text-brick-600 hover:text-brick-800 hover:underline text-[11px] font-semibold cursor-pointer inline-flex items-center gap-0.5"
                                                title="Delete warehouse tracking"
                                              >
                                                <Trash2 size={11} /> Delete
                                              </button>
                                            </div>
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              )}

                              {/* 2. Live Database Batch Expiry Details */}
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
                                            <td className="py-2 px-3 font-medium text-ink-800">{formatDate(b.expiryDate)}</td>
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

      {/* Historical Inventory Audit Trail */}
      <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-ink-100 pb-3">
          <div>
            <h3 className="text-[15px] font-bold text-ink-900 flex items-center gap-1.5">
              <History size={16} className="text-forest-700" /> Historical Stock Transactions Audit Trail
            </h3>
            <p className="text-[11.5px] text-ink-500">Live database audit log of physical receipts, sales dispatch, and stock adjustments.</p>
          </div>

          <div className="flex items-center gap-2">
            {/* Search Input for Transactions */}
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-400" />
              <input
                type="text"
                placeholder="Search transactions..."
                value={txSearch}
                onChange={(e) => setTxSearch(e.target.value)}
                className="pl-7 pr-7 py-1 text-[11.5px] border border-ink-200 rounded focus:outline-none focus:ring-1 focus:ring-forest-600 w-44 sm:w-56 bg-cream-100/30"
              />
              {txSearch && (
                <button
                  type="button"
                  onClick={() => setTxSearch('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700 p-0.5 cursor-pointer"
                  title="Clear search"
                >
                  <X size={12} />
                </button>
              )}
            </div>

            {/* Expand / View More Toggle Button */}
            <button
              onClick={() => setTxExpanded(!txExpanded)}
              className="px-2.5 py-1 text-[11.5px] font-medium border border-ink-200 rounded hover:bg-cream-200 text-ink-700 transition-colors cursor-pointer"
            >
              {txExpanded ? 'Show Latest 10' : 'View More (100 Records)'}
            </button>
          </div>
        </div>

        {txLoading ? (
          <div className="py-4 text-center text-ink-400 text-[12px] animate-pulse">Loading transaction records from Database...</div>
        ) : recentTransactions.length === 0 ? (
          <p className="text-[12px] text-ink-400 py-3 text-center">
            {txSearch ? `No historical transactions match "${txSearch}".` : 'No transactions recorded yet in Database.'}
          </p>
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

                  const formattedTimeStr = tx.formattedTime || formatDateTime(tx.timestamp);

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

      {/* Edit Warehouse Inventory Modal */}
      {editModalOpen && editingItem && (
        <EditInventoryModal
          open={editModalOpen}
          onClose={() => {
            setEditModalOpen(false);
            setEditingItem(null);
          }}
          item={editingItem}
          onSaved={() => {
            triggerRefresh();
            loadInventory();
          }}
        />
      )}

      {/* Transaction Modal */}
      {txModalOpen && (
        <TransactionModal
          open={txModalOpen}
          onClose={() => setTxModalOpen(false)}
          defaultProduct={selectedProduct}
          onSuccess={() => {
            triggerRefresh();
            loadInventory();
            loadTransactions();
          }}
        />
      )}

      {/* Add Product Modal (Admin Only) */}
      {canAddProduct && addProductOpen && (
        <AddProductModal
          open={addProductOpen}
          onClose={() => setAddProductOpen(false)}
          onProductAdded={() => {
            triggerRefresh();
            loadInventory();
            loadTransactions();
          }}
        />
      )}
    </div>
  );
}