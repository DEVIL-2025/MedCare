import { useState } from 'react';
import { Building2, AlertCircle, CheckCircle2 } from 'lucide-react';
import Modal from '../ui/Modal';
import { api } from '../../api/client';

export default function AddWarehouseModal({ open, onClose, onWarehouseAdded }) {
  const [id, setId] = useState('');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [tier, setTier] = useState('Tier-2 DC');
  const [region, setRegion] = useState('West');
  const [capacityUnits, setCapacityUnits] = useState(10000);
  const [mapX, setMapX] = useState(40);
  const [mapY, setMapY] = useState(55);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      const res = await api.addWarehouse({
        id: id.trim().toUpperCase(),
        name: name.trim(),
        location: location.trim(),
        tier,
        region,
        capacity_units: Number(capacityUnits),
        current_utilization_pct: 10.0,
        health_score: 98,
        status: 'Healthy',
        map_x: Number(mapX),
        map_y: Number(mapY)
      });

      setSuccess(res.message || 'Warehouse successfully added to network database.');
      if (onWarehouseAdded) onWarehouseAdded(res);

      setTimeout(() => {
        setSuccess(null);
        onClose();
      }, 1400);
    } catch (err) {
      setError(err.message || 'Failed to add warehouse');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Commission New Distribution Center (DC)">
      <form onSubmit={handleSubmit} className="space-y-4 text-[12.5px]">
        {/* DC ID & Name */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">DC Identifier Code</label>
            <input
              type="text"
              placeholder="e.g. AHM-01"
              value={id}
              onChange={(e) => setId(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded font-mono uppercase focus:outline-none focus:border-forest-600 bg-cream-100/50"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Facility / Warehouse Name</label>
            <input
              type="text"
              placeholder="e.g. Ahmedabad Regional Distribution Center"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600 bg-cream-100/50"
              required
            />
          </div>
        </div>

        {/* Location & Region */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">City / Location</label>
            <input
              type="text"
              placeholder="e.g. Ahmedabad, Gujarat"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Geographic Region</label>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="North">North India</option>
              <option value="South">South India</option>
              <option value="West">West India</option>
              <option value="East">East India</option>
              <option value="Central">Central India</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Echelon Network Tier</label>
            <select
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded bg-white text-ink-800 focus:outline-none focus:border-forest-600"
            >
              <option value="Mother DC">Mother DC (National Hub)</option>
              <option value="Tier-1 DC">Tier-1 DC (Regional Hub)</option>
              <option value="Tier-2 DC">Tier-2 DC (Local Spoke)</option>
            </select>
          </div>
        </div>

        {/* Capacity & Map Coordinates */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Capacity (Units)</label>
            <input
              type="number"
              min="500"
              step="500"
              value={capacityUnits}
              onChange={(e) => setCapacityUnits(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Map X Coordinate (%)</label>
            <input
              type="number"
              min="5"
              max="95"
              value={mapX}
              onChange={(e) => setMapX(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600"
              required
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-700 block mb-1">Map Y Coordinate (%)</label>
            <input
              type="number"
              min="5"
              max="95"
              value={mapY}
              onChange={(e) => setMapY(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ink-200 rounded focus:outline-none focus:border-forest-600"
              required
            />
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
            {loading ? 'Adding DC to Network...' : 'Add Distribution Center'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
