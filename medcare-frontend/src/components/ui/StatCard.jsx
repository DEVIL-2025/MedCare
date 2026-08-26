const toneMap = {
  forest: { bg: 'bg-forest-100', text: 'text-forest-700' },
  gold: { bg: 'bg-gold-100', text: 'text-gold-700' },
  brick: { bg: 'bg-brick-100', text: 'text-brick-700' },
  critical: { bg: 'bg-brick-100', text: 'text-brick-700' },
  amber2: { bg: 'bg-amber2-100', text: 'text-amber2-700' },
  warning: { bg: 'bg-amber2-100', text: 'text-amber2-700' },
  sage: { bg: 'bg-sage-100', text: 'text-sage-700' },
  good: { bg: 'bg-sage-100', text: 'text-sage-700' },
  slate2: { bg: 'bg-slate2-100', text: 'text-slate2-700' },
  neutral: { bg: 'bg-ink-100', text: 'text-ink-700' },
  info: { bg: 'bg-slate2-100', text: 'text-slate2-700' },
};

export default function StatCard({ icon: Icon, label, value, delta, deltaPositive = true, subtext, tone = 'forest', onClick }) {
  const t = toneMap[tone] || toneMap.forest || { bg: 'bg-forest-100', text: 'text-forest-700' };
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-lg border border-ink-100 p-4 shadow-card transition-all ${
        onClick ? 'cursor-pointer hover:border-forest-500/50 hover:shadow-md' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-xs text-ink-500">{label}</span>
        {Icon && (
          <div className={`w-7 h-7 rounded-md flex items-center justify-center ${t.bg}`}>
            <Icon size={14} className={t.text} />
          </div>
        )}
      </div>
      <div className="text-2xl font-semibold text-ink-900 tracking-tight">{value}</div>
      {delta && <div className={`text-[11px] mt-1 ${deltaPositive ? 'text-sage-600' : 'text-brick-600'}`}>{delta}</div>}
      {subtext && <div className="text-[11px] mt-1 text-ink-400">{subtext}</div>}
    </div>
  );
}