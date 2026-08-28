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
    <header className="flex items-center justify-between px-6 py-3.5 bg-white border-b border-emerald-500/20 shadow-xs relative z-30">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
          {title}
        </h1>
        <p className="text-[13px] text-gray-500 font-medium">{subtitle}</p>
      </div>
      <div className="flex items-center gap-2.5">
        {/* Live IST System Clock */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50/60 border border-emerald-200/80 text-[12px] font-mono text-gray-800 shadow-xs" title="Live Asia/Kolkata (IST, UTC+05:30) Current Time">
          <Clock size={14} className="text-emerald-700 animate-pulse" />
          <span className="font-semibold text-gray-900">{dateString}</span>
          <span className="text-gray-300">|</span>
          <span className="text-emerald-800 font-bold">{timeString}</span>
        </div>
        {/* Dynamic Warehouse Selector Dropdown */}
        <div className="relative">
          <button
            onClick={() => setWhDropdownOpen(!whDropdownOpen)}
            className="flex items-center gap-1.5 text-[12.5px] border border-gray-200 rounded-lg px-3 py-1.5 text-gray-900 font-semibold hover:bg-emerald-50/50 hover:border-emerald-300 transition-colors cursor-pointer bg-white shadow-xs"
          >
            <Building2 size={14} className="text-emerald-700" />
            <span>{warehouseLabel}</span>
            <ChevronDown size={13} className="text-gray-500 ml-0.5" />
          </button>

          {whDropdownOpen && (
            <div className="absolute left-0 sm:right-0 sm:left-auto mt-2 w-64 bg-white border border-gray-200 rounded-lg shadow-xl py-1 z-50 text-[12px] max-h-72 overflow-y-auto">
              <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400 border-b border-gray-100 bg-gray-50">
                Filter Network Scope
              </div>
              <button
                onClick={() => { setSelectedWarehouse('All'); setWhDropdownOpen(false); }}
                className={`w-full px-3 py-2 text-left flex items-center justify-between hover:bg-emerald-50/60 cursor-pointer ${selectedWarehouse === 'All' ? 'bg-emerald-50 text-emerald-900 font-bold' : 'text-gray-700'}`}
              >
                <span>🌐 All Warehouses (Aggregated Rollup)</span>
                {selectedWarehouse === 'All' && <Check size={14} className="text-emerald-700" />}
              </button>
              {warehouses.map((w) => (
                <button
                  key={w.id}
                  onClick={() => { setSelectedWarehouse(w.id); setWhDropdownOpen(false); }}
                  className={`w-full px-3 py-2 text-left flex items-center justify-between hover:bg-emerald-50/60 cursor-pointer ${selectedWarehouse === w.id ? 'bg-emerald-50 text-emerald-900 font-bold' : 'text-gray-700'}`}
                >
                  <div>
                    <div className="font-semibold">{w.name}</div>
                    <div className="text-[10px] text-gray-400 font-mono">{w.id} • {w.region || 'Regional DC'}</div>
                  </div>
                  {selectedWarehouse === w.id && <Check size={14} className="text-emerald-700" />}
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={triggerRefresh}
          className="p-2 rounded-lg border border-gray-200 text-gray-600 hover:text-emerald-700 hover:bg-emerald-50/60 hover:border-emerald-300 cursor-pointer transition-colors"
          title="Refresh Real-Time Data"
        >
          <RefreshCw size={15} />
        </button>
        <button
          onClick={() => navigate('/alerts')}
          className="relative p-2 rounded-lg border border-gray-200 text-gray-600 hover:text-emerald-700 hover:bg-emerald-50/60 hover:border-emerald-300 cursor-pointer transition-colors"
          title="System Alerts"
        >
          <Bell size={15} />
          {activeAlertCount > 0 && (
            <span className="absolute -top-1 -right-1 px-1.5 min-w-4 h-4 text-[9.5px] flex items-center justify-center bg-brick-600 text-white font-extrabold rounded-full shadow-xs animate-pulse">
              {activeAlertCount}
            </span>
          )}
        </button>

        {/* User Profile Header Badge & Menu */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2.5 pl-3 border-l border-gray-200 hover:opacity-90 transition-all cursor-pointer group"
          >
            {/* Elegant Medical Executive Badge */}
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-700 via-emerald-800 to-forest-900 text-white flex items-center justify-center shadow-xs border border-emerald-600/30 group-hover:border-emerald-500/60 transition-colors">
              {user?.role === 'ADMIN' ? (
                <ShieldCheck size={16} className="text-emerald-300" />
              ) : (
                <UserCheck size={16} className="text-emerald-300" />
              )}
            </div>
            <div className="text-[12.5px] leading-tight text-left">
              <div className="text-gray-900 font-bold tracking-tight">{user?.name || user?.full_name || 'System Administrator'}</div>
              <div className="flex items-center gap-1.5 text-[11px] mt-0.5">
                <span className="font-bold text-emerald-800 bg-emerald-100 border border-emerald-300/80 px-1.5 py-0.2 rounded text-[10px] tracking-wide font-mono">
                  {user?.role || 'ADMIN'}
                </span>
                <span className="text-gray-400">•</span>
                <span className="text-gray-600 font-medium">{user?.roleLabel || (user?.role === 'ADMIN' ? 'Control Tower Lead' : 'Supply Chain Manager')}</span>
              </div>
            </div>
            <ChevronDown size={13} className="text-gray-400 ml-0.5 group-hover:text-gray-700 group-hover:translate-y-0.5 transition-all" />
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