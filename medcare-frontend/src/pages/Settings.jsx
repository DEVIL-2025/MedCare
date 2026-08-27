import { useState, useEffect } from 'react';
import {
  Package, Truck, Users, FileClock, Server, Check, Save, Plus, Trash2,
  AlertCircle, Mail, Key, Send, RefreshCw, Radio
} from 'lucide-react';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import { api } from '../api/client';
import { useControlTower } from '../context/ControlTowerContext';
import { formatDateTime } from '../utils/dateUtils';

const navItems = [
  { label: 'Inventory', icon: Package, desc: 'Inventory rules, FEFO threshold and buffers' },
  { label: 'Notifications & Email', icon: Mail, desc: 'Low-stock email alerts, Resend API key, and recipients' },
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

  // Editable parameters (Inventory)
  const [serviceLevel, setServiceLevel] = useState('95');
  const [leadTimeBuffer, setLeadTimeBuffer] = useState('2');
  const [expiryCriticalDays, setExpiryCriticalDays] = useState('30');
  const [autoApproveLimit, setAutoApproveLimit] = useState('100000');
  const [transferFirstPolicy, setTransferFirstPolicy] = useState('Enabled');

  // Email & Notification settings
  const [emailProvider, setEmailProvider] = useState('resend'); // 'resend' | 'smtp'
  const [resendApiKey, setResendApiKey] = useState('');
  const [emailFrom, setEmailFrom] = useState('');
  const [alertRecipientEmail, setAlertRecipientEmail] = useState('');
  const [lowStockAlertsEnabled, setLowStockAlertsEnabled] = useState('Enabled');
  const [smtpHost, setSmtpHost] = useState('');
  const [smtpPort, setSmtpPort] = useState('587');
  const [smtpUser, setSmtpUser] = useState('');
  const [smtpPassword, setSmtpPassword] = useState('');
  const [testingAlert, setTestingAlert] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [emailLogs, setEmailLogs] = useState([]);
  const [loadingEmailLogs, setLoadingEmailLogs] = useState(false);

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

          // Email settings
          if (res.parameters.resend_api_key) setResendApiKey(res.parameters.resend_api_key);
          if (res.parameters.email_from) setEmailFrom(res.parameters.email_from);
          if (res.parameters.alert_recipient_email) setAlertRecipientEmail(res.parameters.alert_recipient_email);
          if (res.parameters.low_stock_alerts_enabled) setLowStockAlertsEnabled(res.parameters.low_stock_alerts_enabled);
          if (res.parameters.smtp_host) setSmtpHost(res.parameters.smtp_host);
          if (res.parameters.smtp_port) setSmtpPort(res.parameters.smtp_port);
          if (res.parameters.smtp_user) setSmtpUser(res.parameters.smtp_user);
          if (res.parameters.smtp_host) setEmailProvider('smtp');
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

  async function loadEmailLogs() {
    setLoadingEmailLogs(true);
    try {
      const res = await api.getNotifications({ channel: 'EMAIL', limit: 10 });
      setEmailLogs(Array.isArray(res) ? res : []);
    } catch (err) {
      console.warn('Failed to load email logs:', err);
    } finally {
      setLoadingEmailLogs(false);
    }
  }

  useEffect(() => {
    loadSettings();
    loadSuppliers();
    loadEmailLogs();
  }, []);

  async function handleSave(e) {
    if (e) e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        service_level_pct: serviceLevel,
        lead_time_buffer_days: leadTimeBuffer,
        expiry_critical_days: expiryCriticalDays,
        auto_approve_threshold_inr: autoApproveLimit,
        transfer_first_policy: transferFirstPolicy,
        resend_api_key: resendApiKey.trim(),
        email_from: emailFrom.trim(),
        alert_recipient_email: alertRecipientEmail.trim(),
        low_stock_alerts_enabled: lowStockAlertsEnabled,
        smtp_host: smtpHost.trim(),
        smtp_port: smtpPort.trim(),
        smtp_user: smtpUser.trim(),
      };
      if (smtpPassword) {
        payload.smtp_password = smtpPassword;
      }

      await api.updateSettings(payload);
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

  async function handleTriggerLowStockCheck() {
    setTestingAlert(true);
    setTestResult(null);
    try {
      const res = await api.triggerLowStockCheck({ force_ignore_cooldown: true });
      setTestResult(res);
      await loadEmailLogs();
      triggerRefresh();
    } catch (err) {
      setTestResult({ success: false, message: `Check failed: ${err.message}` });
    } finally {
      setTestingAlert(false);
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
      setSuppActionSuccess(`Supplier '${suppName.trim()}' added to Database successfully!`);
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
      setSuppActionSuccess(`Supplier '${supplierName}' removed from Database.`);
      await loadSuppliers();
      triggerRefresh();
      setTimeout(() => setSuppActionSuccess(null), 3000);
    } catch (err) {
      setSuppActionError(err.message || 'Failed to remove supplier.');
    }
  }

  if (loading && !data) {
    return <LoadingState message="Loading system configuration parameters from Database..." />;
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
        <p className="text-[12px] text-ink-500">Fine-tune safety stock multipliers, configure low-stock email alerts, manage suppliers, and monitor system audit trails.</p>
      </div>

      {saveSuccess && (
        <div className="p-3 bg-forest-100 border border-forest-600/30 text-forest-900 text-[12.5px] rounded-lg font-medium flex items-center gap-2">
          <Check size={16} className="text-forest-700" />
          Settings successfully updated and persisted to Database!
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
                  <span>{saving ? 'Persisting to Database...' : 'Save Parameters'}</span>
                </button>
              </div>
            </form>
          )}

          {/* Tab 2: Notifications & Low-Stock Email Alert Settings */}
          {active === 'Notifications & Email' && (
            <div className="space-y-5 text-[12.5px]">
              {/* Clean Email Configuration Form */}
              <form onSubmit={handleSave} className="space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-ink-100">
                  <div>
                    <h3 className="text-[15px] font-bold text-ink-900 flex items-center gap-2">
                      <Mail size={16} className="text-forest-700" />
                      <span>Outbound Email & Alert Settings</span>
                    </h3>
                    <p className="text-[11.5px] text-ink-500">Configure email API credentials and automated consolidated low-stock digest triggers.</p>
                  </div>
                  <span className="text-[11px] font-mono bg-forest-100 text-forest-800 px-2.5 py-0.5 rounded font-bold">
                    24h Cooldown Active
                  </span>
                </div>

                {/* Provider Selector */}
                <div className="flex gap-4 p-2.5 bg-cream-100/60 rounded border border-ink-100">
                  <label className="flex items-center gap-2 cursor-pointer font-semibold text-ink-800">
                    <input
                      type="radio"
                      name="provider"
                      value="resend"
                      checked={emailProvider === 'resend'}
                      onChange={() => setEmailProvider('resend')}
                      className="accent-forest-700"
                    />
                    <span>Resend API (HTTP)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer font-semibold text-ink-800">
                    <input
                      type="radio"
                      name="provider"
                      value="smtp"
                      checked={emailProvider === 'smtp'}
                      onChange={() => setEmailProvider('smtp')}
                      className="accent-forest-700"
                    />
                    <span>Standard SMTP Server (Gmail / Outlook / Custom)</span>
                  </label>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {emailProvider === 'resend' && (
                    <div className="sm:col-span-2">
                      <label className="block text-ink-700 font-semibold mb-1 flex items-center gap-1.5">
                        <Key size={13} className="text-forest-700" />
                        <span>Resend API Key</span>
                      </label>
                      <input
                        type="password"
                        placeholder="re_xxxxxxxxxxxxxxxxxxxxxxxx"
                        value={resendApiKey}
                        onChange={(e) => setResendApiKey(e.target.value)}
                        className="w-full px-3 py-2 rounded border border-ink-200 font-mono text-[12px] focus:outline-none focus:border-forest-600 bg-white"
                      />
                      <span className="text-[11px] text-ink-400">
                        Enter your Resend API key. Note: Free tier accounts without verified domains require sending from <code>onboarding@resend.dev</code> to the registered account email.
                      </span>
                    </div>
                  )}

                  {emailProvider === 'smtp' && (
                    <>
                      <div>
                        <label className="block text-ink-700 font-semibold mb-1">SMTP Host</label>
                        <input
                          type="text"
                          placeholder="smtp.gmail.com"
                          value={smtpHost}
                          onChange={(e) => setSmtpHost(e.target.value)}
                          className="w-full px-3 py-1.5 rounded border border-ink-200 bg-white font-mono text-[12px]"
                        />
                      </div>
                      <div>
                        <label className="block text-ink-700 font-semibold mb-1">SMTP Port</label>
                        <input
                          type="text"
                          placeholder="587"
                          value={smtpPort}
                          onChange={(e) => setSmtpPort(e.target.value)}
                          className="w-full px-3 py-1.5 rounded border border-ink-200 bg-white font-mono text-[12px]"
                        />
                      </div>
                      <div>
                        <label className="block text-ink-700 font-semibold mb-1">SMTP Username / Email</label>
                        <input
                          type="text"
                          placeholder="your_email@gmail.com"
                          value={smtpUser}
                          onChange={(e) => setSmtpUser(e.target.value)}
                          className="w-full px-3 py-1.5 rounded border border-ink-200 bg-white font-mono text-[12px]"
                        />
                      </div>
                      <div>
                        <label className="block text-ink-700 font-semibold mb-1">SMTP App Password</label>
                        <input
                          type="password"
                          placeholder="••••••••••••••••"
                          value={smtpPassword}
                          onChange={(e) => setSmtpPassword(e.target.value)}
                          className="w-full px-3 py-1.5 rounded border border-ink-200 bg-white font-mono text-[12px]"
                        />
                      </div>
                    </>
                  )}

                  <div>
                    <label className="block text-ink-700 font-semibold mb-1">Sender Email / Address (From)</label>
                    <input
                      type="text"
                      value={emailFrom}
                      onChange={(e) => setEmailFrom(e.target.value)}
                      placeholder={emailProvider === 'resend' ? 'MedCare SCM <onboarding@resend.dev>' : 'MedCare SCM <alerts@yourdomain.com>'}
                      className="w-full px-3 py-1.5 rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-white font-mono text-[12px]"
                    />
                    <span className="text-[11px] text-ink-400">
                      {emailProvider === 'resend' ? 'Must be onboarding@resend.dev or your verified custom domain.' : 'Sender address used for SMTP.'}
                    </span>
                  </div>

                  <div>
                    <label className="block text-ink-700 font-semibold mb-1">Alert Recipient Email(s)</label>
                    <input
                      type="email"
                      value={alertRecipientEmail}
                      onChange={(e) => setAlertRecipientEmail(e.target.value)}
                      placeholder="e.g. planner@hospital.org, user@domain.com"
                      className="w-full px-3 py-1.5 rounded border border-ink-200 focus:outline-none focus:border-forest-600 bg-white font-mono text-[12px]"
                    />
                    <span className="text-[11px] text-ink-400 font-medium text-forest-800">
                      Low-stock consolidated digest alerts will be sent exclusively to this address.
                    </span>
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-ink-700 font-semibold mb-1">Automated Low-Stock Trigger</label>
                    <select
                      value={lowStockAlertsEnabled}
                      onChange={(e) => setLowStockAlertsEnabled(e.target.value)}
                      className="w-full px-3 py-1.5 rounded border border-ink-200 bg-white text-ink-800 focus:outline-none focus:border-forest-600 font-medium"
                    >
                      <option value="Enabled">Enabled (Automatically send consolidated digest on outbound transactions & daily check)</option>
                      <option value="Disabled">Disabled (Suppress outbound digest emails)</option>
                    </select>
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex items-center gap-1.5 px-4 py-2 bg-forest-700 hover:bg-forest-600 text-white rounded text-[12.5px] font-semibold transition-colors shadow-sm cursor-pointer disabled:opacity-50"
                  >
                    <Save size={14} />
                    <span>{saving ? 'Saving Settings...' : 'Save Email Settings'}</span>
                  </button>
                </div>
              </form>

              {/* Manual Trigger & Test Panel */}
              <div className="p-4 bg-cream-100/70 border border-ink-100 rounded-lg space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="font-bold text-ink-900">Execute Dynamic Low-Stock Scan (Consolidated Digest)</h4>
                    <p className="text-[11.5px] text-ink-500">Scans all SKU-DC nodes in Database and dispatches a single consolidated digest email.</p>
                  </div>
                  <button
                    type="button"
                    onClick={handleTriggerLowStockCheck}
                    disabled={testingAlert}
                    className="flex items-center gap-1.5 px-3.5 py-2 bg-forest-800 hover:bg-forest-700 text-white rounded text-[12px] font-semibold transition-colors shadow-xs cursor-pointer self-start sm:self-auto disabled:opacity-50"
                  >
                    {testingAlert ? <RefreshCw size={13} className="animate-spin" /> : <Send size={13} />}
                    <span>{testingAlert ? 'Scanning Database...' : 'Run Low-Stock Email Check Now'}</span>
                  </button>
                </div>

                {testResult && (
                  <div className={`p-3 rounded text-[12px] font-medium border ${testResult.success ? 'bg-forest-100 border-forest-500/40 text-forest-900' : 'bg-brick-100 border-brick-500/40 text-brick-900'}`}>
                    <div className="font-bold mb-1">{testResult.message}</div>
                    {testResult.alerts && testResult.alerts.length > 0 && (
                      <div className="mt-2 space-y-1">
                        <div className="text-[11px] font-semibold text-forest-800 flex items-center justify-between">
                          <span>{testResult.alerts[0].digest_subject} &bull; Destination: <strong>{testResult.alerts[0].recipients?.join(', ')}</strong></span>
                          <span className={`px-2 py-0.5 rounded text-[10.5px] font-bold ${
                            testResult.alerts[0].delivery_status === 'SENT' || testResult.alerts[0].delivery_status === 'DELIVERED'
                              ? 'bg-forest-200 text-forest-900'
                              : testResult.alerts[0].delivery_status === 'FAILED'
                              ? 'bg-brick-200 text-brick-900'
                              : 'bg-cream-300 text-ink-800'
                          }`}>
                            {testResult.alerts[0].delivery_status === 'PARTIAL' ? 'SENT (PARTIAL)' : testResult.alerts[0].delivery_status} ({testResult.alerts[0].provider || 'simulated'})
                          </span>
                        </div>
                        {testResult.alerts[0].items && (
                          <div className="overflow-x-auto border border-ink-100 rounded bg-white mt-1">
                            <table className="w-full text-left text-[11px]">
                              <thead className="bg-cream-200/70 text-ink-600 font-semibold border-b border-ink-100">
                                <tr>
                                  <th className="p-1.5">Product & SKU</th>
                                  <th className="p-1.5">DC</th>
                                  <th className="p-1.5 text-right">Available</th>
                                  <th className="p-1.5 text-right">Reorder Pt</th>
                                  <th className="p-1.5 text-right">Deficit</th>
                                  <th className="p-1.5 text-center">Status</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-ink-100">
                                {testResult.alerts[0].items.map((it, idx) => (
                                  <tr key={idx} className="hover:bg-cream-100/50">
                                    <td className="p-1.5 font-medium text-ink-900">{it.product_name} <span className="font-mono text-ink-400">({it.sku})</span></td>
                                    <td className="p-1.5 font-bold text-ink-800">{it.warehouse_id}</td>
                                    <td className="p-1.5 text-right font-bold text-brick-700">{it.available_stock}</td>
                                    <td className="p-1.5 text-right text-ink-700">{it.reorder_point}</td>
                                    <td className="p-1.5 text-right font-bold text-brick-700">-{it.deficit}</td>
                                    <td className="p-1.5 text-center"><Badge tone="critical">{it.status}</Badge></td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Recent Email Alert Logs Table */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-ink-900">Recent Dispatched Email Notifications</h4>
                  <button
                    onClick={loadEmailLogs}
                    className="text-[11.5px] text-forest-700 hover:underline flex items-center gap-1"
                  >
                    <RefreshCw size={11} className={loadingEmailLogs ? "animate-spin" : ""} /> Refresh Logs
                  </button>
                </div>
                {emailLogs.length === 0 ? (
                  <div className="p-4 bg-white rounded border border-ink-100 text-center text-ink-400 text-[12px]">
                    No email notifications logged in Database yet. Run a check above to test.
                  </div>
                ) : (
                  <div className="overflow-x-auto border border-ink-100 rounded-lg">
                    <table className="w-full text-left text-[12px]">
                      <thead className="bg-cream-200/60 text-ink-500 font-semibold border-b border-ink-100">
                        <tr>
                          <th className="py-2.5 px-3">Subject / Alert</th>
                          <th className="py-2.5 px-3">Recipient</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3 text-right">Timestamp (IST)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-ink-100 bg-white">
                        {emailLogs.map((log) => (
                          <tr key={log.id} className="hover:bg-cream-100/60">
                            <td className="py-2.5 px-3 font-semibold text-ink-900">
                              <div>{log.subject}</div>
                              <div className="text-[10.5px] text-ink-400 font-mono">{log.alertId}</div>
                            </td>
                            <td className="py-2.5 px-3 text-ink-600 font-mono text-[11.5px]">{log.recipient}</td>
                            <td className="py-2.5 px-3">
                              <Badge tone={log.status === 'SENT' || log.status === 'DELIVERED' ? 'good' : (log.status === 'FAILED' ? 'critical' : 'neutral')}>
                                {log.status === 'PARTIAL' ? 'SENT (PARTIAL)' : log.status}
                              </Badge>
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono text-ink-500 text-[11.5px]">
                              {formatDateTime(log.iso || log.timestamp, { includeSeconds: true })}
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

          {/* Tab 3: Suppliers */}
          {active === 'Suppliers' && (
            <div className="space-y-5 text-[12.5px]">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-ink-100">
                <div>
                  <h3 className="text-[15px] font-bold text-ink-900 flex items-center gap-1.5">
                    <Truck size={16} className="text-forest-700" /> Pharmaceutical Supplier Directory
                  </h3>
                  <p className="text-[11.5px] text-ink-500">Add, configure, and remove authorized medicine manufacturers & logistics vendors in Database.</p>
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
                    <span>{addingSupplier ? 'Registering...' : 'Register Supplier in Database'}</span>
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

          {/* Tab 4: Users & Roles */}
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

          {/* Tab 5: Audit Logs */}
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
                    <th className="py-2.5 px-3 text-right">Timestamp (IST)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {audit_logs.map((log, i) => (
                    <tr key={i} className="hover:bg-cream-100/60">
                      <td className="py-2.5 px-3 text-ink-900 font-medium">{log.action}</td>
                      <td className="py-2.5 px-3 text-forest-800">{log.user}</td>
                      <td className="py-2.5 px-3 text-right font-mono text-ink-500 text-[11.5px]">
                        {formatDateTime(log.iso || log.time, { includeSeconds: true })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 6: System Architecture */}
          {active === 'System' && (
            <div className="space-y-3 text-[12.5px]">
              <h3 className="text-[15px] font-bold text-ink-900 pb-2 border-b border-ink-100">
                System Runtime Architecture
              </h3>
              <div className="p-3 bg-cream-100 rounded border border-ink-100 space-y-2">
                <div className="flex justify-between">
                  <span className="text-ink-500">Database Engine:</span>
                  <span className="font-mono font-semibold text-ink-900">PostgreSQL (Neon Lakebase) via Async SQLAlchemy + asyncpg</span>
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