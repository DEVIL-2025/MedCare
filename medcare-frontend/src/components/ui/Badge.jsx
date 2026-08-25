const tones = {
  critical: 'bg-brick-100 text-brick-700',
  warning: 'bg-amber2-100 text-amber2-700',
  medium: 'bg-gold-100 text-gold-700',
  info: 'bg-slate2-100 text-slate2-700',
  good: 'bg-sage-100 text-sage-700',
  neutral: 'bg-ink-100 text-ink-700',
}

export default function Badge({ tone = 'neutral', children }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  )
}