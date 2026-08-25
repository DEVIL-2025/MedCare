import { useState, useEffect } from 'react';
import { ShoppingCart, AlertCircle, CheckCircle2 } from 'lucide-react';
import Modal from '../ui/Modal';
import { api } from '../../api/client';

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

export default function RecordSaleModal({ open, onClose, defaultItem, onSaleRecorded }) {
  const [sku, setSku] = useState(defaultItem?.sku || 'P-1065');
  const [warehouse, setWarehouse] = useState(resolveValidWarehouseId(defaultItem?.warehouse, defaultItem, [], 'MUM-01'));
  const [quantity, setQuantity] = useState(150);
  const [customerName, setCustomerName] = useState('Apollo Hospitals Mumbai');
  const [channel, setChannel] = useState('Hospital');
  const [unitPrice, setUnitPrice] = useState(defaultItem?.unitCost ? defaultItem.unitCost * 1.25 : 32.0);
  const [reason, setReason] = useState('Outbound hospital clinical dispensing supply');
  const [warehouses, setWarehouses] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [whs, prods] = await Promise.all([
          api.getWarehouses(),
          api.getProducts()
        ]);
        const whList = Array.isArray(whs) ? whs : (whs?.overview || []);
        setWarehouses(whList);
        setProducts(Array.isArray(prods) ? prods : []);
        if (whList.length > 0) {
          setWarehouse(prev => resolveValidWarehouseId(prev, defaultItem, whList));
        }
      } catch (err) {
        console.warn('Failed to load metadata for sale modal:', err);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    if (defaultItem) {
      if (defaultItem.sku) setSku(defaultItem.sku);
      const validWh = resolveValidWarehouseId(defaultItem.warehouse_id || defaultItem.warehouse, defaultItem, warehouses);
      setWarehouse(validWh);
      if (defaultItem.unitCost) setUnitPrice(defaultItem.unitCost * 1.25);
    }
  }, [defaultItem, warehouses]);

  const selectedProd = products.find(p => p.sku === sku);
  const totalPrice = Number(quantity || 0) * Number(unitPrice || 0);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const cleanWh = String(warehouse || '').trim();
    if (!cleanWh || ['all', 'all warehouses', 'network', 'network rollup', 'all_dcs'].includes(cleanWh.toLowerCase())) {
      setError('Please select a specific distribution center warehouse.');
      return;
    }

    setLoading(true);

    try {
      const res = await api.recordSale({
        sku: sku.trim().toUpperCase(),
        warehouse_id: cleanWh,
        quantity: Number(quantity),
        customer_name: customerName,
        channel,
        unit_price: Number(unitPrice),
        reason
      });

      setSuccess(res.message || 'Sale recorded successfully! Inventory decremented via FEFO.');
      if (onSaleRecorded) onSaleRecorded(res);

      setTimeout(() => {
        setSuccess(null);
        onClose();
      }, 1400);
    } catch (err) {
      setError(err.message || 'Failed to record sale');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Record Outbound Sale & Real-Time Stock Decrement">
      <form onSubmit={handleSubmit} className="space-y-4 text-[12.5px]">
        {/* Customer & Channel */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Customer / Healthcare Institution</label>
            <input
              type="text"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600 bg-white"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Distribution Channel</label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="Hospital">Hospital / Clinical Network</option>
              <option value="Distributor">Wholesale Distributor</option>
              <option value="Retail Pharmacy">Retail Pharmacy Chain</option>
              <option value="Online">Online / Direct-to-Patient</option>
            </select>
          </div>
        </div>

        {/* Product & Warehouse */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Product / SKU</label>
            <select
              value={sku}
              onChange={(e) => {
                const newSku = e.target.value;
                setSku(newSku);
                const p = products.find(prod => prod.sku === newSku);
                if (p) setUnitPrice(p.unitCost * 1.25);
              }}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 font-mono text-[12px] focus:outline-none focus:border-forest-600"
            >
              {products.map((p) => (
                <option key={p.sku} value={p.sku}>{p.name} ({p.sku})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Fulfilling Distribution Center</label>
            <select
              value={warehouse}
              onChange={(e) => setWarehouse(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 text-[12px] focus:outline-none focus:border-forest-600"
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
                </>
              )}
            </select>
          </div>
        </div>

        {/* Quantity & Unit Price */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Order Quantity (Units)</label>
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded font-bold text-forest-900 focus:outline-none focus:border-forest-600 bg-white"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Unit Billing Price (₹ INR)</label>
            <input
              type="number"
              step="0.5"
              value={unitPrice}
              onChange={(e) => setUnitPrice(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded text-ink-900 focus:outline-none focus:border-forest-600 bg-white"
              required
            />
          </div>
        </div>

        {/* Order Reason */}
        <div>
          <label className="text-[11px] font-semibold text-ink-700 block mb-1">Transaction Reason / PO Reference</label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Scheduled bi-weekly replenishment for hospital pharmacy"
            className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600 bg-white"
          />
        </div>

        {/* Total Price & FEFO Notice */}
        <div className="p-3 bg-cream-200/80 rounded-md border border-ink-100 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-ink-500 font-medium">Estimated Invoice Total</div>
            <div className="text-[15px] font-bold text-forest-800">
              ₹{totalPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          <div className="text-[11px] text-forest-700 bg-forest-100/60 px-2.5 py-1 rounded border border-forest-600/20 font-medium">
            ⚡ FEFO Batch Deduction Guaranteed
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-2.5 rounded-md bg-brick-100 text-brick-700 text-[12px]">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 p-2.5 rounded-md bg-forest-100 text-forest-800 text-[12px] animate-fadeIn">
            <CheckCircle2 size={15} />
            <span>{success}</span>
          </div>
        )}

        <div className="flex justify-end gap-2.5 pt-2 border-t border-ink-100">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 text-[13px] border border-ink-100 rounded-md text-ink-700 hover:bg-cream-200 cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-1.5 text-[13px] font-medium bg-forest-700 text-white rounded-md hover:bg-forest-600 disabled:opacity-50 shadow-sm cursor-pointer"
          >
            {loading ? 'Submitting to PostgreSQL...' : 'Record Sale & Decrement Stock'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
