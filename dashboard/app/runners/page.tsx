'use client';
import StatCard from '@/components/StatCard';
import SignalCard from '@/components/SignalCard';
import { useRunners, useRunnerStats } from '@/lib/hooks';

export default function RunnersPage() {
  const { data: stats, isLoading: loadingStats } = useRunnerStats();
  const { data: runners, isLoading: loadingRunners } = useRunners(30);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Runner Alerts</h1>

      {stats && (
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
            value={`${stats.runner_avg_return >= 0 ? '+' : ''}${stats.runner_avg_return}%`}
            color={stats.runner_avg_return >= 0 ? 'green' : 'red'}
          />
        </div>
      )}

      <div>
        <h2 className="text-lg font-semibold mb-3">Recent Runners</h2>
        {loadingRunners ? (
          <p className="text-slate-400">Loading...</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {runners?.runners.map((signal) => (
              <SignalCard key={signal.id} signal={signal} />
            ))}
            {(!runners?.runners || runners.runners.length === 0) && (
              <p className="text-slate-500">No runners detected yet.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
