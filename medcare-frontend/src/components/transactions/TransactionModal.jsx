import { useState, useEffect } from 'react';
import { ShoppingCart, PackagePlus, ArrowRightLeft, SlidersHorizontal, AlertCircle, CheckCircle2, FlaskConical } from 'lucide-react';
import Modal from '../ui/Modal';
import { api } from '../../api/client';

const TRANSACTION_TYPES = [
  { id: 'SALE', label: 'Sale (Outbound)', icon: ShoppingCart, desc: 'Deducts stock for hospital/distributor sale via strict FEFO allocation' },
  { id: 'RECEIPT', label: 'Stock Receipt (Inbound)', icon: PackagePlus, desc: 'Receive newly manufactured supplier batch into DC inventory' },
  { id: 'ADJUSTMENT', label: 'Audit Adjustment', icon: SlidersHorizontal, desc: 'Record physical inventory count discrepancies or shrinkage' },
  { id: 'TRANSFER_OUT', label: 'Inter-DC Transfer', icon: ArrowRightLeft, desc: 'Rebalance surplus inventory from one DC to another' },
  { id: 'CONSUMPTION', label: 'Internal Consumption', icon: FlaskConical, desc: 'Clinical trials, QA destructive testing, or hospital dispensing' },
];

function resolveValidWarehouseId(whValue, defaultObj, availableList, fallback = 'MUM-01') {
  const invalidStrings = ['all', 'all warehouses', 'network', 'network rollup', 'all_dcs', 'null', 'undefined', ''];
  
  // 1. Check direct passed value
  if (whValue && !invalidStrings.includes(String(whValue).trim().toLowerCase())) {
    return whValue;
  }
  // 2. Check defaultObj breakdown if rollup
  if (defaultObj?.warehouseBreakdown && defaultObj.warehouseBreakdown.length > 0) {
    const firstWb = defaultObj.warehouseBreakdown[0].warehouseId;
    if (firstWb && !invalidStrings.includes(String(firstWb).trim().toLowerCase())) {
      return firstWb;
    }
  }
  // 3. Check defaultObj warehouse_id / warehouse
  const objWh = defaultObj?.warehouse_id || defaultObj?.warehouse;
  if (objWh && !invalidStrings.includes(String(objWh).trim().toLowerCase())) {
    return objWh;
  }
  // 4. Use first available DC from loaded list
  if (availableList && availableList.length > 0) {
    return availableList[0].id;
  }
  return fallback;
}

