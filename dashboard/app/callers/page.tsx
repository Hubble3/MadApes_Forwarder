'use client';
import { useState } from 'react';
import CallerRow from '@/components/CallerRow';
import { SkeletonRow } from '@/components/Skeleton';
import { useCallers, useLeaderboard } from '@/lib/hooks';
import clsx from 'clsx';

const windows = [
  { key: 'all', label: 'All Time' },
  { key: '24h', label: '24h' },
  { key: '7d', label: '7d' },
  { key: '30d', label: '30d' },
];

export default function CallersPage() {
  const [window, setWindow] = useState('all');
  const { data: callerData, isLoading: loadingCallers } = useCallers(2);
  const { data: lbData, isLoading: loadingLb } = useLeaderboard(window);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Caller Leaderboard</h1>
          <p className="text-sm text-slate-500 mt-1">Top performing signal callers ranked by performance</p>
        </div>
        <div className="flex items-center gap-1.5 bg-dark-700 rounded-lg p-1 border border-dark-400/30">
          {windows.map((w) => (
            <button
              key={w.key}
              onClick={() => setWindow(w.key)}
              className={clsx(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200',
                window === w.key
                  ? 'bg-blue-500/20 text-blue-400 shadow-sm'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-dark-600'
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {/* Leaderboard */}
      {loadingLb || loadingCallers ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)}
        </div>
      ) : (
        <div className="space-y-3">
          {lbData?.leaderboard.map((entry) => {
            const caller = callerData?.callers.find((c) => c.sender_id === entry.sender_id);
            if (!caller) {
              return (
                <div key={entry.sender_id} className="relative overflow-hidden rounded-xl border border-dark-400/30 bg-dark-700 p-4 flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-dark-500 flex items-center justify-center text-slate-500 font-bold text-sm">
                    #{entry.rank}
                  </div>
                  <div className="flex-1">
                    <span className="font-semibold text-sm text-white">{entry.sender_name}</span>
                    <div className="flex gap-3 text-[11px] text-slate-500 mt-1">
                      <span>{entry.total_signals} calls</span>
                      <span className="text-emerald-400/80">{entry.wins}W</span>
                      <span className="text-red-400/80">{entry.losses}L</span>
                      <span>WR {entry.win_rate}%</span>
                    </div>
                  </div>
                  <span className={clsx(
                    'text-sm font-bold font-mono',
                    entry.avg_return >= 0 ? 'text-emerald-400' : 'text-red-400'
                  )}>
                    {entry.avg_return >= 0 ? '+' : ''}{entry.avg_return.toFixed(1)}%
                  </span>
                </div>
              );
            }
            return <CallerRow key={caller.sender_id} caller={caller} rank={entry.rank} />;
          })}
          {(!lbData?.leaderboard || lbData.leaderboard.length === 0) && (
            <div className="py-12 text-center">
              <p className="text-slate-600">No caller data yet.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
