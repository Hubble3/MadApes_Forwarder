'use client';
import StatCard from '@/components/StatCard';
import SignalCard from '@/components/SignalCard';
import ChainDistribution from '@/components/ChainDistribution';
import { SkeletonCard, SkeletonSignal } from '@/components/Skeleton';
import { useOverview, useRecentSignals, usePortfolioSummary } from '@/lib/hooks';
import clsx from 'clsx';

export default function DashboardHome() {
  const { data: overview, isLoading: loadingOverview } = useOverview();
  const { data: recent, isLoading: loadingSignals } = useRecentSignals(8);
  const { data: portfolio, isLoading: loadingPortfolio } = usePortfolioSummary();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Real-time signal intelligence overview</p>
      </div>

      {/* Stat cards */}
      {loadingOverview ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard label="Total Signals" value={overview?.total_signals ?? 0} color="blue" />
          <StatCard label="Today" value={overview?.today_signals ?? 0} color="purple" />
          <StatCard
            label="Win Rate"
            value={`${overview?.win_rate ?? 0}%`}
            color={(overview?.win_rate ?? 0) >= 50 ? 'green' : 'red'}
          />
          <StatCard label="Runners" value={overview?.runners ?? 0} color="yellow" />
          <StatCard
            label="Total P&L"
            value={portfolio ? `$${portfolio.total_pnl.toFixed(0)}` : '$0'}
            color={portfolio && portfolio.total_pnl >= 0 ? 'green' : 'red'}
          />
          <StatCard label="Active" value={overview?.active ?? 0} />
        </div>
      )}

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Portfolio summary */}
        <div className="lg:col-span-2 bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Portfolio Performance</h2>
          {loadingPortfolio ? (
            <div className="grid grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-12 rounded animate-shimmer" />)}
            </div>
          ) : portfolio && (portfolio.total_open > 0 || portfolio.total_closed > 0) ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Unrealized P&L</p>
                <p className={clsx('text-lg font-bold font-mono', portfolio.total_unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                  ${portfolio.total_unrealized_pnl.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Realized P&L</p>
                <p className={clsx('text-lg font-bold font-mono', portfolio.total_realized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                  ${portfolio.total_realized_pnl.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Win Rate</p>
                <p className="text-lg font-bold text-white">{portfolio.win_rate}%</p>
                <p className="text-[10px] text-slate-600">{portfolio.wins}W / {portfolio.losses}L</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Max Drawdown</p>
                <p className="text-lg font-bold text-red-400">{portfolio.max_drawdown_pct.toFixed(1)}%</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-600">No portfolio data yet.</p>
          )}
        </div>

        {/* Chain distribution */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Chain Distribution</h2>
          {overview?.chains && Object.keys(overview.chains).length > 0 ? (
            <ChainDistribution chains={overview.chains} />
          ) : (
            <p className="text-sm text-slate-600">No chain data yet.</p>
          )}
        </div>
      </div>

      {/* Win/Loss breakdown */}
      {overview && (overview.wins > 0 || overview.losses > 0) && (
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Signal Outcomes</h2>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex h-3 rounded-full overflow-hidden bg-dark-500">
                <div
                  className="bg-emerald-500 transition-all duration-700"
                  style={{ width: `${(overview.wins / (overview.wins + overview.losses)) * 100}%`, opacity: 0.8 }}
                />
                <div
                  className="bg-red-500 transition-all duration-700"
                  style={{ width: `${(overview.losses / (overview.wins + overview.losses)) * 100}%`, opacity: 0.8 }}
                />
              </div>
            </div>
            <div className="flex items-center gap-4 text-xs shrink-0">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-slate-400">{overview.wins} Wins</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-slate-400">{overview.losses} Losses</span>
              </span>
              <span className="text-slate-600">{overview.active} Active</span>
            </div>
          </div>
        </div>
      )}

      {/* Recent signals */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Recent Signals</h2>
          <a href="/signals" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
            View all &rarr;
          </a>
        </div>
        {loadingSignals ? (
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => <SkeletonSignal key={i} />)}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {recent?.signals.map((signal) => (
              <SignalCard key={signal.id} signal={signal} />
            ))}
            {(!recent?.signals || recent.signals.length === 0) && (
              <p className="text-sm text-slate-600">No signals yet.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
