import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Users, Bell, Package, TrendingUp, Truck, ShieldCheck, FileClock, Server, Check, Save } from 'lucide-react';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import { api } from '../api/client';

const navItems = [
  { label: 'Inventory', icon: Package, desc: 'Inventory rules, FEFO threshold and buffers' },
  { label: 'Users & Roles', icon: Users, desc: 'Manage access and active stakeholders' },
  { label: 'Audit Logs', icon: FileClock, desc: 'Live system execution records' },
  { label: 'System', icon: Server, desc: 'Architecture and runtime status' },
];

export default function Settings() {
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

  useEffect(() => {
    loadSettings();
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
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
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
        <p className="text-[12px] text-ink-500">Fine-tune safety stock multipliers, SLA escalation timelines, and role-based access controls.</p>
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
                  <span className="text-[11px] text-ink-400">Added to supplier lead time during demand surge periods.</span>
                </div>

                <div>
                  <label className="block text-ink-700 font-semibold mb-1">Near Expiry Threshold (Days)</label>
                  <input
                    type="number"
                    value={expiryCriticalDays}
                    onChange={(e) => setExpiryCriticalDays(e.target.value)}
                    className="w-full px-3 py-1.5 rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-cream-100/50"
                  />
                  <span className="text-[11px] text-ink-400">Batches below this threshold trigger priority FEFO inter-DC transfer.</span>
                </div>

                <div>
                  <label className="block text-ink-700 font-semibold mb-1">Inter-DC FEFO Transfer Policy</label>
                  <select
                    value={transferFirstPolicy}
                    onChange={(e) => setTransferFirstPolicy(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600"
                  >
                    <option value="Enabled">Enabled (Transfer Surplus Before New PO)</option>
                    <option value="Disabled">Disabled (Direct Vendor Orders Only)</option>
                  </select>
                  <span className="text-[11px] text-ink-400">Enforces network balancing before issuing emergency POs.</span>
                </div>
              </div>

              <div className="pt-3 border-t border-ink-100 flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-1.5 px-4 py-2 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[12.5px] font-semibold transition-colors shadow-sm cursor-pointer disabled:opacity-50"
                >
                  <Save size={14} />
                  {saving ? 'Saving Changes...' : 'Save Parameters'}
                </button>
              </div>
            </form>
          )}

          {/* Tab 2: Users & Roles */}
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

          {/* Tab 3: Audit Logs */}
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

          {/* Tab 4: System Architecture */}
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