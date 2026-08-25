import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorState({ message = 'Unable to fetch live data from server.', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 bg-brick-100/40 rounded-lg border border-brick-600/30 text-center">
      <div className="w-10 h-10 rounded-full bg-brick-100 flex items-center justify-center text-brick-600 mb-2.5">
        <AlertCircle size={20} />
      </div>
      <div className="text-[14px] font-semibold text-ink-900 mb-1">Backend Connection Error</div>
      <div className="text-[12px] text-ink-600 max-w-sm mb-4">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3.5 py-1.5 bg-forest-700 hover:bg-forest-600 text-white rounded-md text-[12px] font-medium transition-colors shadow-sm"
        >
          <RefreshCw size={13} />
          Retry Request
        </button>
      )}
    </div>
  );
}
