'use client';
import StatCard from '@/components/StatCard';
import { usePortfolioSummary } from '@/lib/hooks';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

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

  if (isLoading) return <div className="text-slate-400">Loading portfolio...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Portfolio</h1>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
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
          <StatCard label="Win Rate" value={`${summary.win_rate}%`} color="green" />
          <StatCard label="Open" value={summary.total_open} color="blue" />
          <StatCard label="Max Drawdown" value={`${summary.max_drawdown_pct}%`} color="red" />
        </div>
      )}

      {/* Open Positions */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Open Positions</h2>
        {openData?.positions && openData.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 border-b border-[#334155]">
                  <th className="pb-2">Token</th>
                  <th className="pb-2">Chain</th>
                  <th className="pb-2">Entry</th>
                  <th className="pb-2">Current</th>
                  <th className="pb-2">P&L</th>
                  <th className="pb-2">Drawdown</th>
                </tr>
              </thead>
              <tbody>
                {openData.positions.map((pos: any) => (
                  <tr key={pos.id} className="border-b border-[#334155]/50">
                    <td className="py-2">{pos.token_symbol || pos.token_address?.slice(0, 8)}</td>
                    <td className="py-2 text-xs text-slate-400">{(pos.chain || '').toUpperCase()}</td>
                    <td className="py-2">${pos.entry_price?.toFixed(6)}</td>
                    <td className="py-2">${pos.current_price?.toFixed(6)}</td>
                    <td className={`py-2 ${(pos.unrealized_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pos.unrealized_pnl_pct?.toFixed(1)}% (${pos.unrealized_pnl?.toFixed(2)})
                    </td>
                    <td className="py-2 text-red-400">{pos.max_drawdown_pct?.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-slate-500">No open positions.</p>
        )}
      </div>

      {/* Closed Positions */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Recent Closed</h2>
        {closedData?.positions && closedData.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 border-b border-[#334155]">
                  <th className="pb-2">Token</th>
                  <th className="pb-2">Chain</th>
                  <th className="pb-2">Entry</th>
                  <th className="pb-2">Exit</th>
                  <th className="pb-2">P&L</th>
                </tr>
              </thead>
              <tbody>
                {closedData.positions.map((pos: any) => (
                  <tr key={pos.id} className="border-b border-[#334155]/50">
                    <td className="py-2">{pos.token_symbol || pos.token_address?.slice(0, 8)}</td>
                    <td className="py-2 text-xs text-slate-400">{(pos.chain || '').toUpperCase()}</td>
                    <td className="py-2">${pos.entry_price?.toFixed(6)}</td>
                    <td className="py-2">${pos.exit_price?.toFixed(6)}</td>
                    <td className={`py-2 ${(pos.realized_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pos.realized_pnl_pct?.toFixed(1)}% (${pos.realized_pnl?.toFixed(2)})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-slate-500">No closed positions yet.</p>
        )}
      </div>
    </div>
  );
}
