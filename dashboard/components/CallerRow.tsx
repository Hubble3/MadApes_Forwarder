'use client';
import type { Caller } from '@/lib/api';
import clsx from 'clsx';

function scoreBadge(score: number): { label: string; color: string; bg: string } {
  if (score >= 90) return { label: 'S+', color: 'text-amber-400', bg: 'bg-amber-500/15' };
  if (score >= 75) return { label: 'S', color: 'text-emerald-400', bg: 'bg-emerald-500/15' };
  if (score >= 60) return { label: 'A', color: 'text-blue-400', bg: 'bg-blue-500/15' };
  if (score >= 45) return { label: 'B', color: 'text-slate-300', bg: 'bg-slate-500/15' };
  if (score >= 30) return { label: 'C', color: 'text-slate-400', bg: 'bg-slate-500/10' };
  return { label: 'D', color: 'text-red-400', bg: 'bg-red-500/10' };
}

const medals: Record<number, { emoji: string; glow: string }> = {
  1: { emoji: '#1', glow: 'text-amber-400' },
  2: { emoji: '#2', glow: 'text-slate-300' },
  3: { emoji: '#3', glow: 'text-orange-400' },
};

export default function CallerRow({ caller, rank }: { caller: Caller; rank: number }) {
  const badge = scoreBadge(caller.composite_score);
  const medal = medals[rank];
  const winRate = caller.win_count + caller.loss_count > 0
    ? ((caller.win_count / (caller.win_count + caller.loss_count)) * 100).toFixed(0)
    : '0';

  return (
    <div
      className={clsx(
        'group relative overflow-hidden rounded-xl border bg-dark-700 p-4 transition-all duration-300',
        'hover:bg-dark-600 hover:border-dark-300',
        rank <= 3 ? 'border-dark-400/80' : 'border-dark-400/30',
      )}
    >
      {/* Rank indicator */}
      {rank <= 3 && (
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-amber-500/60 to-transparent" />
      )}

      <div className="flex items-center gap-4">
        {/* Rank */}
        <div className={clsx(
          'w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm shrink-0',
          medal ? `${medal.glow} bg-dark-500` : 'text-slate-500 bg-dark-500'
        )}>
          {medal ? medal.emoji : `#${rank}`}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-sm text-white truncate">{caller.sender_name}</span>
            <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold', badge.bg, badge.color)}>
              {badge.label}
            </span>
            <span className="text-[10px] text-slate-600 font-mono">{caller.composite_score.toFixed(0)}pts</span>
          </div>
          <div className="flex items-center gap-3 text-[11px]">
            <span className="text-slate-500">{caller.total_signals} calls</span>
            <span className="text-emerald-400/80">{caller.win_count}W</span>
            <span className="text-red-400/80">{caller.loss_count}L</span>
            <span className="text-slate-400">WR {winRate}%</span>
          </div>
        </div>

        {/* Performance */}
        <div className="text-right shrink-0">
          <p className={clsx(
            'text-sm font-bold font-mono',
            caller.avg_return >= 0 ? 'text-emerald-400' : 'text-red-400'
          )}>
            {caller.avg_return >= 0 ? '+' : ''}{caller.avg_return.toFixed(1)}%
          </p>
          <p className="text-[10px] text-slate-600">
            Best: <span className="text-emerald-400/60">+{caller.best_return.toFixed(0)}%</span>
          </p>
        </div>
      </div>
    </div>
  );
}
