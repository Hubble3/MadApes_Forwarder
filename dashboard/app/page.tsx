'use client';
import StatCard from '@/components/StatCard';
import SignalCard from '@/components/SignalCard';
import { useOverview, useRecentSignals, usePortfolioSummary } from '@/lib/hooks';

export default function DashboardHome() {
  const { data: overview, isLoading: loadingOverview } = useOverview();
  const { data: recent, isLoading: loadingSignals } = useRecentSignals(10);
  const { data: portfolio, isLoading: loadingPortfolio } = usePortfolioSummary();

  if (loadingOverview) {
    return <div className="text-slate-400">Loading dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <StatCard label="Total Signals" value={overview?.total_signals ?? 0} />
        <StatCard label="Today" value={overview?.today_signals ?? 0} color="blue" />
        <StatCard label="Win Rate" value={`${overview?.win_rate ?? 0}%`} color="green" />
        <StatCard label="Runners" value={overview?.runners ?? 0} color="yellow" />
        <StatCard
          label="Total P&L"
          value={portfolio ? `$${portfolio.total_pnl.toFixed(2)}` : '$0'}
          color={portfolio && portfolio.total_pnl >= 0 ? 'green' : 'red'}
        />
        <StatCard label="Active" value={overview?.active ?? 0} />
      </div>

      {/* Portfolio Summary */}
      {portfolio && (portfolio.total_open > 0 || portfolio.total_closed > 0) && (
        <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Portfolio</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-slate-500">Unrealized</span>
              <p className={portfolio.total_unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                ${portfolio.total_unrealized_pnl.toFixed(2)}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Realized</span>
              <p className={portfolio.total_realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                ${portfolio.total_realized_pnl.toFixed(2)}
              </p>
            </div>
            <div>
              <span className="text-slate-500">Win Rate</span>
              <p>{portfolio.win_rate}%</p>
            </div>
            <div>
              <span className="text-slate-500">Max Drawdown</span>
              <p className="text-red-400">{portfolio.max_drawdown_pct.toFixed(1)}%</p>
            </div>
          </div>
        </div>
      )}

      {/* Chain Distribution */}
      {overview?.chains && Object.keys(overview.chains).length > 0 && (
        <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Chains</h2>
          <div className="flex gap-3 flex-wrap">
            {Object.entries(overview.chains).map(([chain, count]) => (
              <span key={chain} className="px-3 py-1 rounded-full text-xs bg-[#334155] text-slate-300">
                {chain.toUpperCase()}: {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recent Signals */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Recent Signals</h2>
        {loadingSignals ? (
          <p className="text-slate-400">Loading...</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {recent?.signals.map((signal) => (
              <SignalCard key={signal.id} signal={signal} />
            ))}
            {(!recent?.signals || recent.signals.length === 0) && (
              <p className="text-slate-500">No signals yet.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
