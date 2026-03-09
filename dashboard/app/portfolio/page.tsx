'use client';
import StatCard from '@/components/StatCard';
import { SkeletonCard } from '@/components/Skeleton';
import { usePortfolioSummary } from '@/lib/hooks';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import clsx from 'clsx';

function formatPrice(price: number | null | undefined): string {
  if (price === null || price === undefined) return 'N/A';
  if (price < 0.0001) return `$${price.toExponential(2)}`;
  if (price < 1) return `$${price.toFixed(6)}`;
  return `$${price.toFixed(4)}`;
}

export default function PortfolioPage() {
  const { data: summary, isLoading } = usePortfolioSummary();
  const { data: openData } = useQuery({
    queryKey: ['portfolio', 'open'],
    queryFn: () => api.portfolio.open(),
    refetchInterval: 15000,
  });
  const { data: closedData } = useQuery({
    queryKey: ['portfolio', 'closed'],
    queryFn: () => api.portfolio.closed(20),
    refetchInterval: 30000,
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Portfolio</h1>
        <p className="text-sm text-slate-500 mt-1">Virtual portfolio tracking ($100 per signal)</p>
      </div>

      {/* Stats */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard
            label="Total P&L"
            value={`$${summary.total_pnl.toFixed(2)}`}
            color={summary.total_pnl >= 0 ? 'green' : 'red'}
          />
          <StatCard
            label="Unrealized"
            value={`$${summary.total_unrealized_pnl.toFixed(2)}`}
            color={summary.total_unrealized_pnl >= 0 ? 'green' : 'red'}
          />
          <StatCard
            label="Realized"
            value={`$${summary.total_realized_pnl.toFixed(2)}`}
            color={summary.total_realized_pnl >= 0 ? 'green' : 'red'}
          />
          <StatCard label="Win Rate" value={`${summary.win_rate}%`} color="green" subtext={`${summary.wins}W / ${summary.losses}L`} />
          <StatCard label="Open Positions" value={summary.total_open} color="blue" />
          <StatCard label="Max Drawdown" value={`${summary.max_drawdown_pct.toFixed(1)}%`} color="red" />
        </div>
      ) : null}

      {/* Open Positions */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 overflow-hidden">
        <div className="px-5 py-4 border-b border-dark-400/30">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse-dot" />
            <h2 className="text-sm font-semibold text-slate-300">Open Positions</h2>
            {openData?.positions && (
              <span className="text-[10px] text-slate-600 ml-1">({openData.positions.length})</span>
            )}
          </div>
        </div>
        {openData?.positions && openData.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] text-slate-600 uppercase tracking-wider">
                  <th className="px-5 py-3">Token</th>
                  <th className="px-3 py-3">Chain</th>
                  <th className="px-3 py-3">Entry Price</th>
                  <th className="px-3 py-3">Current Price</th>
                  <th className="px-3 py-3">P&L</th>
                  <th className="px-3 py-3">Drawdown</th>
                </tr>
              </thead>
              <tbody>
                {openData.positions.map((pos: any) => (
                  <tr key={pos.id} className="border-t border-dark-400/20 table-row-hover transition-colors">
                    <td className="px-5 py-3 font-medium text-white">
                      {pos.token_symbol || pos.token_address?.slice(0, 8)}
                    </td>
                    <td className="px-3 py-3">
                      <span className="text-[10px] font-semibold text-slate-500 uppercase">
                        {(pos.chain || '').toUpperCase()}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-400">{formatPrice(pos.entry_price)}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-400">{formatPrice(pos.current_price)}</td>
                    <td className={clsx('px-3 py-3 font-mono text-xs font-medium', (pos.unrealized_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {(pos.unrealized_pnl_pct || 0) >= 0 ? '+' : ''}{pos.unrealized_pnl_pct?.toFixed(1)}%
                      <span className="text-slate-600 ml-1">(${pos.unrealized_pnl?.toFixed(2)})</span>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-red-400/60">{pos.max_drawdown_pct?.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-sm text-slate-600">No open positions.</div>
        )}
      </div>

      {/* Closed Positions */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 overflow-hidden">
        <div className="px-5 py-4 border-b border-dark-400/30">
          <h2 className="text-sm font-semibold text-slate-300">Recently Closed</h2>
        </div>
        {closedData?.positions && closedData.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] text-slate-600 uppercase tracking-wider">
                  <th className="px-5 py-3">Token</th>
                  <th className="px-3 py-3">Chain</th>
                  <th className="px-3 py-3">Entry</th>
                  <th className="px-3 py-3">Exit</th>
                  <th className="px-3 py-3">P&L</th>
                </tr>
              </thead>
              <tbody>
                {closedData.positions.map((pos: any) => (
                  <tr key={pos.id} className="border-t border-dark-400/20 table-row-hover transition-colors">
                    <td className="px-5 py-3 font-medium text-white">
                      {pos.token_symbol || pos.token_address?.slice(0, 8)}
                    </td>
                    <td className="px-3 py-3">
                      <span className="text-[10px] font-semibold text-slate-500 uppercase">
                        {(pos.chain || '').toUpperCase()}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-400">{formatPrice(pos.entry_price)}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-400">{formatPrice(pos.exit_price)}</td>
                    <td className={clsx('px-3 py-3 font-mono text-xs font-medium', (pos.realized_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {(pos.realized_pnl_pct || 0) >= 0 ? '+' : ''}{pos.realized_pnl_pct?.toFixed(1)}%
                      <span className="text-slate-600 ml-1">(${pos.realized_pnl?.toFixed(2)})</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-sm text-slate-600">No closed positions yet.</div>
        )}
      </div>
    </div>
  );
}
