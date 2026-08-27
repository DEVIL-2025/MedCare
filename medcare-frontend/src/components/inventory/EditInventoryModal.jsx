import { useState, useEffect } from 'react';
import { Sliders, CheckCircle2, AlertCircle, Save, Building2, Package, ShieldAlert } from 'lucide-react';
import Modal from '../ui/Modal';
import { api } from '../../api/client';

export default function EditInventoryModal({ open, onClose, item, onSaved }) {
  const [reorderPoint, setReorderPoint] = useState(200);
  const [safetyStock, setSafetyStock] = useState(80);
  const [unitCost, setUnitCost] = useState(50.0);
  const [moq, setMoq] = useState(50);
  const [currentStock, setCurrentStock] = useState(0);
  const [allowStockAdjustment, setAllowStockAdjustment] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    if (item) {
      setReorderPoint(item.reorderPoint !== undefined ? item.reorderPoint : (item.defaultReorderPoint || 200));
      setSafetyStock(item.safetyStock !== undefined ? item.safetyStock : (item.defaultSafetyStock || 80));
      setUnitCost(item.unitCost !== undefined ? item.unitCost : (item.price || 50.0));
      setMoq(item.moq !== undefined ? item.moq : 50);
      setCurrentStock(item.currentStock || 0);
      setAllowStockAdjustment(false);
      setError(null);
      setSuccess(null);
    }
  }, [item, open]);

  if (!item) return null;

  const warehouseId = item.warehouseId || item.warehouse || 'MUM-01';

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Validation
    const ropNum = Number(reorderPoint);
    const ssNum = Number(safetyStock);
    const costNum = Number(unitCost);
    const moqNum = Number(moq);
    const stockNum = Number(currentStock);

    if (isNaN(ropNum) || ropNum < 0) {
      setError('Reorder Point must be a non-negative number.');
      return;
    }
    if (isNaN(ssNum) || ssNum < 0) {
      setError('Safety Stock must be a non-negative number.');
      return;
    }
    if (isNaN(costNum) || costNum <= 0) {
      setError('Unit Cost / Price must be greater than 0.');
      return;
    }
    if (isNaN(moqNum) || moqNum < 1) {
      setError('Minimum Order Quantity (MOQ) must be at least 1.');
      return;
    }
    if (allowStockAdjustment && (isNaN(stockNum) || stockNum < 0)) {
      setError('Current Stock must be a non-negative number.');
      return;
    }

    setLoading(true);

    try {
      const payload = {
        reorder_point: ropNum,
        safety_stock: ssNum,
        unit_cost: costNum,
        moq: moqNum,
        ...(allowStockAdjustment ? { current_stock: stockNum } : {})
      };

      const res = await api.updateInventoryConfig(warehouseId, item.sku, payload);
      setSuccess(res.message || `Inventory configuration for ${item.sku} at ${warehouseId} saved to database!`);

      setTimeout(() => {
        if (onSaved) onSaved(res);
        onClose();
      }, 1000);
    } catch (err) {
      console.error('Failed to update inventory config:', err);
      setError(err.message || 'Failed to persist configuration in database.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Configure Warehouse Inventory: ${item.sku}`}>
      <form onSubmit={handleSubmit} className="space-y-4 text-[12.5px]">
        {/* Product & Warehouse Summary Banner */}
        <div className="p-3 bg-cream-100/70 border border-ink-100 rounded-lg flex items-center justify-between gap-3">
          <div className="space-y-0.5">
            <div className="font-bold text-ink-900 flex items-center gap-1.5">
              <Package size={14} className="text-forest-700" />
              <span>{item.name || item.sku}</span>
            </div>
            <div className="text-[11px] text-ink-500 font-mono">
              SKU: <span className="font-semibold text-ink-800">{item.sku}</span> | Category: <span className="font-semibold text-ink-800">{item.category || 'General'}</span>
            </div>
          </div>
          <div className="text-right">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-cream-200 text-ink-800 border border-ink-200">
              <Building2 size={12} className="text-amber-700" /> {warehouseId}
            </span>
            <div className="text-[10.5px] text-ink-400 mt-0.5">Warehouse-Specific Policy</div>
          </div>
        </div>

        {error && (
          <div className="p-2.5 rounded bg-brick-100 border border-brick-600/30 text-brick-700 font-medium flex items-center gap-2 text-[12px]">
            <AlertCircle size={15} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="p-2.5 rounded bg-forest-100 border border-forest-600/30 text-forest-800 font-medium flex items-center gap-2 text-[12px]">
            <CheckCircle2 size={15} className="shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {/* Configuration Inputs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
          {/* Reorder Point */}
          <div>
            <label className="block text-ink-700 font-semibold mb-1">
              Reorder Point (ROP) <span className="text-brick-600">*</span>
            </label>
            <input
              type="number"
              min="0"
              required
              value={reorderPoint}
              onChange={(e) => setReorderPoint(e.target.value)}
              className="w-full px-3 py-1.5 border border-ink-200 rounded text-[12.5px] font-mono focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
            />
            <p className="text-[10.5px] text-ink-400 mt-0.5">
              Replenishment triggers when stock falls below this level in {warehouseId}.
            </p>
          </div>

          {/* Safety Stock */}
          <div>
            <label className="block text-ink-700 font-semibold mb-1">
              Safety Stock Buffer <span className="text-brick-600">*</span>
            </label>
            <input
              type="number"
              min="0"
              required
              value={safetyStock}
              onChange={(e) => setSafetyStock(e.target.value)}
              className="w-full px-3 py-1.5 border border-ink-200 rounded text-[12.5px] font-mono focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
            />
            <p className="text-[10.5px] text-ink-400 mt-0.5">
              Critical buffer threshold. Stock remains sellable/transactable.
            </p>
          </div>

          {/* Unit Price / Cost */}
          <div>
            <label className="block text-ink-700 font-semibold mb-1">
              Unit Price / Cost (₹ INR) <span className="text-brick-600">*</span>
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={unitCost}
              onChange={(e) => setUnitCost(e.target.value)}
              className="w-full px-3 py-1.5 border border-ink-200 rounded text-[12.5px] font-mono focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
            />
            <p className="text-[10.5px] text-ink-400 mt-0.5">
              Active unit valuation used in inventory value and procurement calculations.
            </p>
          </div>

          {/* Minimum Order Quantity (MOQ) */}
          <div>
            <label className="block text-ink-700 font-semibold mb-1">
              Minimum Order Qty (MOQ) <span className="text-brick-600">*</span>
            </label>
            <input
              type="number"
              min="1"
              required
              value={moq}
              onChange={(e) => setMoq(e.target.value)}
              className="w-full px-3 py-1.5 border border-ink-200 rounded text-[12.5px] font-mono focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
            />
            <p className="text-[10.5px] text-ink-400 mt-0.5">
              Minimum supplier batch order size.
            </p>
          </div>
        </div>

        {/* Optional Physical Stock Override Toggle */}
        <div className="border-t border-ink-100 pt-3">
          <label className="flex items-center gap-2 cursor-pointer select-none text-[12px] text-ink-700">
            <input
              type="checkbox"
              checked={allowStockAdjustment}
              onChange={(e) => setAllowStockAdjustment(e.target.checked)}
              className="rounded text-forest-700 focus:ring-forest-600 cursor-pointer"
            />
            <span className="font-medium">Direct physical stock level adjustment</span>
          </label>

          {allowStockAdjustment && (
            <div className="mt-2.5 p-3 bg-amber-50 border border-amber-200 rounded-md space-y-2 animate-fadeIn">
              <div className="flex items-start gap-2 text-[11.5px] text-amber-800">
                <ShieldAlert size={14} className="shrink-0 mt-0.5 text-amber-700" />
                <span>
                  Adjusting stock count directly will write an audit-logged <strong>ADJUSTMENT</strong> transaction to the database.
                </span>
              </div>
              <div>
                <label className="block text-ink-800 font-semibold mb-1">New Physical Stock Count:</label>
                <input
                  type="number"
                  min="0"
                  value={currentStock}
                  onChange={(e) => setCurrentStock(e.target.value)}
                  className="w-full px-3 py-1.5 border border-ink-200 rounded text-[12.5px] font-mono focus:outline-none focus:ring-1 focus:ring-forest-600 bg-white"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-ink-100">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-3.5 py-1.5 border border-ink-200 rounded-md text-ink-700 font-medium hover:bg-cream-200 transition-colors cursor-pointer text-[12px]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-forest-800 text-white rounded-md font-semibold hover:bg-forest-700 transition-colors shadow-xs cursor-pointer text-[12px] disabled:opacity-50"
          >
            <Save size={14} />
            <span>{loading ? 'Saving...' : 'Save Configuration'}</span>
          </button>
        </div>
      </form>
    </Modal>
  );
}
