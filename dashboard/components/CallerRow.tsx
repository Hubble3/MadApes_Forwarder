import type { Caller } from '@/lib/api';

function scoreBadge(score: number): { label: string; color: string } {
  if (score >= 90) return { label: 'S+', color: 'text-yellow-400' };
  if (score >= 75) return { label: 'S', color: 'text-green-400' };
  if (score >= 60) return { label: 'A', color: 'text-blue-400' };
  if (score >= 45) return { label: 'B', color: 'text-slate-300' };
  if (score >= 30) return { label: 'C', color: 'text-slate-400' };
  return { label: 'D', color: 'text-red-400' };
}

export default function CallerRow({ caller, rank }: { caller: Caller; rank: number }) {
  const badge = scoreBadge(caller.composite_score);
  const medals: Record<number, string> = { 1: '\u{1F947}', 2: '\u{1F948}', 3: '\u{1F949}' };
  const medal = medals[rank] || `${rank}.`;

  return (
    <div className="bg-[#1e293b] rounded-lg p-3 border border-[#334155] flex items-center gap-4">
      <span className="text-lg w-8 text-center">{medal}</span>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{caller.sender_name}</span>
          <span className={`text-xs font-bold ${badge.color}`}>[{badge.label}]</span>
          <span className="text-xs text-slate-500">Score: {caller.composite_score.toFixed(0)}</span>
        </div>
        <div className="flex gap-4 text-xs text-slate-400 mt-1">
          <span>{caller.total_signals} signals</span>
          <span className="text-green-400">{caller.win_count}W</span>
          <span className="text-red-400">{caller.loss_count}L</span>
          <span>WR: {caller.total_signals > 0 ? ((caller.win_count / (caller.win_count + caller.loss_count)) * 100).toFixed(0) : 0}%</span>
        </div>
      </div>
      <div className="text-right">
        <p className={`text-sm font-medium ${caller.avg_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {caller.avg_return >= 0 ? '+' : ''}{caller.avg_return.toFixed(1)}% avg
        </p>
        <p className="text-xs text-slate-500">
          Best: +{caller.best_return.toFixed(0)}%
        </p>
      </div>
    </div>
  );
}
