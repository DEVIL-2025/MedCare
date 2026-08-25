import { useState } from 'react';
import { Bell, ChevronDown, RefreshCw, LogOut, UserCheck, Building2, Check, Sparkles, ShieldCheck, Shield, Users, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useControlTower } from '../../context/ControlTowerContext';
import { useLiveISTClock } from '../../utils/dateUtils';

export default function Topbar({ title, subtitle }) {
  const navigate = useNavigate();
  const { user, logout, isAdmin } = useAuth();
  const { selectedWarehouse, setSelectedWarehouse, warehouses, activeAlertCount, triggerRefresh } = useControlTower();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [whDropdownOpen, setWhDropdownOpen] = useState(false);
  const { dateString, timeString } = useLiveISTClock(1000);

  async function handleLogout() {
    setDropdownOpen(false);
    await logout();
    navigate('/login');
  }

  const selectedWhObj = warehouses.find(w => w.id === selectedWarehouse);
  const warehouseLabel = selectedWarehouse === 'All' ? 'All Warehouses' : `${selectedWhObj?.name || selectedWarehouse} (${selectedWarehouse})`;

  return (
    <header className="flex items-center justify-between px-6 py-3.5 bg-white border-b border-ink-100 relative z-30">
      <div>
        <h1 className="text-2xl font-semibold text-ink-900 tracking-tight">{title}</h1>
        <p className="text-[13px] text-ink-500">{subtitle}</p>
      </div>
      <div className="flex items-center gap-2.5">
        {/* Live IST System Clock */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-md bg-cream-100 border border-ink-100 text-[12px] font-mono text-ink-700 shadow-sm" title="Live Asia/Kolkata (IST, UTC+05:30) Current Time">
          <Clock size={13} className="text-forest-700 animate-pulse" />
          <span className="font-semibold text-ink-800">{dateString}</span>
          <span className="text-ink-300">|</span>
          <span className="text-forest-800 font-bold">{timeString}</span>
        </div>
        {/* Dynamic Warehouse Selector Dropdown */}
        <div className="relative">
          <button
            onClick={() => setWhDropdownOpen(!whDropdownOpen)}
            className="flex items-center gap-1.5 text-[12.5px] border border-ink-200 rounded-md px-3 py-1.5 text-ink-800 font-medium hover:bg-cream-200 transition-colors cursor-pointer bg-cream-100/60"
          >
            <Building2 size={14} className="text-forest-700" />
            <span>{warehouseLabel}</span>
            <ChevronDown size={13} className="text-ink-500 ml-0.5" />
          </button>

          {whDropdownOpen && (
            <div className="absolute left-0 sm:right-0 sm:left-auto mt-2 w-64 bg-white border border-ink-100 rounded-md shadow-xl py-1 z-50 text-[12px] max-h-72 overflow-y-auto">
              <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-ink-400 border-b border-ink-100 bg-cream-100">
                Filter Network Scope
              </div>
              <button
                onClick={() => { setSelectedWarehouse('All'); setWhDropdownOpen(false); }}
                className={`w-full px-3 py-2 text-left flex items-center justify-between hover:bg-cream-200 cursor-pointer ${selectedWarehouse === 'All' ? 'bg-forest-50 text-forest-800 font-bold' : 'text-ink-700'}`}
              >
                <span>🌐 All Warehouses (Aggregated Rollup)</span>
                {selectedWarehouse === 'All' && <Check size={14} className="text-forest-700" />}
              </button>
              {warehouses.map((w) => (
                <button
                  key={w.id}
                  onClick={() => { setSelectedWarehouse(w.id); setWhDropdownOpen(false); }}
                  className={`w-full px-3 py-2 text-left flex items-center justify-between hover:bg-cream-200 cursor-pointer ${selectedWarehouse === w.id ? 'bg-forest-50 text-forest-800 font-bold' : 'text-ink-700'}`}
                >
                  <div>
                    <div className="font-semibold">{w.name}</div>
                    <div className="text-[10px] text-ink-400 font-mono">{w.id} • {w.region || 'Regional DC'}</div>
                  </div>
                  {selectedWarehouse === w.id && <Check size={14} className="text-forest-700" />}
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={triggerRefresh}
          className="p-1.5 rounded-md border border-ink-100 text-ink-500 hover:bg-cream-200 cursor-pointer transition-colors"
          title="Refresh Real-Time Data"
        >
          <RefreshCw size={15} />
        </button>
        <button
          onClick={() => navigate('/alerts')}
          className="relative p-1.5 rounded-md border border-ink-100 text-ink-500 hover:bg-cream-200 cursor-pointer transition-colors"
          title="System Alerts"
        >
          <Bell size={15} />
          {activeAlertCount > 0 && (
            <span className="absolute -top-1 -right-1 px-1 min-w-3.5 h-3.5 text-[9px] flex items-center justify-center bg-brick-600 text-white font-bold rounded-full animate-pulse">
              {activeAlertCount}
            </span>
          )}
        </button>

        {/* User Profile Header Badge & Menu */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 pl-2.5 border-l border-ink-100 hover:opacity-85 transition-opacity cursor-pointer"
          >
            <div className={`w-7 h-7 rounded-full text-white flex items-center justify-center text-xs font-bold ${
              user?.role === 'ADMIN' ? 'bg-brick-600' : 'bg-forest-700'
            }`}>
              {user?.avatar || 'U'}
            </div>
            <div className="text-[12.5px] leading-tight text-left">
              <div className="text-ink-900 font-semibold">{user?.name || user?.full_name || 'SCM User'}</div>
              <div className="flex items-center gap-1 text-[10.5px]">
                <span className={`font-semibold ${user?.role === 'ADMIN' ? 'text-brick-700 font-bold' : 'text-forest-700'}`}>
                  {user?.role || 'MANAGER'}
                </span>
                <span className="text-ink-400">•</span>
                <span className="text-ink-500">{user?.roleLabel || (user?.role === 'ADMIN' ? 'Administrator' : 'Manager')}</span>
              </div>
            </div>
            <ChevronDown size={12} className="text-ink-400" />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-52 bg-white border border-ink-100 rounded-md shadow-xl py-1 z-50 text-[12px]">
              <div className="px-3 py-2 border-b border-ink-100 bg-cream-100/60">
                <div className="font-semibold text-ink-900">{user?.full_name || user?.name}</div>
                <div className="text-[10.5px] text-ink-400 font-mono">{user?.email || user?.user_id}</div>
              </div>

              {isAdmin && (
                <button
                  onClick={() => { setDropdownOpen(false); navigate('/users'); }}
                  className="w-full px-3 py-2 text-left text-ink-700 hover:bg-cream-200 flex items-center gap-2 cursor-pointer font-medium text-forest-800"
                >
                  <Users size={14} className="text-forest-700" /> User Management
                </button>
              )}

              <button
                onClick={() => { setDropdownOpen(false); navigate('/settings'); }}
                className="w-full px-3 py-2 text-left text-ink-700 hover:bg-cream-200 flex items-center gap-2 cursor-pointer"
              >
                <UserCheck size={14} /> System Settings & Roles
              </button>

              <button
                onClick={handleLogout}
                className="w-full px-3 py-2 text-left text-brick-600 hover:bg-brick-50 flex items-center gap-2 border-t border-ink-100 cursor-pointer font-medium"
              >
                <LogOut size={14} /> Log Out / Switch User
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}