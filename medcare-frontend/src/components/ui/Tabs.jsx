export default function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto">
      {tabs.map((t) => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={`px-3 py-2 text-[13px] font-medium border-b-2 whitespace-nowrap transition-colors ${
            active === t ? 'border-forest-600 text-forest-700' : 'border-transparent text-ink-500 hover:text-ink-900'
          }`}
        >
          {t}
        </button>
      ))}
    </div>
  )
}