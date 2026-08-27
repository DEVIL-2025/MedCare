export default function LoadingState({ message = 'Loading live data from Control Tower backend...' }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 bg-white rounded-lg border border-ink-100 shadow-card text-center">
      <div className="animate-spin rounded-full h-8 w-8 border-3 border-forest-600 border-t-transparent mb-3" />
      <div className="text-[13px] font-medium text-ink-800">{message}</div>
      <div className="text-[11px] text-ink-400 mt-1">Connecting to Database & SCM Engines</div>
    </div>
  );
}
