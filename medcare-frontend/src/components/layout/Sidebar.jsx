import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Package, TrendingUp, Truck, Bell, Building2,
  FileBarChart, GitBranch, Settings as SettingsIcon, Cross, Users,
  Bot, Sparkles
} from 'lucide-react';
import { useControlTower } from '../../context/ControlTowerContext';
import { useAuth } from '../../context/AuthContext';

export default function Sidebar({ isAiAssistantOpen, onToggleAiAssistant }) {
  const { activeAlertCount } = useControlTower();
  const { isAdmin } = useAuth();

  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/inventory', label: 'Inventory', icon: Package },
    { to: '/demand-forecast', label: 'Demand Forecast', icon: TrendingUp },
    { to: '/replenishment', label: 'Replenishment', icon: Truck },
    { to: '/alerts', label: 'Alerts', icon: Bell, badge: activeAlertCount > 0 ? activeAlertCount : null },
    { to: '/warehouses', label: 'Warehouses', icon: Building2 },
    { to: '/reports', label: 'Reports', icon: FileBarChart },
    { to: '/scenario-simulator', label: 'Scenario Simulator', icon: GitBranch },
    ...(isAdmin ? [{ to: '/users', label: 'User Management', icon: Users }] : []),
    { to: '/settings', label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <aside className="w-60 bg-forest-900 text-cream-100 flex flex-col shrink-0">
        <div
        onClick={() => window.location.reload()}
        className="flex items-center gap-2.5 px-5 py-5 border-b border-white/10 cursor-pointer select-none"
      >
        <div className="w-7 h-7 rounded-md bg-forest-500 flex items-center justify-center">
          <Cross size={14} className="text-forest-900" />
        </div>
        <div>
          <div className="text-[14px] font-semibold leading-tight">MedCare Pharma</div>
          <div className="text-[10.5px] text-cream-100/50 tracking-wide">Better Health, Delivered</div>
        </div>
      </div>

      <nav className="flex-1 px-2.5 py-3 space-y-0.5 overflow-y-auto">
        {navItems.map(({ to, label, icon: Icon, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center justify-between px-2.5 py-2 rounded-md text-[13px] transition-colors border-l-2 ${
                isActive
                  ? 'bg-forest-800 text-white border-forest-500'
                  : 'text-cream-100/65 hover:bg-forest-800/60 hover:text-white border-transparent'
              }`
            }
          >
            <span className="flex items-center gap-2.5">
              <Icon size={15} />
              {label}
            </span>
            {badge && <span className="text-[10px] bg-brick-600 text-white rounded px-1.5 py-0.5">{badge}</span>}
          </NavLink>
        ))}

        {/* Standalone Ask SCM AI Navigation Action */}
        <div className="pt-2 mt-2 border-t border-white/10">
          <button
            type="button"
            onClick={onToggleAiAssistant}
            className={`w-full flex items-center justify-between px-2.5 py-2 rounded-md text-[13px] transition-colors border-l-2 text-left cursor-pointer group ${
              isAiAssistantOpen
                ? 'bg-forest-800 text-white border-forest-500 shadow-inner'
                : 'text-cream-100/65 hover:bg-forest-800/60 hover:text-white border-transparent'
            }`}
            title="Open MedCare AI Assistant"
          >
            <span className="flex items-center gap-2.5">
              <Bot size={15} className={isAiAssistantOpen ? 'text-emerald-400' : 'text-emerald-300/80 group-hover:text-emerald-300'} />
              <span>Ask SCM AI</span>
            </span>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded px-1.5 py-0.5 flex items-center gap-1 font-mono">
              <Sparkles size={9} /> AI
            </span>
          </button>
        </div>
      </nav>
    </aside>
  );
}
