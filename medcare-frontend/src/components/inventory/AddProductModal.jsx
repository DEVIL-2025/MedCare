import { useState, useEffect } from 'react';
import { Package, Plus, AlertCircle, CheckCircle2 } from 'lucide-react';
import Modal from '../ui/Modal';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';

const PHARMA_CATEGORIES = [
  'Analgesics',
  'Antibiotics',
  'Cough & Cold',
  'Diabetes Care',
  'Gastro Care',
  'Vitamins',
  'Respiratory',
  'Cardiovascular',
  'Oncology',
  'Dermatology'
];

export default function AddProductModal({ open, onClose, onProductAdded }) {
  const { isAdmin, hasPermission } = useAuth();
  const canAdd = isAdmin || hasPermission('inventory.create_product');

  const [sku, setSku] = useState('');
  const [name, setName] = useState('');
  const [category, setCategory] = useState(PHARMA_CATEGORIES[0]);
  const [criticality, setCriticality] = useState('Critical');
  const [unit, setUnit] = useState('Strips');
  const [unitCost, setUnitCost] = useState(45.0);
  const [moq, setMoq] = useState(2500);
  const [reorderPoint, setReorderPoint] = useState(8000);
  const [safetyStock, setSafetyStock] = useState(4000);
  const [initialWarehouse, setInitialWarehouse] = useState('MUM-01');
  const [initialStock, setInitialStock] = useState(5000);
  const [isTempSensitive, setIsTempSensitive] = useState(false);
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    async function loadWhs() {
      try {
        const whs = await api.getWarehouses();
        const list = Array.isArray(whs) ? whs : (whs?.overview || []);
        setWarehouses(list);
        if (list.length > 0) setInitialWarehouse(list[0].id);
      } catch (err) {
        console.warn('Failed to load warehouses:', err);
      }
    }
    loadWhs();
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      const res = await api.addProduct({
        sku: sku.trim().toUpperCase(),
        name: name.trim(),
        category,
        criticality,
        unit,
        unit_cost: Number(unitCost),
        moq: Number(moq),
        default_reorder_point: Number(reorderPoint),
        default_safety_stock: Number(safetyStock),
        initial_warehouse_id: initialWarehouse,
        initial_stock: Number(initialStock),
        is_temperature_sensitive: isTempSensitive
      });

      setSuccess(res.message || 'Product successfully registered in database catalog.');
      if (onProductAdded) onProductAdded(res);

      setTimeout(() => {
        setSuccess(null);
        onClose();
      }, 1400);
    } catch (err) {
      setError(err.message || 'Failed to add product');
    } finally {
      setLoading(false);
    }
  }

  if (!canAdd) return null;

  return (
    <Modal open={open} onClose={onClose} title="Register New Pharmaceutical SKU in Catalog">
      <form onSubmit={handleSubmit} className="space-y-4 text-[12.5px]">
        {/* Basic Details */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">SKU Identifier Code</label>
            <input
              type="text"
              placeholder="e.g. AZ-9920"
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded font-mono uppercase focus:outline-none focus:border-forest-600 bg-cream-100/50"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Product Generic / Brand Name</label>
            <input
              type="text"
              placeholder="e.g. Azithromycin 250mg Suspension"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600 bg-cream-100/50"
              required
            />
          </div>
        </div>

        {/* Category & Criticality */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Therapeutic Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              {PHARMA_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Clinical Criticality</label>
            <select
              value={criticality}
              onChange={(e) => setCriticality(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="Critical">Critical (Life-Saving)</option>
              <option value="High">High Priority</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Dispensing Unit</label>
            <select
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="Strips">Strips</option>
              <option value="Bottles">Bottles</option>
              <option value="Capsules">Capsules</option>
              <option value="Vials">Vials</option>
              <option value="Inhalers">Inhalers</option>
            </select>
          </div>
        </div>

        {/* Cost, MOQ, Thresholds */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Unit Cost (₹ INR)</label>
            <input
              type="number"
              step="0.1"
              min="1"
              value={unitCost}
              onChange={(e) => setUnitCost(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Reorder Point (Units)</label>
            <input
              type="number"
              min="100"
              value={reorderPoint}
              onChange={(e) => setReorderPoint(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Safety Stock (Units)</label>
            <input
              type="number"
              min="50"
              value={safetyStock}
              onChange={(e) => setSafetyStock(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600"
              required
            />
          </div>
        </div>

        {/* Initial Stock Allocation */}
        <div className="p-3 bg-cream-100 rounded-lg border border-ink-100 space-y-2">
          <span className="text-[11.5px] font-bold text-ink-900 block">Initial Warehouse Batch Allocation (Optional)</span>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-ink-500 block mb-1">Receiving Distribution Center</label>
              <select
                value={initialWarehouse}
                onChange={(e) => setInitialWarehouse(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-700 focus:outline-none focus:border-forest-600 text-[12px]"
              >
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] text-ink-500 block mb-1">Initial Opening Stock (Units)</label>
              <input
                type="number"
                min="0"
                value={initialStock}
                onChange={(e) => setInitialStock(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white focus:outline-none focus:border-forest-600 text-[12px]"
              />
            </div>
          </div>
        </div>

        {/* Status messages */}
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
            {loading ? 'Registering Product...' : 'Update Inventory'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
