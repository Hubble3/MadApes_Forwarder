'use client';
import StatCard from '@/components/StatCard';
import SignalCard from '@/components/SignalCard';
import { SkeletonCard, SkeletonSignal } from '@/components/Skeleton';
import { useRunners, useRunnerStats } from '@/lib/hooks';

export default function RunnersPage() {
  const { data: stats, isLoading: loadingStats } = useRunnerStats();
  const { data: runners, isLoading: loadingRunners } = useRunners(30);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Runner Alerts</h1>
        <p className="text-sm text-slate-500 mt-1">Tokens showing strong momentum and volume acceleration</p>
      </div>

      {/* Stats */}
      {loadingStats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Runners" value={stats.total_runners} color="yellow" />
          <StatCard
            label="Runner Rate"
            value={`${stats.runner_rate}%`}
            subtext={`of ${stats.total_signals} signals`}
          />
          <StatCard
            label="Runner Win Rate"
            value={`${stats.runner_win_rate}%`}
            color="green"
          />
          <StatCard
            label="Avg Return"
            value={`${stats.runner_avg_return >= 0 ? '+' : ''}${Number(stats.runner_avg_return).toFixed(1)}%`}
            color={stats.runner_avg_return >= 0 ? 'green' : 'red'}
          />
        </div>
      ) : null}

      {/* Runner list */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Recent Runners</h2>
        {loadingRunners ? (
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => <SkeletonSignal key={i} />)}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {runners?.runners.map((signal) => (
              <SignalCard key={signal.id} signal={signal} />
            ))}
            {(!runners?.runners || runners.runners.length === 0) && (
              <div className="col-span-2 py-12 text-center">
                <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-dark-600 flex items-center justify-center">
                  <svg className="w-6 h-6 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
                  </svg>
                </div>
                <p className="text-slate-600">No runners detected yet.</p>
                <p className="text-xs text-slate-700 mt-1">Runners appear when tokens show strong momentum</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
