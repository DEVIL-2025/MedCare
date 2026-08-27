import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  Search, Building2, Boxes, Gauge, AlertTriangle, Plus, CheckCircle2, Edit2, Trash2
} from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import AddWarehouseModal from '../components/warehouses/AddWarehouseModal';
import EditWarehouseModal from '../components/warehouses/EditWarehouseModal';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';

const statusTone = { Healthy: 'good', 'At Risk': 'critical', Monitor: 'warning', Decommissioned: 'critical' };

export default function Warehouses() {
  const { refreshKey, triggerRefresh } = useControlTower();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedWarehouse, setSelectedWarehouse] = useState(null);

  const loadWarehouses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getWarehouses();
      if (res) {
        setData(res);
      } else {
        throw new Error('Failed to load warehouse data');
      }
    } catch (err) {
      console.error('Warehouses load error:', err);
      setError(err.message || 'Unable to connect to warehouse service.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWarehouses();
  }, [loadWarehouses, refreshKey]);

  const overviewList = useMemo(() => {
    if (!data) return [];
    const list = Array.isArray(data) ? data : (data.overview || []);
    return list;
  }, [data]);

  const filtered = useMemo(() => {
    return overviewList.filter((w) => {
      const wId = w.id || '';
      const wName = w.name || '';
      const wLoc = w.location || '';
      const matchesSearch =
        wId.toLowerCase().includes(search.toLowerCase()) ||
        wName.toLowerCase().includes(search.toLowerCase()) ||
        wLoc.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === 'All' || w.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [overviewList, search, statusFilter]);

  function handleOpenEdit(wh) {
    setSelectedWarehouse(wh);
    setEditModalOpen(true);
  }

  async function handleDeleteWarehouse(wh) {
    if (window.confirm(`Are you sure you want to decommission warehouse "${wh.name}" (${wh.id})? Historical audit logs will remain intact.`)) {
      try {
        await api.deleteWarehouse(wh.id);
        triggerRefresh();
        await loadWarehouses();
      } catch (err) {
        alert(`Failed to delete warehouse: ${err.message}`);
      }
    }
  }

  if (loading && !data) {
    return <LoadingState message="Loading distribution centers and capacity metrics from Database..." />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={loadWarehouses} />;
  }

  const top_by_value = data?.top_by_value || [];

  const totalInventory = overviewList.reduce((sum, w) => sum + (Number(w.inventory) || 0), 0);
  const avgUtilization = overviewList.length > 0 ? Math.round(overviewList.reduce((sum, w) => sum + (Number(w.utilization) || 0), 0) / overviewList.length) : 0;
  const atRiskCount = overviewList.filter((w) => w.status === 'At Risk').length;

  return (
    <div className="space-y-5">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3.5 rounded-lg border border-ink-100 shadow-card">
        <div>
          <h2 className="text-[16px] font-bold text-ink-900">Distribution Centers & Logistics Hubs</h2>
          <p className="text-[12px] text-ink-500">Live multi-tier DC capacity tracking, stock valuation, and space utilization metrics.</p>
        </div>
        <button
          onClick={() => setAddModalOpen(true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[12px] font-semibold transition-colors shadow-sm cursor-pointer"
        >
          <Plus size={15} /> Add New Warehouse
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Building2} tone="forest" label="Active Distribution Centers" value={overviewList.length} delta="Active Database nodes" />
        <StatCard icon={Boxes} tone="gold" label="Total Network Physical Stock" value={`${totalInventory.toLocaleString()} units`} delta="Physical inventory count" />
        <StatCard icon={Gauge} tone="sage" label="Average Capacity Utilization" value={`${avgUtilization}%`} delta="Network capacity factor" />
        <StatCard icon={AlertTriangle} tone="brick" label="DCs Requiring Attention" value={atRiskCount} delta="Imminent stockout / surge risk" deltaPositive={false} />
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3.5 rounded-lg border border-ink-100 shadow-card">
        <div className="relative max-w-sm w-full">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <input
            type="text"
            placeholder="Search DC name, code, or city..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-[12px] rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
          />
        </div>

        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-[12px] px-2.5 py-1.5 rounded border border-ink-200 bg-white text-ink-700 focus:outline-none focus:border-forest-600 font-medium"
          >
            <option value="All">All Health Statuses</option>
            <option value="Healthy">Healthy</option>
            <option value="At Risk">At Risk</option>
            <option value="Monitor">Monitor</option>
          </select>
        </div>
      </div>

      {/* Warehouses Table */}
      {filtered.length === 0 ? (
        <EmptyState title="No Warehouses Found" description="No distribution centers match your active filter." />
      ) : (
        <div className="bg-white rounded-lg border border-ink-100 shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                <tr>
                  <th className="py-3 px-3.5">DC Code & Facility</th>
                  <th className="py-3 px-3">Location & Tier</th>
                  <th className="py-3 px-3">Stock Units</th>
                  <th className="py-3 px-3">Capacity Utilization</th>
                  <th className="py-3 px-3">Critical SKUs</th>
                  <th className="py-3 px-3">Stock Valuation</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {filtered.map((wh) => (
                  <tr key={wh.id} className="hover:bg-cream-100/60 transition-colors">
                    <td className="py-3 px-3.5">
                      <div className="font-semibold text-ink-900">{wh.name}</div>
                      <div className="text-[10.5px] text-ink-400 font-mono">{wh.id}</div>
                    </td>
                    <td className="py-3 px-3 text-ink-600">
                      <div>{wh.location}</div>
                      <div className="text-[10.5px] text-ink-400">{wh.tier || 'Tier-2 DC'} • {wh.region || 'West'}</div>
                    </td>
                    <td className="py-3 px-3 font-medium text-ink-800">
                      <div>{Number(wh.inventory || 0).toLocaleString()} units</div>
                      <div className="text-[10.5px] text-ink-400">Cap: {wh.capacity}</div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-cream-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${wh.utilization >= 90 ? 'bg-brick-600' : wh.utilization >= 75 ? 'bg-amber-500' : 'bg-forest-600'}`}
                            style={{ width: `${Math.min(100, wh.utilization || 50)}%` }}
                          />
                        </div>
                        <span className="font-medium text-[11.5px]">{wh.utilization || 50}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`font-semibold ${Number(wh.criticalSkus || 0) > 0 ? 'text-brick-600' : 'text-forest-700'}`}>
                        {wh.criticalSkus || 0} SKUs
                      </span>
                    </td>
                    <td className="py-3 px-3 font-bold text-forest-800">
                      {wh.valDisplay || '₹0'}
                    </td>
                    <td className="py-3 px-3">
                      <Badge tone={statusTone[wh.status] || 'good'}>{wh.status}</Badge>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleOpenEdit(wh)}
                          className="p-1 text-ink-500 hover:text-forest-700 hover:bg-forest-50 rounded border border-ink-200 transition-colors cursor-pointer"
                          title="Edit Warehouse Parameters"
                        >
                          <Edit2 size={13} />
                        </button>
                        <button
                          onClick={() => handleDeleteWarehouse(wh)}
                          className="p-1 text-ink-500 hover:text-brick-700 hover:bg-brick-50 rounded border border-ink-200 transition-colors cursor-pointer"
                          title="Decommission Warehouse"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Distribution Centers Stock Valuation Overview */}
      <div className="bg-white rounded-lg border border-ink-100 shadow-card p-4">
        <div className="flex items-center justify-between mb-3 border-b border-ink-100 pb-2.5">
          <div>
            <h3 className="text-[14.5px] font-bold text-ink-900">Distribution Centers by Stock Valuation</h3>
            <p className="text-[11.5px] text-ink-500">Aggregated inventory valuation and holding values across active distribution facilities.</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 pt-1 text-[12px]">
          {top_by_value.map((item, i) => (
            <div key={item.id || i} className="space-y-1 p-2 rounded hover:bg-cream-100/50 transition-colors">
              <div className="flex justify-between text-ink-700">
                <span className="font-semibold text-ink-900">{item.name} ({item.id})</span>
                <span className="font-bold text-forest-800">{item.value}</span>
              </div>
              <div className="w-full bg-cream-200 rounded-full h-2">
                <div
                  className="bg-forest-700 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${item.pct}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Add Warehouse Modal */}
      {addModalOpen && (
        <AddWarehouseModal
          open={addModalOpen}
          onClose={() => setAddModalOpen(false)}
          onWarehouseAdded={() => {
            triggerRefresh();
            loadWarehouses();
          }}
        />
      )}

      {/* Edit Warehouse Modal */}
      {editModalOpen && selectedWarehouse && (
        <EditWarehouseModal
          open={editModalOpen}
          warehouse={selectedWarehouse}
          onClose={() => {
            setEditModalOpen(false);
            setSelectedWarehouse(null);
          }}
          onWarehouseUpdated={() => {
            triggerRefresh();
            loadWarehouses();
          }}
        />
      )}
    </div>
  );
}