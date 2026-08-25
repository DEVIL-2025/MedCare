import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import AssistantDrawer from '../assistant/AssistantDrawer'

const pageMeta = {
  '/': { title: 'Executive Dashboard', subtitle: 'Supply chain control tower' },
  '/inventory': { title: 'Inventory', subtitle: 'Real-time inventory visibility across all warehouses' },
  '/demand-forecast': { title: 'Demand Forecast', subtitle: 'AI-powered demand sensing and forecasting' },
  '/replenishment': { title: 'Replenishment Planning', subtitle: 'Recommendations to keep the right stock at the right place' },
  '/alerts': { title: 'Alerts', subtitle: 'Real-time alerts and notifications' },
  '/warehouses': { title: 'Warehouses', subtitle: 'Monitor performance across all distribution centers' },
  '/reports': { title: 'Reports', subtitle: 'Analytics and insights across inventory and demand' },
  '/scenario-simulator': { title: 'Scenario Simulator', subtitle: 'Model changes and see their impact' },
  '/settings': { title: 'Settings', subtitle: 'Preferences and system configuration' },
}

export default function Layout() {
  const location = useLocation()
  const [assistantOpen, setAssistantOpen] = useState(false)
  const meta = pageMeta[location.pathname] || { title: '', subtitle: '' }

  return (
    <div className="flex h-screen bg-cream">
      <Sidebar onOpenAssistant={() => setAssistantOpen(true)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar
          title={meta.title}
          subtitle={meta.subtitle}
          onOpenAssistant={() => setAssistantOpen(true)}
        />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>

      <AssistantDrawer
        open={assistantOpen}
        onClose={() => setAssistantOpen(false)}
      />
    </div>
  )
}