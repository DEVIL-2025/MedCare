import { useState, useEffect } from 'react';
import {
  Users, UserPlus, Shield, ShieldCheck, ShieldAlert, KeyRound, Lock,
  Search, RefreshCw, Check, X, AlertCircle, Edit, Power, FileClock,
  Copy, Eye, EyeOff, Sparkles, Filter
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import Badge from '../components/ui/Badge';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import Modal from '../components/ui/Modal';
import { formatDateTime } from '../utils/dateUtils';

export default function UserManagement() {
  const { user: currentAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState('users'); // 'users' or 'audit'

  // Users state
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [userError, setUserError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('All');

  // Audit logs state
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [auditModuleFilter, setAuditModuleFilter] = useState('All');

  // Modals state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);

  // Form states
  const [createForm, setCreateForm] = useState({
    user_id: '',
    email: '',
    full_name: '',
    role_id: 'MANAGER',
    temporary_password: '',
  });
  const [editForm, setEditForm] = useState({
    full_name: '',
    email: '',
    role_id: 'MANAGER',
    is_active: true,
  });

  const [tempPasswordResult, setTempPasswordResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  function showToast(msg) {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  }

  async function loadUsers() {
    setLoadingUsers(true);
    setUserError(null);
    try {
      const res = await api.getUsers({ search: searchQuery, role: roleFilter });
      setUsers(res || []);
    } catch (err) {
      console.error('Failed to load users:', err);
      setUserError(err.message || 'Unable to retrieve user directory.');
    } finally {
      setLoadingUsers(false);
    }
  }

  async function loadAuditLogs() {
    setLoadingAudit(true);
    try {
      const res = await api.getAuditLogs({ module: auditModuleFilter, limit: 100 });
      setAuditLogs(res.logs || []);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoadingAudit(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, [roleFilter]);

  useEffect(() => {
    if (activeTab === 'audit') {
      loadAuditLogs();
    }
  }, [activeTab, auditModuleFilter]);

  function generateRandomPassword() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*';
    let pwd = '';
    for (let i = 0; i < 12; i++) {
      pwd += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return pwd;
  }

  function handleOpenCreate() {
    setCreateForm({
      user_id: '',
      email: '',
      full_name: '',
      role_id: 'MANAGER',
      temporary_password: generateRandomPassword(),
    });
    setActionError(null);
    setTempPasswordResult(null);
    setCreateModalOpen(true);
  }

  async function handleCreateUser(e) {
    if (e) e.preventDefault();
    setActionLoading(true);
    setActionError(null);

    try {
      const res = await api.createUser(createForm);
      showToast(`User '${res.user.user_id}' created successfully.`);
      setTempPasswordResult({
        user_id: res.user.user_id,
        email: res.user.email,
        password: res.user.temporary_password,
      });
      loadUsers();
    } catch (err) {
      setActionError(err.message || 'Failed to create user.');
    } finally {
      setActionLoading(false);
    }
  }

  function handleOpenEdit(u) {
    setSelectedUser(u);
    setEditForm({
      full_name: u.full_name,
      email: u.email,
      role_id: u.role,
      is_active: u.is_active,
    });
    setActionError(null);
    setEditModalOpen(true);
  }

  async function handleUpdateUser(e) {
    if (e) e.preventDefault();
    if (!selectedUser) return;
    setActionLoading(true);
    setActionError(null);

    try {
      await api.updateUser(selectedUser.id, editForm);
      showToast(`User '${selectedUser.user_id}' updated successfully.`);
      setEditModalOpen(false);
      loadUsers();
    } catch (err) {
      setActionError(err.message || 'Failed to update user.');
    } finally {
      setActionLoading(false);
    }
  }

  function handleOpenReset(u) {
    setSelectedUser(u);
    setTempPasswordResult(null);
    setActionError(null);
    setResetModalOpen(true);
  }

  async function handleResetPassword() {
    if (!selectedUser) return;
    setActionLoading(true);
    setActionError(null);

    try {
      const res = await api.resetUserPassword(selectedUser.id);
      setTempPasswordResult({
        user_id: selectedUser.user_id,
        password: res.temporary_password,
      });
      showToast(`Password reset for '${selectedUser.user_id}'.`);
      loadUsers();
    } catch (err) {
      setActionError(err.message || 'Failed to reset password.');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleToggleStatus(u) {
    if (u.id === currentAdmin?.id) {
      alert('You cannot deactivate your own administrator account.');
      return;
    }
    const confirmMsg = u.is_active
      ? `Are you sure you want to deactivate user '${u.user_id}'? They will be immediately blocked from signing in.`
      : `Activate user account '${u.user_id}'?`;

    if (!window.confirm(confirmMsg)) return;

    try {
      await api.toggleUserStatus(u.id);
      showToast(`User '${u.user_id}' is now ${u.is_active ? 'Deactivated' : 'Active'}.`);
      loadUsers();
    } catch (err) {
      alert(`Status update failed: ${err.message}`);
    }
  }

  function handleCopy(text) {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const filteredUsers = users.filter((u) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      u.full_name.toLowerCase().includes(q) ||
      u.user_id.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-5">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 bg-forest-900 text-white px-4 py-2.5 rounded-lg shadow-xl border border-forest-600 flex items-center gap-2 text-[13px] animate-bounce">
          <Check size={16} className="text-forest-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-white p-4 rounded-lg border border-ink-100 shadow-card flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-forest-700 text-white flex items-center justify-center shadow-sm">
            <ShieldCheck size={22} />
          </div>
          <div>
            <h2 className="text-[17px] font-bold text-ink-900 leading-tight">Admin User Management & RBAC</h2>
            <p className="text-[12px] text-ink-500">
              Provision stakeholders, configure role-based access controls, and audit security events in Database.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('users')}
            className={`px-3 py-1.5 rounded-md text-[12.5px] font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'users' ? 'bg-forest-700 text-white shadow-sm' : 'bg-cream-200 text-ink-700 hover:bg-cream-300'
            }`}
          >
            <Users size={14} /> User Accounts ({users.length})
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`px-3 py-1.5 rounded-md text-[12.5px] font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'audit' ? 'bg-forest-700 text-white shadow-sm' : 'bg-cream-200 text-ink-700 hover:bg-cream-300'
            }`}
          >
            <FileClock size={14} /> Security Audit Trail
          </button>
        </div>
      </div>

      {activeTab === 'users' ? (
        <div className="space-y-4">
          {/* Action Bar */}
          <div className="bg-white p-3 rounded-lg border border-ink-100 shadow-card flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 flex-1">
              <div className="relative flex-1 max-w-sm">
                <Search size={14} className="absolute left-3 top-2.5 text-ink-400" />
                <input
                  type="text"
                  placeholder="Search by name, user ID, or email..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full text-[12.5px] pl-8 pr-3 py-1.5 border border-ink-200 rounded-md focus:outline-none focus:ring-1 focus:ring-forest-600"
                />
              </div>

              <div className="flex items-center gap-1 text-[12px] text-ink-600">
                <Filter size={13} className="text-ink-400" />
                <select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  className="border border-ink-200 rounded-md px-2 py-1.5 text-[12px] bg-white focus:outline-none focus:ring-1 focus:ring-forest-600"
                >
                  <option value="All">All Roles</option>
                  <option value="ADMIN">ADMIN</option>
                  <option value="MANAGER">MANAGER</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={loadUsers}
                className="p-1.5 rounded-md border border-ink-200 hover:bg-cream-200 text-ink-600 transition-colors"
                title="Refresh user list"
              >
                <RefreshCw size={14} />
              </button>
              <button
                onClick={handleOpenCreate}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[12.5px] font-medium shadow-sm transition-colors cursor-pointer"
              >
                <UserPlus size={14} /> Create New User
              </button>
            </div>
          </div>

          {/* User List Table */}
          {loadingUsers ? (
            <LoadingState message="Fetching persistent user accounts from Database..." />
          ) : userError ? (
            <ErrorState message={userError} onRetry={loadUsers} />
          ) : filteredUsers.length === 0 ? (
            <EmptyState
              title="No Users Found"
              description="No user accounts match your search or filter criteria."
              actionLabel="Create User"
              onAction={handleOpenCreate}
            />
          ) : (
            <div className="bg-white rounded-lg border border-ink-100 shadow-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-[12.5px]">
                  <thead>
                    <tr className="bg-cream-100/70 border-b border-ink-100 text-ink-500 text-[11px] uppercase tracking-wider font-semibold">
                      <th className="py-2.5 px-4">User</th>
                      <th className="py-2.5 px-4">User ID</th>
                      <th className="py-2.5 px-4">Role</th>
                      <th className="py-2.5 px-4">Status</th>
                      <th className="py-2.5 px-4">Security Policy</th>
                      <th className="py-2.5 px-4">Last Login</th>
                      <th className="py-2.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100 text-ink-800">
                    {filteredUsers.map((u) => {
                      const isSelf = u.id === currentAdmin?.id;
                      return (
                        <tr key={u.id} className="hover:bg-cream-100/40 transition-colors">
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2.5">
                              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                                u.role === 'ADMIN' ? 'bg-brick-600' : 'bg-forest-700'
                              }`}>
                                {u.full_name.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <div className="font-semibold text-ink-900 flex items-center gap-1.5">
                                  {u.full_name}
                                  {isSelf && (
                                    <span className="text-[10px] bg-forest-100 text-forest-800 px-1.5 py-0.2 rounded font-bold">
                                      You
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-ink-400">{u.email}</div>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4 font-mono text-[12px] text-ink-600">
                            {u.user_id}
                          </td>
                          <td className="py-3 px-4">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold ${
                              u.role === 'ADMIN'
                                ? 'bg-brick-100 text-brick-700 border border-brick-200'
                                : 'bg-forest-100 text-forest-800 border border-forest-200'
                            }`}>
                              {u.role === 'ADMIN' ? <Shield size={11} /> : <ShieldCheck size={11} />}
                              {u.role}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${
                              u.is_active
                                ? 'bg-forest-50 text-forest-700'
                                : 'bg-brick-50 text-brick-600'
                            }`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-forest-600' : 'bg-brick-600'}`} />
                              {u.is_active ? 'Active' : 'Deactivated'}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            {u.must_change_password ? (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10.5px] bg-amber-100 text-amber-800 font-medium">
                                <KeyRound size={11} /> Temp Pwd (Must Change)
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10.5px] bg-forest-100/50 text-forest-700 font-medium">
                                <Lock size={11} /> Password Active
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-ink-500 text-[11.5px]">
                            {formatDateTime(u.last_login_at, { fallback: 'Never' })}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleOpenEdit(u)}
                                className="p-1 rounded text-ink-500 hover:text-forest-700 hover:bg-cream-200 transition-colors"
                                title="Edit User Profile & Role"
                              >
                                <Edit size={14} />
                              </button>
                              <button
                                onClick={() => handleOpenReset(u)}
                                className="p-1 rounded text-ink-500 hover:text-amber-700 hover:bg-amber-100/50 transition-colors"
                                title="Reset User Password"
                              >
                                <KeyRound size={14} />
                              </button>
                              {!isSelf && (
                                <button
                                  onClick={() => handleToggleStatus(u)}
                                  className={`p-1 rounded transition-colors ${
                                    u.is_active
                                      ? 'text-ink-500 hover:text-brick-600 hover:bg-brick-100/50'
                                      : 'text-forest-600 hover:bg-forest-100/50'
                                  }`}
                                  title={u.is_active ? 'Deactivate User Account' : 'Activate User Account'}
                                >
                                  <Power size={14} />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Audit Trail View */
        <div className="space-y-4">
          <div className="bg-white p-3 rounded-lg border border-ink-100 shadow-card flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-semibold text-ink-700">Filter Audit Module:</span>
              <select
                value={auditModuleFilter}
                onChange={(e) => setAuditModuleFilter(e.target.value)}
                className="border border-ink-200 rounded-md px-2 py-1 text-[12px] bg-white focus:outline-none"
              >
                <option value="All">All Modules</option>
                <option value="auth">Authentication (auth)</option>
                <option value="users">User Management (users)</option>
                <option value="inventory">Inventory (inventory)</option>
                <option value="warehouses">Warehouses (warehouses)</option>
                <option value="system">System (system)</option>
              </select>
            </div>
            <button
              onClick={loadAuditLogs}
              className="p-1.5 rounded-md border border-ink-200 hover:bg-cream-200 text-ink-600 transition-colors"
              title="Refresh audit trail"
            >
              <RefreshCw size={14} />
            </button>
          </div>

          {loadingAudit ? (
            <LoadingState message="Loading persistent security audit logs from Database..." />
          ) : auditLogs.length === 0 ? (
            <EmptyState
              title="No Audit Records"
              description="No audit trail events match your filter."
            />
          ) : (
            <div className="bg-white rounded-lg border border-ink-100 shadow-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-[12px]">
                  <thead>
                    <tr className="bg-cream-100/70 border-b border-ink-100 text-ink-500 text-[11px] uppercase tracking-wider font-semibold">
                      <th className="py-2.5 px-4">Timestamp</th>
                      <th className="py-2.5 px-4">User</th>
                      <th className="py-2.5 px-4">Action</th>
                      <th className="py-2.5 px-4">Module</th>
                      <th className="py-2.5 px-4">Audit Details</th>
                      <th className="py-2.5 px-4">Client IP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100 text-ink-800">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-cream-100/30">
                        <td className="py-2.5 px-4 text-ink-500 font-mono text-[11.5px]">
                          {formatDateTime(log.created_at || log.timestamp)}
                        </td>
                        <td className="py-2.5 px-4 font-semibold text-ink-900">
                          {log.user_id}
                        </td>
                        <td className="py-2.5 px-4">
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[10.5px] font-mono font-semibold ${
                            log.action.includes('SUCCESS') || log.action.includes('CREATED') || log.action.includes('ACTIVATED')
                              ? 'bg-forest-100 text-forest-800'
                              : log.action.includes('FAILED') || log.action.includes('DEACTIVATED') || log.action.includes('DELETE')
                              ? 'bg-brick-100 text-brick-700'
                              : 'bg-cream-200 text-ink-700'
                          }`}>
                            {log.action}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 uppercase text-[10.5px] font-bold text-ink-500">
                          {log.module}
                        </td>
                        <td className="py-2.5 px-4 text-ink-600 max-w-md truncate">
                          {log.new_value || log.old_value || '-'}
                        </td>
                        <td className="py-2.5 px-4 font-mono text-[11px] text-ink-400">
                          {log.ip_address || '127.0.0.1'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal: Create User */}
      <Modal
        open={createModalOpen}
        onClose={() => { setCreateModalOpen(false); setTempPasswordResult(null); }}
        title="Provision New MedCare SCM User"
      >
        {tempPasswordResult ? (
          <div className="space-y-4">
            <div className="p-3 bg-forest-50 border border-forest-200 rounded-lg text-forest-900 text-[13px]">
              <div className="font-bold flex items-center gap-1.5 mb-1">
                <Check size={16} className="text-forest-600" />
                User Successfully Provisioned!
              </div>
              <p className="text-[12px] text-forest-700">
                Please copy and share the generated temporary credentials with the user. The user will be required to change their password on first login.
              </p>
            </div>

            <div className="bg-cream-100 p-3 rounded-lg border border-ink-100 space-y-2 text-[12.5px]">
              <div>
                <span className="text-ink-400 font-medium">User ID / Username:</span>
                <div className="font-mono font-bold text-ink-900">{tempPasswordResult.user_id}</div>
              </div>
              <div>
                <span className="text-ink-400 font-medium">Email:</span>
                <div className="text-ink-900">{tempPasswordResult.email}</div>
              </div>
              <div>
                <span className="text-ink-400 font-medium">Temporary Password:</span>
                <div className="flex items-center justify-between mt-1 bg-white p-2 border border-ink-200 rounded font-mono font-bold text-forest-800 text-[14px]">
                  <span>{tempPasswordResult.password}</span>
                  <button
                    onClick={() => handleCopy(tempPasswordResult.password)}
                    className="flex items-center gap-1 px-2 py-1 bg-forest-700 hover:bg-forest-600 text-white rounded text-[11px] transition-colors"
                  >
                    {copied ? <Check size={12} /> : <Copy size={12} />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </div>
            </div>

            <button
              onClick={() => { setCreateModalOpen(false); setTempPasswordResult(null); }}
              className="w-full py-2 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[13px] font-medium transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={handleCreateUser} className="space-y-3.5 text-[13px]">
            {actionError && (
              <div className="p-2.5 bg-brick-100 text-brick-700 text-[12px] rounded-md border border-brick-200 flex items-center gap-2">
                <AlertCircle size={14} className="shrink-0" />
                <span>{actionError}</span>
              </div>
            )}

            <div>
              <label className="block text-[11.5px] font-semibold text-ink-700">Full Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Priya Sharma"
                value={createForm.full_name}
                onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md focus:outline-none focus:ring-1 focus:ring-forest-600 text-[12.5px]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11.5px] font-semibold text-ink-700">User ID (Login Handle)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. priya.sharma"
                  value={createForm.user_id}
                  onChange={(e) => setCreateForm({ ...createForm, user_id: e.target.value.toLowerCase().replace(/\s+/g, '.') })}
                  className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md font-mono text-[12.5px]"
                />
              </div>

              <div>
                <label className="block text-[11.5px] font-semibold text-ink-700">Role Assignment</label>
                <select
                  value={createForm.role_id}
                  onChange={(e) => setCreateForm({ ...createForm, role_id: e.target.value })}
                  className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md bg-white text-[12.5px]"
                >
                  <option value="MANAGER">MANAGER (Operational SCM)</option>
                  <option value="ADMIN">ADMIN (Full System Access)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-[11.5px] font-semibold text-ink-700">Work Email Address</label>
              <input
                type="email"
                required
                placeholder="e.g. priya.sharma@medcarepharma.com"
                value={createForm.email}
                onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md text-[12.5px]"
              />
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="block text-[11.5px] font-semibold text-ink-700">Auto-Generated Temporary Password</label>
                <button
                  type="button"
                  onClick={() => setCreateForm({ ...createForm, temporary_password: generateRandomPassword() })}
                  className="text-[11px] text-forest-700 hover:underline flex items-center gap-1"
                >
                  <RefreshCw size={11} /> Regenerate
                </button>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="text"
                  required
                  value={createForm.temporary_password}
                  onChange={(e) => setCreateForm({ ...createForm, temporary_password: e.target.value })}
                  className="w-full px-3 py-1.5 border border-ink-200 rounded-md font-mono font-bold text-forest-800 text-[12.5px]"
                />
              </div>
              <p className="text-[11px] text-ink-400 mt-1">
                The account will be created with <code className="font-semibold text-ink-600">must_change_password = true</code>.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-ink-100">
              <button
                type="button"
                onClick={() => setCreateModalOpen(false)}
                className="px-3 py-1.5 border border-ink-200 rounded-md text-ink-600 hover:bg-cream-200 text-[12.5px]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading}
                className="px-4 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[12.5px] font-medium shadow-sm transition-colors"
              >
                {actionLoading ? 'Provisioning...' : 'Provision User'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Modal: Edit User */}
      <Modal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title={`Edit User: ${selectedUser?.user_id || ''}`}
      >
        <form onSubmit={handleUpdateUser} className="space-y-3.5 text-[13px]">
          {actionError && (
            <div className="p-2.5 bg-brick-100 text-brick-700 text-[12px] rounded-md border border-brick-200 flex items-center gap-2">
              <AlertCircle size={14} className="shrink-0" />
              <span>{actionError}</span>
            </div>
          )}

          <div>
            <label className="block text-[11.5px] font-semibold text-ink-700">Full Name</label>
            <input
              type="text"
              required
              value={editForm.full_name}
              onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
              className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md text-[12.5px]"
            />
          </div>

          <div>
            <label className="block text-[11.5px] font-semibold text-ink-700">Email Address</label>
            <input
              type="email"
              required
              value={editForm.email}
              onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
              className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md text-[12.5px]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11.5px] font-semibold text-ink-700">Role</label>
              <select
                value={editForm.role_id}
                onChange={(e) => setEditForm({ ...editForm, role_id: e.target.value })}
                className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md bg-white text-[12.5px]"
              >
                <option value="MANAGER">MANAGER</option>
                <option value="ADMIN">ADMIN</option>
              </select>
            </div>

            <div>
              <label className="block text-[11.5px] font-semibold text-ink-700">Account Status</label>
              <select
                value={editForm.is_active ? 'true' : 'false'}
                onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value === 'true' })}
                disabled={selectedUser?.id === currentAdmin?.id}
                className="w-full mt-1 px-3 py-1.5 border border-ink-200 rounded-md bg-white text-[12.5px]"
              >
                <option value="true">Active</option>
                <option value="false">Deactivated</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-ink-100">
            <button
              type="button"
              onClick={() => setEditModalOpen(false)}
              className="px-3 py-1.5 border border-ink-200 rounded-md text-ink-600 hover:bg-cream-200 text-[12.5px]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={actionLoading}
              className="px-4 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[12.5px] font-medium shadow-sm transition-colors"
            >
              {actionLoading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal: Reset Password */}
      <Modal
        open={resetModalOpen}
        onClose={() => { setResetModalOpen(false); setTempPasswordResult(null); }}
        title={`Reset Password: ${selectedUser?.user_id || ''}`}
      >
        {tempPasswordResult ? (
          <div className="space-y-4">
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-[13px]">
              <div className="font-bold flex items-center gap-1.5 mb-1">
                <KeyRound size={16} className="text-amber-700" />
                Temporary Password Generated!
              </div>
              <p className="text-[12px] text-amber-800">
                The password has been updated in Database. The user will be required to create a new password on their next login.
              </p>
            </div>

            <div className="bg-cream-100 p-3 rounded-lg border border-ink-100 text-[12.5px]">
              <span className="text-ink-400 font-medium">New Temporary Password:</span>
              <div className="flex items-center justify-between mt-1 bg-white p-2 border border-ink-200 rounded font-mono font-bold text-forest-800 text-[14px]">
                <span>{tempPasswordResult.password}</span>
                <button
                  onClick={() => handleCopy(tempPasswordResult.password)}
                  className="flex items-center gap-1 px-2 py-1 bg-forest-700 hover:bg-forest-600 text-white rounded text-[11px] transition-colors"
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>

            <button
              onClick={() => { setResetModalOpen(false); setTempPasswordResult(null); }}
              className="w-full py-2 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[13px] font-medium transition-colors"
            >
              Done
            </button>
          </div>
        ) : (
          <div className="space-y-4 text-[13px]">
            <p className="text-ink-600 text-[12.5px]">
              Are you sure you want to generate a new secure temporary password for user{' '}
              <span className="font-bold text-ink-900">{selectedUser?.full_name}</span> ({selectedUser?.user_id})?
            </p>

            {actionError && (
              <div className="p-2.5 bg-brick-100 text-brick-700 text-[12px] rounded-md border border-brick-200 flex items-center gap-2">
                <AlertCircle size={14} className="shrink-0" />
                <span>{actionError}</span>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-ink-100">
              <button
                type="button"
                onClick={() => setResetModalOpen(false)}
                className="px-3 py-1.5 border border-ink-200 rounded-md text-ink-600 hover:bg-cream-200 text-[12.5px]"
              >
                Cancel
              </button>
              <button
                onClick={handleResetPassword}
                disabled={actionLoading}
                className="px-4 py-1.5 bg-amber-700 hover:bg-amber-600 text-white rounded-md text-[12.5px] font-medium shadow-sm transition-colors"
              >
                {actionLoading ? 'Generating...' : 'Generate New Password'}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
