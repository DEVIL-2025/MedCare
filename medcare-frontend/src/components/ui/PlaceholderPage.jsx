export default function PlaceholderPage({ icon: Icon, title, note }) {
  return (
    <div className="bg-white rounded-xl border border-ink-100 shadow-card p-12 flex flex-col items-center justify-center text-center min-h-[400px]">
      {Icon && (
        <div className="w-14 h-14 rounded-full bg-forest-100 flex items-center justify-center mb-4">
          <Icon size={24} className="text-forest-700" />
        </div>
      )}
      <h2 className="font-heading text-xl text-ink-900 mb-2">{title}</h2>
      <p className="text-sm text-ink-500 max-w-md">{note}</p>
    </div>
  )
}