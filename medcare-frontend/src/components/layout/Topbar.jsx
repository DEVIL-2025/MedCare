import { useState } from 'react';
import { Bell, ChevronDown, RefreshCw, LogOut, UserCheck, Building2, Check, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useControlTower } from '../../context/ControlTowerContext';

export default function Topbar({ title, subtitle, onOpenAssistant }) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { selectedWarehouse, setSelectedWarehouse, warehouses, activeAlertCount, triggerRefresh } = useControlTower();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [whDropdownOpen, setWhDropdownOpen] = useState(false);

  function handleLogout() {
    logout();
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
          onClick={onOpenAssistant}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-forest-600/30 bg-forest-50 hover:bg-forest-100 text-forest-800 text-[12px] font-semibold cursor-pointer transition-colors"
          title="Open AI Supply Chain Assistant"
        >
          <Sparkles size={14} className="text-forest-700" />
          <span className="hidden md:inline">AI Assistant</span>
        </button>

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

        {/* User Role Profile Menu */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 pl-2.5 border-l border-ink-100 hover:opacity-80 transition-opacity"
          >
            <div className="w-7 h-7 rounded-full bg-forest-700 text-white flex items-center justify-center text-xs font-bold">
              {user?.avatar || 'P'}
            </div>
            <div className="text-[13px] leading-tight text-left">
              <div className="text-ink-900 font-medium">{user?.name || 'Dr. Aditi Rao'}</div>
              <div className="text-ink-500 text-[11px]">{user?.role || 'Lead Demand Planner'}</div>
            </div>
            <ChevronDown size={12} className="text-ink-400" />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white border border-ink-100 rounded-md shadow-lg py-1 z-50 text-[12px]">
              <button
                onClick={() => { setDropdownOpen(false); navigate('/settings'); }}
                className="w-full px-3 py-2 text-left text-ink-700 hover:bg-cream-200 flex items-center gap-2"
              >
                <UserCheck size={14} /> Profile & Roles
              </button>
              <button
                onClick={handleLogout}
                className="w-full px-3 py-2 text-left text-brick-600 hover:bg-brick-100 flex items-center gap-2 border-t border-ink-100"
              >
                <LogOut size={14} /> Switch User / Log Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}