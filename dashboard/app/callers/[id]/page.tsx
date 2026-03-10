'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import clsx from 'clsx';
import { api } from '@/lib/api';
import type { Signal } from '@/lib/api';
import { formatPct, timeAgo } from '@/lib/format';

function scoreBadge(score: number): { label: string; color: string; bg: string } {
  if (score >= 90) return { label: 'S+', color: 'text-amber-400', bg: 'bg-amber-500/15' };
  if (score >= 75) return { label: 'S', color: 'text-emerald-400', bg: 'bg-emerald-500/15' };
  if (score >= 60) return { label: 'A', color: 'text-blue-400', bg: 'bg-blue-500/15' };
  if (score >= 45) return { label: 'B', color: 'text-slate-300', bg: 'bg-slate-500/15' };
  if (score >= 30) return { label: 'C', color: 'text-slate-400', bg: 'bg-slate-500/10' };
  return { label: 'D', color: 'text-red-400', bg: 'bg-red-500/10' };
}

function signalStatus(signal: Signal): { label: string; color: string } {
  if (signal.status === 'win') return { label: 'Win', color: 'text-emerald-400' };
  if (signal.status === 'loss') return { label: 'Loss', color: 'text-red-400' };
  return { label: 'Active', color: 'text-blue-400' };
}

export default function CallerDetailPage() {
  const params = useParams();
  const senderId = Number(params.id);

  const { data: callerData, isLoading: callerLoading } = useQuery({
    queryKey: ['caller', senderId],
    queryFn: () => api.callers.get(senderId),
    enabled: !isNaN(senderId),
  });

  const { data: signalsData, isLoading: signalsLoading } = useQuery({
    queryKey: ['caller-signals', senderId],
    queryFn: () => api.callers.signals(senderId),
    enabled: !isNaN(senderId),
  });

  const caller = callerData?.caller;
  const signals = signalsData?.signals ?? [];

  if (callerLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-slate-500">Loading caller...</div>
      </div>
    );
  }

  if (!caller) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="text-slate-500">Caller not found</div>
        <Link href="/callers" className="text-blue-400 hover:text-blue-300 text-sm">
          Back to Callers
        </Link>
      </div>
    );
  }

  const badge = scoreBadge(caller.composite_score);
  const winRate = caller.win_rate ?? (
    (caller.win_count + caller.loss_count > 0)
      ? Number(((caller.win_count / (caller.win_count + caller.loss_count)) * 100).toFixed(1))
      : 0
  );

  const stats = [
    { label: 'Wins', value: caller.win_count, color: 'text-emerald-400' },
    { label: 'Losses', value: caller.loss_count, color: 'text-red-400' },
    { label: 'Avg Return', value: formatPct(caller.avg_return), color: caller.avg_return >= 0 ? 'text-emerald-400' : 'text-red-400' },
    { label: 'Best Return', value: formatPct(caller.best_return), color: 'text-emerald-400' },
    { label: 'Worst Return', value: formatPct(caller.worst_return), color: 'text-red-400' },
    { label: 'Runner Count', value: caller.runner_count, color: 'text-amber-400' },
  ];

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Link
        href="/callers"
        className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
        </svg>
        Back to Callers
      </Link>

      {/* Caller header */}
      <div className="rounded-xl border border-dark-400/30 bg-dark-700 p-6">
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-xl font-bold text-white">{caller.sender_name}</h1>
              <span className={clsx('px-2 py-0.5 rounded text-xs font-bold', badge.bg, badge.color)}>
                {badge.label}
              </span>
            </div>
            <div className="flex items-center gap-4 text-sm text-slate-400">
              <span>Score: <span className="text-white font-mono">{caller.composite_score.toFixed(0)}</span></span>
              <span>Signals: <span className="text-white font-mono">{caller.total_signals}</span></span>
              <span>Win Rate: <span className="text-white font-mono">{winRate}%</span></span>
            </div>
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-dark-400/30 bg-dark-700 p-4 text-center"
          >
            <p className="text-[11px] text-slate-500 mb-1">{stat.label}</p>
            <p className={clsx('text-lg font-bold font-mono', stat.color)}>
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      {/* Recent signals */}
      <div className="rounded-xl border border-dark-400/30 bg-dark-700">
        <div className="px-6 py-4 border-b border-dark-400/30">
          <h2 className="text-sm font-semibold text-white">Recent Signals</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">{signalsData?.total ?? 0} signals</p>
        </div>

        {signalsLoading ? (
          <div className="p-6 text-center text-slate-500 text-sm">Loading signals...</div>
        ) : signals.length === 0 ? (
          <div className="p-6 text-center text-slate-500 text-sm">No signals found</div>
        ) : (
          <div className="divide-y divide-dark-400/20">
            {signals.map((signal: Signal) => {
              const status = signalStatus(signal);
              return (
                <div key={signal.id} className="px-6 py-3 flex items-center gap-4 hover:bg-dark-600 transition-colors">
                  {/* Token info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white truncate">
                        {signal.token_name || 'Unknown'}
                      </span>
                      {signal.token_symbol && (
                        <span className="text-[10px] text-slate-500 font-mono">
                          ${signal.token_symbol}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-slate-600 uppercase">{signal.chain}</span>
                      <span className="text-[10px] text-slate-600">
                        {timeAgo(signal.original_timestamp)}
                      </span>
                    </div>
                  </div>

                  {/* Status */}
                  <span className={clsx('text-xs font-semibold', status.color)}>
                    {status.label}
                  </span>

                  {/* P&L */}
                  <div className="text-right shrink-0 w-20">
                    <span className={clsx(
                      'text-sm font-bold font-mono',
                      signal.price_change_percent !== null && signal.price_change_percent !== undefined
                        ? signal.price_change_percent >= 0 ? 'text-emerald-400' : 'text-red-400'
                        : 'text-slate-500'
                    )}>
                      {signal.price_change_percent !== null && signal.price_change_percent !== undefined
                        ? formatPct(signal.price_change_percent)
                        : 'N/A'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
