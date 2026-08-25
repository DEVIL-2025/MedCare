import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Package, TrendingUp, Truck, Bell, Building2, FileBarChart, GitBranch, Settings as SettingsIcon, Cross, Sparkles } from 'lucide-react';
import { useControlTower } from '../../context/ControlTowerContext';

export default function Sidebar({ onOpenAssistant }) {
  const { activeAlertCount } = useControlTower();

  const navItems = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/inventory', label: 'Inventory', icon: Package },
    { to: '/demand-forecast', label: 'Demand Forecast', icon: TrendingUp },
    { to: '/replenishment', label: 'Replenishment', icon: Truck },
    { to: '/alerts', label: 'Alerts', icon: Bell, badge: activeAlertCount > 0 ? activeAlertCount : null },
    { to: '/warehouses', label: 'Warehouses', icon: Building2 },
    { to: '/reports', label: 'Reports', icon: FileBarChart },
    { to: '/scenario-simulator', label: 'Scenario Simulator', icon: GitBranch },
    { to: '/settings', label: 'Settings', icon: SettingsIcon },
  ];
  return (
    <aside className="w-60 bg-forest-900 text-cream-100 flex flex-col shrink-0">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-white/10">
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
      </nav>

      <div className="mx-2.5 mb-3 p-3 rounded-md bg-forest-800/50 border border-white/5">
        <div className="flex items-center gap-1.5 mb-1">
          <Sparkles size={12} className="text-forest-500" />
          <span className="text-[11px] font-medium text-cream-100/80">AI Supply Chain Assistant</span>
        </div>
        <p className="text-[10.5px] text-cream-100/45 mb-2 leading-snug">Ask questions, get insights and recommendations.</p>
        <button
          onClick={onOpenAssistant}
          className="w-full text-[11px] font-medium bg-cream-100/10 text-cream-100/90 rounded px-2 py-1.5 hover:bg-cream-100/15 cursor-pointer transition-colors"
        >
          Ask Assistant
        </button>
      </div>
    </aside>
  )
}