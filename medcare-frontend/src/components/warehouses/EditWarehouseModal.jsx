import { useState, useEffect } from 'react';
import { Building2, AlertCircle, CheckCircle2 } from 'lucide-react';
import Modal from '../ui/Modal';
import { api } from '../../api/client';

export default function EditWarehouseModal({ open, onClose, warehouse, onWarehouseUpdated }) {
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [tier, setTier] = useState('Tier-1 DC');
  const [region, setRegion] = useState('West');
  const [capacityUnits, setCapacityUnits] = useState(50000);
  const [status, setStatus] = useState('Healthy');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    if (warehouse) {
      setName(warehouse.name || '');
      setLocation(warehouse.location || '');
      setTier(warehouse.tier || 'Tier-1 DC');
      setRegion(warehouse.region || 'West');
      setCapacityUnits(warehouse.capacityUnits || warehouse.capacity_units || 50000);
      setStatus(warehouse.status || 'Healthy');
    }
  }, [warehouse]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!warehouse) return;
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      const res = await api.updateWarehouse(warehouse.id, {
        name: name.trim(),
        location: location.trim(),
        tier,
        region,
        capacity_units: Number(capacityUnits),
        status
      });

      setSuccess(res.message || 'Warehouse parameters updated successfully.');
      if (onWarehouseUpdated) onWarehouseUpdated(res);

      setTimeout(() => {
        setSuccess(null);
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message || 'Failed to update warehouse');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Edit Distribution Center: ${warehouse?.name || ''} (${warehouse?.id || ''})`}>
      <form onSubmit={handleSubmit} className="space-y-4 text-[12.5px]">
        <div>
          <label className="text-[11px] font-semibold text-ink-700 block mb-1">Facility Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600 bg-white"
            required
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">City / Location</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600 bg-white"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Operating Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="Healthy">Healthy (Normal Operations)</option>
              <option value="At Risk">At Risk (High Utilization / Stockout)</option>
              <option value="Monitor">Monitor (Watch List)</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Echelon Tier</label>
            <select
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="Mother DC">Mother DC (Hub)</option>
              <option value="Tier-1 DC">Tier-1 DC (Regional)</option>
              <option value="Tier-2 DC">Tier-2 DC (Spoke)</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Region</label>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="West">West</option>
              <option value="North">North</option>
              <option value="East">East</option>
              <option value="South">South</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Capacity (Units)</label>
            <input
              type="number"
              min="5000"
              step="5000"
              value={capacityUnits}
              onChange={(e) => setCapacityUnits(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600 bg-white"
              required
            />
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
            {loading ? 'Saving Changes...' : 'Save Warehouse Changes'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
