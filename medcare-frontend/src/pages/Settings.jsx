import { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon, Users, Bell, Package, TrendingUp,
  Truck, ShieldCheck, FileClock, Server, Check, Save, Plus, Trash2, AlertCircle, Building2
} from 'lucide-react';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';

const navItems = [
  { label: 'Inventory', icon: Package, desc: 'Inventory rules, FEFO threshold and buffers' },
  { label: 'Suppliers', icon: Truck, desc: 'Add and manage pharmaceutical suppliers' },
  { label: 'Users & Roles', icon: Users, desc: 'Manage access and active stakeholders' },
  { label: 'Audit Logs', icon: FileClock, desc: 'Live system execution records' },
  { label: 'System', icon: Server, desc: 'Architecture and runtime status' },
];

export default function Settings() {
  const { triggerRefresh } = useControlTower();
  const [active, setActive] = useState('Inventory');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState(null);

  // Editable parameters
  const [serviceLevel, setServiceLevel] = useState('95');
  const [leadTimeBuffer, setLeadTimeBuffer] = useState('2');
  const [expiryCriticalDays, setExpiryCriticalDays] = useState('30');
  const [autoApproveLimit, setAutoApproveLimit] = useState('100000');
  const [transferFirstPolicy, setTransferFirstPolicy] = useState('Enabled');

  // Supplier Management State
  const [suppliers, setSuppliers] = useState([]);
  const [loadingSuppliers, setLoadingSuppliers] = useState(false);
  const [suppName, setSuppName] = useState('');
  const [suppEmail, setSuppEmail] = useState('');
  const [suppPhone, setSuppPhone] = useState('');
  const [suppLeadTime, setSuppLeadTime] = useState('5');
  const [suppCategory, setSuppCategory] = useState('');
  const [addingSupplier, setAddingSupplier] = useState(false);
  const [suppActionSuccess, setSuppActionSuccess] = useState(null);
  const [suppActionError, setSuppActionError] = useState(null);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getSettings();
      if (res) {
        setData(res);
        if (res.parameters) {
          if (res.parameters.service_level_pct) setServiceLevel(res.parameters.service_level_pct);
          if (res.parameters.lead_time_buffer_days) setLeadTimeBuffer(res.parameters.lead_time_buffer_days);
          if (res.parameters.expiry_critical_days) setExpiryCriticalDays(res.parameters.expiry_critical_days);
          if (res.parameters.auto_approve_threshold_inr) setAutoApproveLimit(res.parameters.auto_approve_threshold_inr);
          if (res.parameters.transfer_first_policy) setTransferFirstPolicy(res.parameters.transfer_first_policy);
        }
      } else {
        throw new Error('Failed to load settings');
      }
    } catch (err) {
      console.error('Settings load error:', err);
      setError(err.message || 'Unable to connect to settings service.');
    } finally {
      setLoading(false);
    }
  }

  async function loadSuppliers() {
    setLoadingSuppliers(true);
    try {
      const res = await api.getSuppliers();
      setSuppliers(Array.isArray(res) ? res : []);
    } catch (err) {
      console.warn('Failed to load suppliers:', err);
    } finally {
      setLoadingSuppliers(false);
    }
  }

  useEffect(() => {
    loadSettings();
    loadSuppliers();
  }, []);

  async function handleSave(e) {
    if (e) e.preventDefault();
    setSaving(true);
    try {
      await api.updateSettings({
        service_level_pct: serviceLevel,
        lead_time_buffer_days: leadTimeBuffer,
        expiry_critical_days: expiryCriticalDays,
        auto_approve_threshold_inr: autoApproveLimit,
        transfer_first_policy: transferFirstPolicy
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
      loadSettings();
      triggerRefresh();
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleAddSupplier(e) {
    e.preventDefault();
    if (!suppName.trim()) {
      setSuppActionError('Supplier name is required.');
      return;
    }

    setAddingSupplier(true);
    setSuppActionError(null);
    setSuppActionSuccess(null);
    try {
      await api.addSupplier({
        name: suppName.trim(),
        contact_email: suppEmail.trim() || undefined,
        contact_phone: suppPhone.trim() || undefined,
        lead_time_days: Number(suppLeadTime) || 5,
        category: suppCategory.trim() || undefined,
        status: 'Active'
      });
      setSuppActionSuccess(`Supplier '${suppName.trim()}' added to PostgreSQL successfully!`);
      setSuppName('');
      setSuppEmail('');
      setSuppPhone('');
      setSuppLeadTime('5');
      setSuppCategory('');
      await loadSuppliers();
      triggerRefresh();
      setTimeout(() => setSuppActionSuccess(null), 3000);
    } catch (err) {
      setSuppActionError(err.message || 'Failed to add supplier.');
    } finally {
      setAddingSupplier(false);
    }
  }

  async function handleDeleteSupplier(supplierId, supplierName) {
    if (!window.confirm(`Are you sure you want to remove supplier '${supplierName}' from the database?`)) {
      return;
    }

    setSuppActionError(null);
    setSuppActionSuccess(null);
    try {
      await api.deleteSupplier(supplierId);
      setSuppActionSuccess(`Supplier '${supplierName}' removed from PostgreSQL.`);
      await loadSuppliers();
      triggerRefresh();
      setTimeout(() => setSuppActionSuccess(null), 3000);
    } catch (err) {
      setSuppActionError(err.message || 'Failed to remove supplier.');
    }
  }

  if (loading && !data) {
    return <LoadingState message="Loading system configuration parameters from PostgreSQL..." />;
  }

  if (error && !data) {
    return <ErrorState message={error} onRetry={loadSettings} />;
  }

  const users = data?.users || [];
  const audit_logs = data?.audit_logs || [];

  return (
    <div className="space-y-5">
      {/* Top Header */}
      <div className="bg-white p-3.5 rounded-lg border border-ink-100 shadow-card">
        <h2 className="text-[16px] font-bold text-ink-900">Control Tower System & Algorithmic Settings</h2>
        <p className="text-[12px] text-ink-500">Fine-tune safety stock multipliers, manage suppliers, SLA escalation timelines, and role-based access controls.</p>
      </div>

      {saveSuccess && (
        <div className="p-3 bg-forest-100 border border-forest-600/30 text-forest-900 text-[12.5px] rounded-lg font-medium flex items-center gap-2">
          <Check size={16} className="text-forest-700" />
          Settings successfully updated and persisted to PostgreSQL!
        </div>
      )}

      {/* Main Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
        {/* Navigation Sidebar */}
        <div className="bg-white rounded-lg border border-ink-100 shadow-card p-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.label;
            return (
              <button
                key={item.label}
                onClick={() => setActive(item.label)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-md text-left text-[12.5px] transition-colors cursor-pointer ${
                  isActive ? 'bg-forest-700 text-white font-semibold' : 'text-ink-700 hover:bg-cream-200'
                }`}
              >
                <Icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Content Area */}
        <div className="md:col-span-3 bg-white rounded-lg border border-ink-100 shadow-card p-5">
          {/* Tab 1: Inventory & Replenishment Parameters */}
          {active === 'Inventory' && (
            <form onSubmit={handleSave} className="space-y-4 text-[12.5px]">
              <h3 className="text-[15px] font-bold text-ink-900 pb-2 border-b border-ink-100">
                SCM Policy & Replenishment Parameters
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-ink-700 font-semibold mb-1">Target Service Level (%)</label>
                  <input
                    type="number"
                    value={serviceLevel}
                    onChange={(e) => setServiceLevel(e.target.value)}
                    className="w-full px-3 py-1.5 rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
                  />
                  <span className="text-[11px] text-ink-400">Used for dynamic Safety Stock Z-score calculation (95% = 1.65).</span>
                </div>

                <div>
                  <label className="block text-ink-700 font-semibold mb-1">Lead Time Buffer (Days)</label>
                  <input
                    type="number"
                    value={leadTimeBuffer}
                    onChange={(e) => setLeadTimeBuffer(e.target.value)}
                    className="w-full px-3 py-1.5 rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
                  />
                  <span className="text-[11px] text-ink-400">Extra safety window added to DC transit and procurement times.</span>
                </div>

                <div>
                  <label className="block text-ink-700 font-semibold mb-1">FEFO Near-Expiry Threshold (Days)</label>
                  <input
                    type="number"
                    value={expiryCriticalDays}
                    onChange={(e) => setExpiryCriticalDays(e.target.value)}
                    className="w-full px-3 py-1.5 rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
                  />
                  <span className="text-[11px] text-ink-400">Batches expiring within this window trigger automatic FEFO balancing transfers.</span>
                </div>

                <div>
                  <label className="block text-ink-700 font-semibold mb-1">Auto-Approve PO Threshold (₹ INR)</label>
                  <input
                    type="number"
                    value={autoApproveLimit}
                    onChange={(e) => setAutoApproveLimit(e.target.value)}
                    className="w-full px-3 py-1.5 rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
                  />
                  <span className="text-[11px] text-ink-400">Replenishment orders below this value can be expedited without Tier-3 approval.</span>
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-ink-700 font-semibold mb-1">Transfer-First Decision Policy</label>
                  <select
                    value={transferFirstPolicy}
                    onChange={(e) => setTransferFirstPolicy(e.target.value)}
                    className="w-full px-3 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600 font-medium"
                  >
                    <option value="Enabled">Enabled (Prioritize Inter-DC FEFO Transfers over New Procurement)</option>
                    <option value="Disabled">Disabled (Issue Purchase Orders directly to Central Suppliers)</option>
                  </select>
                  <span className="text-[11px] text-ink-400">When enabled, the replenishment engine scans excess network inventory before creating POs.</span>
                </div>
              </div>

              <div className="pt-3 border-t border-ink-100 flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-1.5 px-4 py-2 bg-forest-700 hover:bg-forest-600 text-white rounded text-[12.5px] font-semibold transition-colors shadow-sm cursor-pointer disabled:opacity-50"
                >
                  <Save size={14} />
                  <span>{saving ? 'Persisting to PostgreSQL...' : 'Save Parameters'}</span>
                </button>
              </div>
            </form>
          )}

          {/* Tab 2: Supplier Management */}
          {active === 'Suppliers' && (
            <div className="space-y-5 text-[12.5px]">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-ink-100">
                <div>
                  <h3 className="text-[15px] font-bold text-ink-900 flex items-center gap-1.5">
                    <Truck size={16} className="text-forest-700" /> Pharmaceutical Supplier Directory
                  </h3>
                  <p className="text-[11.5px] text-ink-500">Add, configure, and remove authorized medicine manufacturers & logistics vendors in PostgreSQL.</p>
                </div>
                <span className="text-[11px] bg-forest-100 text-forest-900 px-2.5 py-0.5 rounded font-bold self-start sm:self-auto">
                  {suppliers.length} Registered {suppliers.length === 1 ? 'Supplier' : 'Suppliers'}
                </span>
              </div>

              {suppActionError && (
                <div className="p-2.5 rounded bg-brick-100 border border-brick-600/30 text-brick-700 flex items-center gap-2 animate-fadeIn">
                  <AlertCircle size={14} className="shrink-0" />
                  <span>{suppActionError}</span>
                </div>
              )}

              {suppActionSuccess && (
                <div className="p-2.5 rounded bg-forest-100 border border-forest-600/30 text-forest-800 font-semibold flex items-center gap-2 animate-fadeIn">
                  <Check size={14} className="shrink-0" />
                  <span>{suppActionSuccess}</span>
                </div>
              )}

              {/* Add New Supplier Form */}
              <form onSubmit={handleAddSupplier} className="p-4 bg-cream-100/70 rounded-lg border border-ink-100 space-y-3">
                <div className="font-semibold text-ink-900 flex items-center gap-1.5">
                  <Plus size={14} className="text-forest-700" /> Add New Supplier / Vendor
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-medium text-ink-700 mb-1">Supplier Name *</label>
                    <input
                      type="text"
                      placeholder="e.g. Cipla Direct"
                      value={suppName}
                      onChange={(e) => setSuppName(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded border border-ink-200 bg-white text-[12px] focus:outline-none focus:border-forest-600"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-ink-700 mb-1">Contact Email</label>
                    <input
                      type="email"
                      placeholder="e.g. supply@cipla.com"
                      value={suppEmail}
                      onChange={(e) => setSuppEmail(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded border border-ink-200 bg-white text-[12px] focus:outline-none focus:border-forest-600"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-ink-700 mb-1">Contact Phone</label>
                    <input
                      type="text"
                      placeholder="e.g. +91 98200 55443"
                      value={suppPhone}
                      onChange={(e) => setSuppPhone(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded border border-ink-200 bg-white text-[12px] focus:outline-none focus:border-forest-600"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-ink-700 mb-1">Lead Time (Days)</label>
                    <input
                      type="number"
                      min="1"
                      max="60"
                      placeholder="e.g. 5"
                      value={suppLeadTime}
                      onChange={(e) => setSuppLeadTime(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded border border-ink-200 bg-white text-[12px] focus:outline-none focus:border-forest-600"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-[11px] font-medium text-ink-700 mb-1">Therapeutic Categories Supplied</label>
                    <input
                      type="text"
                      placeholder="e.g. Analgesics, Antibiotics, Diabetes Care"
                      value={suppCategory}
                      onChange={(e) => setSuppCategory(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded border border-ink-200 bg-white text-[12px] focus:outline-none focus:border-forest-600"
                    />
                  </div>
                </div>
                <div className="flex justify-end pt-1">
                  <button
                    type="submit"
                    disabled={addingSupplier}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded text-[12px] font-semibold transition-colors shadow-xs cursor-pointer disabled:opacity-50"
                  >
                    <Plus size={14} />
                    <span>{addingSupplier ? 'Registering...' : 'Register Supplier in PostgreSQL'}</span>
                  </button>
                </div>
              </form>

              {/* Suppliers Table */}
              <div className="space-y-2">
                <div className="font-semibold text-ink-900">Current Registered Suppliers</div>
                {loadingSuppliers ? (
                  <div className="py-6 text-center text-ink-400 text-[12px]">Loading suppliers from database...</div>
                ) : suppliers.length === 0 ? (
                  <EmptyState title="No Suppliers Registered" description="Use the form above to add authorized suppliers." />
                ) : (
                  <div className="overflow-x-auto border border-ink-100 rounded-lg">
                    <table className="w-full text-left text-[12px]">
                      <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                        <tr>
                          <th className="py-2.5 px-3">Supplier Name</th>
                          <th className="py-2.5 px-3">Categories</th>
                          <th className="py-2.5 px-3">Contact</th>
                          <th className="py-2.5 px-3">Lead Time</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-ink-100">
                        {suppliers.map((s) => (
                          <tr key={s.id || s.name} className="hover:bg-cream-100/60 transition-colors">
                            <td className="py-2.5 px-3">
                              <div className="font-semibold text-ink-900">{s.name}</div>
                              <div className="text-[10px] text-ink-400 font-mono">{s.id}</div>
                            </td>
                            <td className="py-2.5 px-3 text-ink-700 font-medium">
                              {s.category || 'General Pharmaceuticals'}
                            </td>
                            <td className="py-2.5 px-3 text-ink-600">
                              <div>{s.contact_email || '—'}</div>
                              <div className="text-[10.5px] text-ink-400 font-mono">{s.contact_phone || ''}</div>
                            </td>
                            <td className="py-2.5 px-3 font-mono font-medium text-ink-800">
                              {s.lead_time_days || 5} days
                            </td>
                            <td className="py-2.5 px-3">
                              <Badge tone={s.status === 'Active' ? 'good' : 'neutral'}>{s.status || 'Active'}</Badge>
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <button
                                onClick={() => handleDeleteSupplier(s.id, s.name)}
                                className="p-1.5 text-brick-600 hover:bg-brick-100 rounded border border-brick-200 transition-colors cursor-pointer"
                                title={`Remove ${s.name} from database`}
                              >
                                <Trash2 size={13} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab 3: Users & Roles */}
          {active === 'Users & Roles' && (
            <div className="space-y-4">
              <h3 className="text-[15px] font-bold text-ink-900 pb-2 border-b border-ink-100">
                Active Stakeholders & Role Permissions
              </h3>
              <table className="w-full text-left text-[12.5px]">
                <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                  <tr>
                    <th className="py-2.5 px-3">Name</th>
                    <th className="py-2.5 px-3">Email</th>
                    <th className="py-2.5 px-3">Role</th>
                    <th className="py-2.5 px-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {users.map((u, i) => (
                    <tr key={i} className="hover:bg-cream-100/60">
                      <td className="py-2.5 px-3 font-semibold text-ink-900">{u.name}</td>
                      <td className="py-2.5 px-3 text-ink-500 font-mono">{u.email}</td>
                      <td className="py-2.5 px-3 text-ink-800 font-medium">{u.role}</td>
                      <td className="py-2.5 px-3 text-right">
                        <Badge tone={u.status === 'Active' ? 'good' : 'neutral'}>{u.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 4: Audit Logs */}
          {active === 'Audit Logs' && (
            <div className="space-y-4">
              <h3 className="text-[15px] font-bold text-ink-900 pb-2 border-b border-ink-100">
                Live System Audit Trail
              </h3>
              <table className="w-full text-left text-[12px]">
                <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                  <tr>
                    <th className="py-2.5 px-3">Action Event</th>
                    <th className="py-2.5 px-3">User / System</th>
                    <th className="py-2.5 px-3 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {audit_logs.map((log, i) => (
                    <tr key={i} className="hover:bg-cream-100/60">
                      <td className="py-2.5 px-3 text-ink-900 font-medium">{log.action}</td>
                      <td className="py-2.5 px-3 text-forest-800">{log.user}</td>
                      <td className="py-2.5 px-3 text-right font-mono text-ink-400">{log.time}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 5: System Architecture */}
          {active === 'System' && (
            <div className="space-y-3 text-[12.5px]">
              <h3 className="text-[15px] font-bold text-ink-900 pb-2 border-b border-ink-100">
                System Runtime Architecture
              </h3>
              <div className="p-3 bg-cream-100 rounded border border-ink-100 space-y-2">
                <div className="flex justify-between">
                  <span className="text-ink-500">Database Engine:</span>
                  <span className="font-mono font-semibold text-ink-900">PostgreSQL / SQLite via Async SQLAlchemy</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">Backend Framework:</span>
                  <span className="font-mono font-semibold text-ink-900">FastAPI + Uvicorn (Asynchronous REST + WebSockets)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">ML Engine:</span>
                  <span className="font-mono font-semibold text-ink-900">scikit-learn RandomForestRegressor + Model Registry</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-500">Frontend Stack:</span>
                  <span className="font-mono font-semibold text-ink-900">React 19 + Vite + TailwindCSS + Recharts</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}