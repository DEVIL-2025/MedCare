import { Inbox } from 'lucide-react';

export default function EmptyState({ title = 'No records found', description = 'Try adjusting your search criteria or filter options.' }) {
  return (
    <div className="flex flex-col items-center justify-center p-10 bg-white rounded-lg border border-ink-100 text-center">
      <div className="w-10 h-10 rounded-full bg-cream-200 flex items-center justify-center text-ink-400 mb-2">
        <Inbox size={20} />
      </div>
      <div className="text-[13px] font-semibold text-ink-800">{title}</div>
      <div className="text-[11px] text-ink-500 max-w-xs mt-0.5">{description}</div>
    </div>
  );
}
