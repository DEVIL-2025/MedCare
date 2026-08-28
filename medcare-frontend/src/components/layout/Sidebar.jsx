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

  const navSections = [
    {
      group: 'Overview',
      items: [
        { to: '/', label: 'Dashboard', icon: LayoutDashboard },
        { to: '/alerts', label: 'Alerts', icon: Bell, badge: activeAlertCount > 0 ? activeAlertCount : null },
      ]
    },
    {
      group: 'Operations',
      items: [
        { to: '/inventory', label: 'Inventory', icon: Package },
        { to: '/demand-forecast', label: 'Demand Forecast', icon: TrendingUp },
        { to: '/replenishment', label: 'Replenishment', icon: Truck },
        { to: '/warehouses', label: 'Warehouses', icon: Building2 },
      ]
    },
    {
      group: 'Analytics & Planning',
      items: [
        { to: '/reports', label: 'Reports', icon: FileBarChart },
        { to: '/scenario-simulator', label: 'Scenario Simulator', icon: GitBranch },
      ]
    },
    {
      group: 'Administration',
      items: [
        ...(isAdmin ? [{ to: '/users', label: 'User Management', icon: Users }] : []),
        { to: '/settings', label: 'Settings', icon: SettingsIcon },
      ]
    }
  ];

  return (
    <aside className="w-60 bg-gradient-to-b from-[#08281E] via-[#0D3B2E] to-[#061D16] text-cream-100 flex flex-col shrink-0 border-r border-emerald-900/40 shadow-xl relative select-none">
      {/* Subtle medical glow accent */}
      <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-emerald-500/10 to-transparent pointer-events-none" />

      <div
        onClick={() => window.location.reload()}
        className="flex items-center gap-2.5 px-5 py-5 border-b border-emerald-500/15 cursor-pointer select-none relative z-10 hover:bg-white/[0.02] transition-colors"
      >
        <div className="w-7 h-7 rounded-md bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-sm shadow-emerald-950/50">
          <Cross size={14} className="text-white fill-white" />
        </div>
        <div>
          <div className="text-[14px] font-semibold leading-tight tracking-tight text-white flex items-center gap-1.5">
            MedCare Pharma
          </div>
          <div className="text-[10.5px] text-emerald-300/70 tracking-wide font-medium">Control Tower Platform</div>
        </div>
      </div>

      <nav className="flex-1 px-2.5 py-3 space-y-4 overflow-y-auto relative z-10">
        {navSections.map((section, sIdx) => (
          <div key={section.group} className="space-y-1">
            <div className="px-3 pt-1 text-[11px] font-bold text-emerald-200/85 tracking-wide flex items-center gap-2">
              <span>{section.group}</span>
              <span className="flex-1 h-[1px] bg-emerald-700/30"></span>
            </div>
            <div className="space-y-1">
              {section.items.map(({ to, label, icon: Icon, badge }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3 py-2 rounded-lg text-[13px] tracking-tight transition-all duration-200 ${
                      isActive
                        ? 'bg-gradient-to-r from-emerald-600/40 to-emerald-700/25 text-white font-bold shadow-sm border border-emerald-400/40'
                        : 'text-emerald-50/90 font-semibold hover:bg-emerald-800/40 hover:text-white border border-transparent'
                    }`
                  }
                >
                  <span className="flex items-center gap-2.5">
                    <Icon size={15.5} className="opacity-95" />
                    <span>{label}</span>
                  </span>
                  {badge && (
                    <span className="text-[10px] font-extrabold bg-brick-600 text-white rounded px-1.5 py-0.5 shadow-sm animate-pulse">
                      {badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}

        {/* Standalone Ask SCM AI Navigation Action */}
        <div className="pt-2 border-t border-emerald-500/20">
          <button
            type="button"
            onClick={onToggleAiAssistant}
            className={`w-full flex items-center justify-between px-3 py-2.2 rounded-lg text-[13px] font-semibold tracking-tight transition-all duration-200 text-left cursor-pointer group ${
              isAiAssistantOpen
                ? 'bg-gradient-to-r from-emerald-600/40 to-emerald-700/25 text-white font-bold shadow-sm border border-emerald-400/40'
                : 'text-emerald-50/90 hover:bg-emerald-800/40 hover:text-white border border-transparent'
            }`}
            title="Open MedCare AI Assistant"
          >
            <span className="flex items-center gap-2.5">
              <Bot size={15.5} className={isAiAssistantOpen ? 'text-emerald-300' : 'text-emerald-300 group-hover:text-emerald-200'} />
              <span>Ask SCM AI</span>
            </span>
            <span className="text-[9.5px] font-bold bg-emerald-400/25 text-emerald-200 border border-emerald-400/40 rounded px-1.5 py-0.5 flex items-center gap-1 font-mono">
              <Sparkles size={9} /> AI
            </span>
          </button>
        </div>
      </nav>
    </aside>
  );
}