export default function TransactionModal({
  open,
  isOpen,
  onClose,
  onTransactionSuccess,
  onSuccess,
  defaultProduct,
  initialSku,
  initialWarehouse,
  currentStock = 0
}) {
  const isModalOpen = open !== undefined ? open : isOpen;
  const initialSkuVal = initialSku || defaultProduct?.sku || 'P-1065';
  const initialWhVal = resolveValidWarehouseId(initialWarehouse, defaultProduct, [], 'MUM-01');
  const initStockVal = currentStock || Number(defaultProduct?.currentStock || defaultProduct?.current_stock || 0);
  const initCostVal = defaultProduct?.unitCost || defaultProduct?.unit_cost || 25.0;

  const [type, setType] = useState('SALE');
  const [sku, setSku] = useState(initialSkuVal);
  const [warehouse, setWarehouse] = useState(initialWhVal);
  const [quantity, setQuantity] = useState(250);
  const [warehouses, setWarehouses] = useState([]);
  const [liveStock, setLiveStock] = useState(initStockVal);
  const [availableBatches, setAvailableBatches] = useState([]);
  const [dbUnitCost, setDbUnitCost] = useState(Number(initCostVal));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Type-specific field states
  // Sale
  const [customerName, setCustomerName] = useState('Apollo Hospitals Mumbai');
  const [salesChannel, setSalesChannel] = useState('Hospital');
  const [unitPrice, setUnitPrice] = useState(Number(initCostVal));

  // Receipt
  const [supplierName, setSupplierName] = useState('HealthGen Pharma');
  const [suppliersList, setSuppliersList] = useState([]);
  const [poNumber, setPoNumber] = useState('PO-8845');
  const [batchId, setBatchId] = useState('');
  const [expiryDate, setExpiryDate] = useState(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() + 2);
    return d.toISOString().split('T')[0];
  });
  const [unitCost, setUnitCost] = useState(Number(initCostVal));

  // Adjustment
  const [actualPhysicalCount, setActualPhysicalCount] = useState(initStockVal);
  const [adjustmentReason, setAdjustmentReason] = useState('Physical Cycle Count Discrepancy');
  const [auditorName, setAuditorName] = useState('QA Audit Officer');

  // Transfer
  const [destinationWarehouse, setDestinationWarehouse] = useState('PAT-01');
  const [transferReason, setTransferReason] = useState('Regional Surge Balancing & FEFO Optimization');
  const [transitDays, setTransitDays] = useState(3);

  // Consumption
  const [department, setDepartment] = useState('Emergency Clinical Ward');
  const [consumptionReason, setConsumptionReason] = useState('Routine Hospital Inpatient Dispensing');

  // Initial metadata loading (Warehouses & Suppliers)
  useEffect(() => {
    async function loadData() {
      try {
        const [whs, supps] = await Promise.all([
          api.getWarehouses(),
          api.getSuppliers()
        ]);
        const list = Array.isArray(whs) ? whs : (whs?.overview || []);
        setWarehouses(list);
        if (list.length > 0) {
          setWarehouse((prev) => resolveValidWarehouseId(prev, defaultProduct, list));
          const otherDcs = list.filter(w => w.id !== warehouse);
          if (otherDcs.length > 0) {
            setDestinationWarehouse(otherDcs[0].id);
          }
        }
        const sList = Array.isArray(supps) ? supps : [];
        setSuppliersList(sList);
        if (sList.length > 0) {
          setSupplierName((prev) => {
            if (prev && sList.some(s => s.name === prev)) return prev;
            return sList[0].name;
          });
        }
      } catch (err) {
        console.warn('Failed to load metadata for modal:', err);
      }
    }
    loadData();
  }, []);

  // Update default states when defaultProduct prop changes
  useEffect(() => {
    if (defaultProduct) {
      if (defaultProduct.sku) setSku(defaultProduct.sku);
      const validWh = resolveValidWarehouseId(defaultProduct.warehouse_id || defaultProduct.warehouse, defaultProduct, warehouses);
      setWarehouse(validWh);
      const st = Number(defaultProduct.currentStock || defaultProduct.current_stock || 0);
      setLiveStock(st);
      setActualPhysicalCount(st);
      const cost = defaultProduct.unitCost || defaultProduct.unit_cost;
      if (cost !== undefined && cost !== null) {
        const numCost = Number(cost);
        setDbUnitCost(numCost);
        setUnitCost(numCost);
        setUnitPrice(numCost);
      }
    }
  }, [defaultProduct, warehouses]);

  // Live stock & unit cost recalculation from DB whenever SKU or Warehouse changes
  useEffect(() => {
    let isMounted = true;
    async function fetchStockForSelection() {
      const cleanSku = String(sku || '').trim().toUpperCase();
      const cleanWh = String(warehouse || '').trim();
      if (!cleanSku || !cleanWh || ['all', 'all warehouses', 'network', 'network rollup', 'all_dcs'].includes(cleanWh.toLowerCase())) {
        return;
      }

      // Fast synchronous lookup if defaultProduct has pre-fetched warehouseBreakdown
      if (defaultProduct?.warehouseBreakdown && Array.isArray(defaultProduct.warehouseBreakdown)) {
        const wbMatch = defaultProduct.warehouseBreakdown.find(
          (wb) => String(wb.warehouseId || wb.warehouse).toUpperCase() === cleanWh.toUpperCase()
        );
        if (wbMatch && isMounted) {
          const st = Number(wbMatch.currentStock ?? wbMatch.current_stock ?? 0);
          setLiveStock(st);
          setActualPhysicalCount(st);
        }
      }

      // Live database query for guaranteed Database state
      try {
        const invRes = await api.getInventory({ warehouse: cleanWh, search: cleanSku });
        if (!isMounted) return;
        const items = Array.isArray(invRes) ? invRes : (invRes?.items || []);
        const matched = items.find(
          (i) => i.sku?.toUpperCase() === cleanSku && (i.warehouse === cleanWh || i.warehouse_id === cleanWh)
        ) || items.find((i) => i.sku?.toUpperCase() === cleanSku);

        if (matched && isMounted) {
          const stockVal = Number(matched.currentStock ?? matched.current_stock ?? 0);
          setLiveStock(stockVal);
          setActualPhysicalCount(stockVal);
          const cost = matched.unitCost ?? matched.unit_cost;
          if (cost !== undefined && cost !== null) {
            const numCost = Number(cost);
            setDbUnitCost(numCost);
            setUnitCost((prev) => (prev === '' || prev === null || isNaN(Number(prev)) ? numCost : prev));
            setUnitPrice((prev) => (prev === '' || prev === null || isNaN(Number(prev)) ? numCost : prev));
          }
        } else if (isMounted && items.length === 0) {
          setLiveStock(0);
          setActualPhysicalCount(0);
        }

        // Also fetch live batches in FEFO order for this SKU + Warehouse
        try {
          const bList = await api.getBatches({ sku: cleanSku, warehouse: cleanWh });
          if (isMounted) {
            setAvailableBatches(Array.isArray(bList) ? bList.filter(b => b.quantity > 0) : []);
          }
        } catch {
          if (isMounted) setAvailableBatches([]);
        }
      } catch (err) {
        console.warn('Failed to fetch live stock for warehouse selection:', err);
      }
    }

    fetchStockForSelection();
    return () => {
      isMounted = false;
    };
  }, [sku, warehouse, defaultProduct]);

  // Adjustments calculate variance delta
  const isAdjustment = type === 'ADJUSTMENT';
  const adjustmentDelta = isAdjustment ? Number(actualPhysicalCount) - Number(liveStock) : 0;

  const isDeduction = ['SALE', 'CONSUMPTION', 'TRANSFER_OUT'].includes(type) || (isAdjustment && adjustmentDelta < 0);
  
  let projectedStock = liveStock;
  if (isAdjustment) {
    projectedStock = Math.max(0, Number(actualPhysicalCount));
  } else if (isDeduction) {
    projectedStock = Math.max(0, liveStock - Number(quantity || 0));
  } else {
    projectedStock = liveStock + Number(quantity || 0);
  }

  // Bug 1: Only display Total Cost / Total Valuation for Inbound (RECEIPT), Outbound (SALE, CONSUMPTION), and Inter-DC Transfer (TRANSFER_OUT)
  const showTotalCost = ['RECEIPT', 'SALE', 'CONSUMPTION', 'TRANSFER_OUT'].includes(type);

  // Bug 3: Reactive active unit cost directly bound to user input (falling back to database default if empty/invalid)
  const activeUnitCost = type === 'SALE'
    ? (unitPrice !== '' && !isNaN(Number(unitPrice)) ? Number(unitPrice) : Number(dbUnitCost || unitCost || 0))
    : (unitCost !== '' && !isNaN(Number(unitCost)) ? Number(unitCost) : Number(dbUnitCost || 0));

  const activeQuantity = Number(quantity || 0);
  const totalValuation = activeUnitCost * activeQuantity;

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Strict Frontend Warehouse Validation
    const cleanWh = String(warehouse || '').trim();
    if (!cleanWh || ['all', 'all warehouses', 'network', 'network rollup', 'all_dcs'].includes(cleanWh.toLowerCase())) {
      setError('Please select a specific, real distribution center warehouse (e.g. MUM-01, DEL-02, PAT-01).');
      return;
    }

    if (type === 'TRANSFER_OUT') {
      const cleanDest = String(destinationWarehouse || '').trim();
      if (!cleanDest || ['all', 'all warehouses', 'network', 'network rollup'].includes(cleanDest.toLowerCase())) {
        setError('Please select a valid destination warehouse.');
        return;
      }
      if (cleanDest === cleanWh) {
        setError('Destination warehouse cannot be the same as the source warehouse.');
        return;
      }
    }

    setLoading(true);

    try {
      let payload = {
        transaction_type: type,
        sku: sku.trim().toUpperCase(),
        warehouse_id: cleanWh,
        performed_by: auditorName || 'Supply Chain Planner'
      };

      if (type === 'SALE') {
        payload.quantity = Number(quantity);
        payload.reference_id = `SO-${Date.now().toString().slice(-6)}`;
        payload.reason = `Sale to ${customerName} (${salesChannel}) @ ₹${activeUnitCost}/unit`;
      } else if (type === 'RECEIPT') {
        payload.quantity = Number(quantity);
        payload.batch_id = batchId || `BAT-${sku.toUpperCase()}-${cleanWh}-${Date.now().toString().slice(-4)}`;
        payload.expiry_date = expiryDate;
        payload.unit_cost = Number(activeUnitCost);
        payload.supplier_name = supplierName;
        payload.reference_id = poNumber;
        payload.reason = `Inbound Receipt from ${supplierName} (PO: ${poNumber}, Rate: ₹${activeUnitCost}, Exp: ${expiryDate})`;
      } else if (type === 'ADJUSTMENT') {
        payload.quantity = adjustmentDelta;
        payload.reference_id = `AUDIT-${Date.now().toString().slice(-6)}`;
        payload.reason = `Physical Audit: ${adjustmentReason} (Variance: ${adjustmentDelta >= 0 ? `+${adjustmentDelta}` : adjustmentDelta} units)`;
      } else if (type === 'TRANSFER_OUT') {
        payload.transaction_type = 'TRANSFER';
        payload.quantity = Number(quantity);
        payload.warehouse_id = cleanWh;
        payload.destination_warehouse_id = destinationWarehouse;
        payload.reference_id = `TRF-${sku.toUpperCase()}-${cleanWh}-${destinationWarehouse}`;
        payload.reason = `Inter-DC Transfer from ${cleanWh} to ${destinationWarehouse}: ${transferReason} (Rate: ₹${activeUnitCost}, ETA: ${transitDays}d)`;
      } else if (type === 'CONSUMPTION') {
        payload.quantity = Number(quantity);
        payload.reference_id = `CON-${Date.now().toString().slice(-6)}`;
        payload.reason = `Internal Consumption by ${department}: ${consumptionReason} (Valuation: ₹${activeUnitCost}/unit)`;
      }

      const res = await api.createTransaction(payload);

      setSuccess(res.message || 'Transaction executed successfully and recorded in Database audit trail!');
      if (onTransactionSuccess) onTransactionSuccess(res);
      if (onSuccess) onSuccess(res);

      setTimeout(() => {
        setSuccess(null);
        if (onClose) onClose();
      }, 1400);
    } catch (err) {
      setError(err.message || 'Transaction execution failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={Boolean(isModalOpen)} onClose={onClose} title="Execute Inventory Transaction">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Transaction Type Tabs */}
        <div>
          <label className="text-[11px] font-semibold text-ink-600 block mb-1.5 uppercase tracking-wide">
            Select Operation Type
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {TRANSACTION_TYPES.map((t) => {
              const Icon = t.icon;
              const isSelected = type === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setType(t.id)}
                  className={`flex items-center gap-2 p-2 rounded-md border text-left transition-colors cursor-pointer ${
                    isSelected
                      ? 'border-forest-600 bg-forest-100/60 text-forest-900 font-bold shadow-xs'
                      : 'border-ink-100 hover:bg-cream-200 text-ink-700 font-medium'
                  }`}
                >
                  <Icon size={14} className={isSelected ? 'text-forest-700' : 'text-ink-500'} />
                  <span className="text-[11.5px] leading-tight">{t.label}</span>
                </button>
              );
            })}
          </div>
          <p className="text-[11px] text-ink-500 mt-1 italic">
            {TRANSACTION_TYPES.find((t) => t.id === type)?.desc}
          </p>
        </div>

        {/* Universal SKU, Warehouse & Supplier Selectors */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 bg-cream-100/60 rounded-md border border-ink-100">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Product SKU</label>
            <input
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              placeholder="e.g. P-1065"
              className="w-full text-[12.5px] font-mono font-bold border border-ink-200 rounded px-2.5 py-1.5 focus:outline-none focus:border-forest-600 uppercase bg-white"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">
              {type === 'TRANSFER_OUT' ? 'Source Warehouse (From)' : 'Target Warehouse (DC)'}
            </label>
            <select
              value={warehouse}
              onChange={(e) => setWarehouse(e.target.value)}
              className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 text-ink-800 font-medium focus:outline-none focus:border-forest-600 bg-white"
              required
            >
              {warehouses.length > 0 ? (
                warehouses.map((w) => (
                  <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
                ))
              ) : (
                <>
                  <option value="MUM-01">Mumbai Central DC (MUM-01)</option>
                  <option value="DEL-02">Delhi NCR DC (DEL-02)</option>
                  <option value="PAT-01">Patna Regional DC (PAT-01)</option>
                  <option value="BLR-01">Bengaluru South DC (BLR-01)</option>
                  <option value="HYD-01">Hyderabad Regional DC (HYD-01)</option>
                </>
              )}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Supplier / Vendor</label>
            <select
              value={supplierName}
              onChange={(e) => setSupplierName(e.target.value)}
              className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 text-ink-800 font-medium focus:outline-none focus:border-forest-600 bg-white"
            >
              {suppliersList.length > 0 ? (
                suppliersList.map((s) => (
                  <option key={s.id || s.name} value={s.name}>{s.name}</option>
                ))
              ) : (
                <>
                  <option value="Sun Pharma Labs">Sun Pharma Labs</option>
                  <option value="Cipla Healthcare">Cipla Healthcare</option>
                  <option value="Dr. Reddy's Laboratories">Dr. Reddy's Laboratories</option>
                  <option value="Lupin Pharmaceuticals">Lupin Pharmaceuticals</option>
                  <option value="Biocon Biologics">Biocon Biologics</option>
                </>
              )}
            </select>
          </div>
        </div>

        {/* 1. SALE (OUTBOUND) SPECIFIC FIELDS */}
        {type === 'SALE' && (
          <div className="space-y-3 p-3 bg-forest-100/30 rounded-md border border-forest-600/20">
            <span className="text-[11px] font-bold text-forest-800 uppercase block">Outbound Sales Order Details</span>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Customer / Hospital Name</label>
                <input
                  type="text"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="e.g. Apollo Hospitals Mumbai"
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Sales Channel</label>
                <select
                  value={salesChannel}
                  onChange={(e) => setSalesChannel(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white text-ink-800 font-medium focus:outline-none focus:border-forest-600"
                >
                  <option value="Hospital">Hospital Network</option>
                  <option value="Retail Pharmacy">Retail Pharmacy Chain</option>
                  <option value="Distributor">Regional Wholesaler</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Quantity to Dispatch (Units)</label>
                <input
                  type="number"
                  min="1"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full text-[13px] font-bold border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600 text-forest-900"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Selling Price / Unit (₹)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={unitPrice}
                  onChange={(e) => setUnitPrice(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                />
              </div>
            </div>
            <div className="text-[11.5px] text-forest-900 bg-forest-100/70 p-2.5 rounded border border-forest-600/30 space-y-1.5">
              <div className="flex items-center justify-between font-bold">
                <span className="flex items-center gap-1">⚡ Strict FEFO Dispatch Queue:</span>
                <span className="text-[10px] bg-forest-200 text-forest-900 px-1.5 py-0.5 rounded font-mono">Earliest Expiry First</span>
              </div>
              {availableBatches.length > 0 ? (
                <div className="space-y-1 pt-0.5">
                  {availableBatches.slice(0, 3).map((b, idx) => (
                    <div key={b.id} className="flex items-center justify-between font-mono text-[11px] bg-white/70 px-2 py-1 rounded border border-forest-600/15">
                      <span className="font-semibold text-ink-800">{idx + 1}. {b.id} ({Number(b.quantity).toLocaleString()} units)</span>
                      <span className={`px-1.5 py-0.2 rounded font-semibold ${
                        b.daysToExpiry <= 30
                          ? 'bg-brick-100 text-brick-700'
                          : b.daysToExpiry <= 90
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-cream-200 text-forest-800'
                      }`}>
                        Exp: {b.expiryDate} ({b.daysToExpiry}d left - {b.daysToExpiry <= 30 ? 'Critical' : b.daysToExpiry <= 90 ? 'Near Expiry' : 'Safe'})
                      </span>
                    </div>
                  ))}
                  {availableBatches.length > 3 && (
                    <div className="text-[10px] text-ink-500 italic text-right">+{availableBatches.length - 3} additional batches in queue</div>
                  )}
                </div>
              ) : (
                <div className="text-[11px] text-forest-700 italic">
                  Units will be allocated automatically against the nearest-expiry batch in {warehouse}.
                </div>
              )}
            </div>
          </div>
        )}

        {/* 2. RECEIPT (INBOUND) SPECIFIC FIELDS */}
        {type === 'RECEIPT' && (
          <div className="space-y-3 p-3 bg-amber-100/30 rounded-md border border-amber-600/20">
            <span className="text-[11px] font-bold text-amber-900 uppercase block">Inbound Supplier Batch Details</span>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Supplier Name</label>
                <select
                  value={supplierName}
                  onChange={(e) => setSupplierName(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white text-ink-800 font-medium focus:outline-none focus:border-forest-600"
                  required
                >
                  {suppliersList.length > 0 ? (
                    suppliersList.map((s) => (
                      <option key={s.id || s.name} value={s.name}>{s.name}</option>
                    ))
                  ) : (
                    <>
                      <option value="Sun Pharma Labs">Sun Pharma Labs</option>
                      <option value="Cipla Healthcare">Cipla Healthcare</option>
                      <option value="Dr. Reddy's Laboratories">Dr. Reddy's Laboratories</option>
                      <option value="Lupin Pharmaceuticals">Lupin Pharmaceuticals</option>
                      <option value="Biocon Biologics">Biocon Biologics</option>
                    </>
                  )}
                </select>
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Purchase Order / GRN Ref</label>
                <input
                  type="text"
                  value={poNumber}
                  onChange={(e) => setPoNumber(e.target.value)}
                  placeholder="e.g. PO-8845"
                  className="w-full text-[12px] font-mono border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Receipt Quantity (Units)</label>
                <input
                  type="number"
                  min="1"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full text-[12.5px] font-bold border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Unit Cost / Purchase Rate (₹)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={unitCost}
                  onChange={(e) => setUnitCost(e.target.value)}
                  placeholder="e.g. 25.00"
                  className="w-full text-[12.5px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Batch ID (Optional)</label>
                <input
                  type="text"
                  value={batchId}
                  onChange={(e) => setBatchId(e.target.value)}
                  placeholder="Auto-generated if blank"
                  className="w-full text-[12px] font-mono border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                />
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Batch Expiry Date</label>
                <input
                  type="date"
                  value={expiryDate}
                  onChange={(e) => setExpiryDate(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                  required
                />
              </div>
            </div>
          </div>
        )}

        {/* 3. AUDIT ADJUSTMENT SPECIFIC FIELDS */}
        {type === 'ADJUSTMENT' && (
          <div className="space-y-3 p-3 bg-gold-100/30 rounded-md border border-gold-600/20">
            <span className="text-[11px] font-bold text-gold-900 uppercase block">Physical Inventory Audit Reconcile</span>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Current System Count</label>
                <div className="text-[13px] font-bold px-3 py-1.5 bg-cream-200 rounded border border-ink-200 text-ink-800">
                  {Number(liveStock).toLocaleString()} units
                </div>
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Actual Physical Counted</label>
                <input
                  type="number"
                  min="0"
                  value={actualPhysicalCount}
                  onChange={(e) => setActualPhysicalCount(e.target.value)}
                  className="w-full text-[13px] font-bold border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600 text-ink-900"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Variance Reason</label>
                <select
                  value={adjustmentReason}
                  onChange={(e) => setAdjustmentReason(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white text-ink-800 font-medium focus:outline-none focus:border-forest-600"
                >
                  <option value="Physical Cycle Count Discrepancy">Physical Cycle Count Discrepancy</option>
                  <option value="Damaged in Warehouse Storage">Damaged in Warehouse Storage</option>
                  <option value="Liquid Spillage / Breakage">Liquid Spillage / Breakage</option>
                  <option value="Quarantine Reclassification">Quarantine Reclassification</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Auditor / Officer Name</label>
                <input
                  type="text"
                  value={auditorName}
                  onChange={(e) => setAuditorName(e.target.value)}
                  placeholder="e.g. Lead QA Auditor"
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                />
              </div>
            </div>
          </div>
        )}

        {/* 4. INTER-DC TRANSFER SPECIFIC FIELDS */}
        {type === 'TRANSFER_OUT' && (
          <div className="space-y-3 p-3 bg-purple-100/30 rounded-md border border-purple-600/20">
            <span className="text-[11px] font-bold text-purple-900 uppercase block">Inter-DC Stock Rebalancing</span>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Destination Warehouse (To)</label>
                <select
                  value={destinationWarehouse}
                  onChange={(e) => setDestinationWarehouse(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white text-ink-800 font-medium focus:outline-none focus:border-forest-600"
                  required
                >
                  {warehouses
                    .filter((w) => w.id !== warehouse)
                    .map((w) => (
                      <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
                    ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Transfer Quantity (Units)</label>
                <input
                  type="number"
                  min="1"
                  max={liveStock}
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full text-[13px] font-bold border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-1">
                <label className="text-[11px] text-ink-600 block mb-1">Unit Cost Valuation (₹)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={unitCost}
                  onChange={(e) => setUnitCost(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                />
              </div>
              <div className="sm:col-span-1">
                <label className="text-[11px] text-ink-600 block mb-1">Rebalancing Reason</label>
                <input
                  type="text"
                  value={transferReason}
                  onChange={(e) => setTransferReason(e.target.value)}
                  placeholder="e.g. Prevent Tier-2 DC stockout"
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                />
              </div>
              <div className="sm:col-span-1">
                <label className="text-[11px] text-ink-600 block mb-1">Estimated Transit Days</label>
                <input
                  type="number"
                  min="1"
                  value={transitDays}
                  onChange={(e) => setTransitDays(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                />
              </div>
            </div>

            {availableBatches.length > 0 && (
              <div className="text-[11px] text-purple-900 bg-purple-100/60 p-2 rounded border border-purple-600/20 font-mono">
                ⚡ <strong>FEFO Transfer Source:</strong> Units deducted from nearest-expiry batch <strong>{availableBatches[0].id}</strong> (Exp: {availableBatches[0].expiryDate}, {availableBatches[0].daysToExpiry}d remaining).
              </div>
            )}
          </div>
        )}

        {/* 5. CONSUMPTION SPECIFIC FIELDS */}
        {type === 'CONSUMPTION' && (
          <div className="space-y-3 p-3 bg-cream-200/50 rounded-md border border-ink-100">
            <span className="text-[11px] font-bold text-ink-800 uppercase block">Dispensing & Consumption Record</span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Department / Clinical Unit</label>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder="e.g. Emergency Ward"
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Quantity (Units)</label>
                <input
                  type="number"
                  min="1"
                  max={liveStock}
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="w-full text-[13px] font-bold border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                  required
                />
              </div>
              <div>
                <label className="text-[11px] text-ink-600 block mb-1">Unit Cost Valuation (₹)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={unitCost}
                  onChange={(e) => setUnitCost(e.target.value)}
                  className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] text-ink-600 block mb-1">Dispensing Reason / Note</label>
              <input
                type="text"
                value={consumptionReason}
                onChange={(e) => setConsumptionReason(e.target.value)}
                placeholder="e.g. Hospital inpatient antibiotic course"
                className="w-full text-[12px] border border-ink-200 rounded px-2.5 py-1.5 bg-white focus:outline-none focus:border-forest-600"
              />
            </div>

            {availableBatches.length > 0 && (
              <div className="text-[11px] text-forest-900 bg-forest-100/60 p-2 rounded border border-forest-600/20 font-mono">
                ⚡ <strong>FEFO Dispensing:</strong> Units allocated from nearest-expiry batch <strong>{availableBatches[0].id}</strong> (Exp: {availableBatches[0].expiryDate}, {availableBatches[0].daysToExpiry}d remaining).
              </div>
            )}
          </div>
        )}

        {/* Dynamic Price & Valuation Section: Conditionally shown ONLY for Inbound, Outbound, and Inter-DC Transfer */}
        {showTotalCost && (
          <div className="bg-forest-100/40 rounded-md p-3 border border-forest-600/20 text-[12px] space-y-1.5 animate-fadeIn">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-forest-900">Total Transaction Value</span>
              <span className="text-[10.5px] bg-forest-200/80 text-forest-900 px-2 py-0.5 rounded font-medium">
                {type === 'SALE' ? 'Selling Price × Quantity' : 'Unit Cost × Quantity'}
              </span>
            </div>
            <div className="flex items-center justify-between text-ink-700">
              <span>{type === 'SALE' ? 'Selling Price / Unit:' : 'Active Unit Cost:'}</span>
              <span className="font-mono font-semibold">
                ₹{Number(activeUnitCost).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex items-center justify-between text-ink-700">
              <span>Transaction Quantity:</span>
              <span className="font-mono font-semibold">{Number(activeQuantity).toLocaleString()} units</span>
            </div>
            <div className="flex items-center justify-between text-forest-900 border-t border-forest-600/20 pt-1.5 font-bold">
              <span>Total Valuation:</span>
              <span className="text-forest-800 font-mono text-[13.5px]">
                ₹{Number(totalValuation).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        )}

        {/* Live Balance Impact Preview */}
        <div className="bg-cream-200/80 rounded-md p-3 border border-ink-100 text-[12px] space-y-1.5">
          <div className="font-semibold text-ink-900">Live Inventory Balance Impact</div>
          <div className="flex items-center justify-between text-ink-700">
            <span>Current Stock in {warehouse}:</span>
            <span className="font-semibold">{Number(liveStock).toLocaleString()} units</span>
          </div>
          <div className="flex items-center justify-between text-ink-700">
            <span>Transaction Impact:</span>
            <span className={isDeduction ? 'text-brick-600 font-bold' : 'text-forest-700 font-bold'}>
              {isAdjustment
                ? (adjustmentDelta >= 0 ? `+${adjustmentDelta.toLocaleString()}` : `${adjustmentDelta.toLocaleString()}`)
                : (isDeduction ? `-${Number(quantity || 0).toLocaleString()}` : `+${Number(quantity || 0).toLocaleString()}`)}{' '}
              units
            </span>
          </div>
          <div className="flex items-center justify-between text-ink-900 border-t border-ink-200 pt-1.5 font-bold">
            <span>Projected New Balance:</span>
            <span className="text-forest-800 font-mono text-[13px]">
              {Number(projectedStock).toLocaleString()} units
            </span>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-2.5 bg-brick-100 border border-brick-600/30 rounded text-brick-700 text-[12px]">
            <AlertCircle size={14} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 p-2.5 bg-forest-100 border border-forest-600/30 rounded text-forest-800 text-[12px] font-semibold animate-fadeIn">
            <CheckCircle2 size={14} className="shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-ink-100">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 border border-ink-200 rounded text-[12px] text-ink-700 hover:bg-cream-200 cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded text-[12px] font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50"
          >
            {loading ? 'Submitting to Database...' : 'Update Inventory'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
