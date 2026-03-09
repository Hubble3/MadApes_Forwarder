'use client';
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import clsx from 'clsx';

const STRATEGY_COLORS: Record<string, string> = {
  convergence_sniper: 'blue',
  elite_caller: 'purple',
  micro_cap_scalp: 'yellow',
  safety_first: 'green',
  momentum_rider: 'orange',
  chain_rotation: 'cyan',
  time_decay: 'pink',
};

const STRATEGY_ICONS: Record<string, string> = {
  convergence_sniper: 'Crosshair',
  elite_caller: 'Crown',
  micro_cap_scalp: 'Zap',
  safety_first: 'Shield',
  momentum_rider: 'TrendingUp',
  chain_rotation: 'Globe',
  time_decay: 'Clock',
};

function getColor(name: string) {
  const c = STRATEGY_COLORS[name] || 'blue';
  const map: Record<string, { bg: string; text: string; border: string; glow: string }> = {
    blue: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30', glow: 'shadow-blue-500/10' },
    purple: { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/30', glow: 'shadow-purple-500/10' },
    yellow: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30', glow: 'shadow-yellow-500/10' },
    green: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30', glow: 'shadow-emerald-500/10' },
    orange: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30', glow: 'shadow-orange-500/10' },
    cyan: { bg: 'bg-cyan-500/10', text: 'text-cyan-400', border: 'border-cyan-500/30', glow: 'shadow-cyan-500/10' },
    pink: { bg: 'bg-pink-500/10', text: 'text-pink-400', border: 'border-pink-500/30', glow: 'shadow-pink-500/10' },
  };
  return map[c] || map.blue;
}

export default function StrategiesPage() {
  const { data: strategiesData, isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => api.strategies.list(),
  });
  const { data: performanceData } = useQuery({
    queryKey: ['strategies', 'performance'],
    queryFn: () => api.strategies.performance(),
    refetchInterval: 60000,
  });

  const [evalId, setEvalId] = useState('');
  const evalMutation = useMutation({
    mutationFn: (signal_id: number) => api.strategies.evaluate(signal_id),
  });

  const strategies = strategiesData?.strategies || [];
  const performance = performanceData?.performance || performanceData || {};

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Trading Strategies</h1>
        <p className="text-sm text-slate-500 mt-1">Automated signal evaluation and position sizing</p>
      </div>

      {/* Strategy Cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-48 rounded-xl animate-shimmer" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {strategies.map((s: any) => {
            const colors = getColor(s.name);
            const perf = performance[s.name];
            return (
              <div
                key={s.name}
                className={clsx(
                  'bg-dark-700 rounded-xl border p-5 transition-all hover:shadow-lg',
                  colors.border,
                  colors.glow
                )}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className={clsx('text-sm font-bold', colors.text)}>
                      {s.display_name || s.name.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    </h3>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">
                      {STRATEGY_ICONS[s.name] || 'Strategy'}
                    </p>
                  </div>
                  <span className={clsx('text-xs font-mono px-2 py-0.5 rounded-full', colors.bg, colors.text)}>
                    ${s.position_size || s.base_position || '?'}
                  </span>
                </div>

                <p className="text-xs text-slate-400 leading-relaxed mb-4">
                  {s.description || 'No description available.'}
                </p>

                {/* Criteria */}
                {s.criteria && (
                  <div className="mb-3">
                    <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1.5">Criteria</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(s.criteria).slice(0, 5).map(([k, v]) => (
                        <span key={k} className="text-[10px] bg-dark-600 text-slate-400 px-1.5 py-0.5 rounded">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Exit Rules */}
                {s.exit_rules && (
                  <div className="mb-3">
                    <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1.5">Exit Rules</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(s.exit_rules).map(([k, v]) => (
                        <span key={k} className="text-[10px] bg-dark-600 text-slate-400 px-1.5 py-0.5 rounded">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Performance */}
                {perf && (
                  <div className="pt-3 border-t border-dark-400/30">
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <p className="text-[10px] text-slate-600">Signals</p>
                        <p className="text-xs font-bold text-white">{perf.total || 0}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-600">Win Rate</p>
                        <p className={clsx('text-xs font-bold', (perf.win_rate || 0) >= 50 ? 'text-emerald-400' : 'text-red-400')}>
                          {(perf.win_rate || 0).toFixed(0)}%
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-slate-600">P&L</p>
                        <p className={clsx('text-xs font-bold font-mono', (perf.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          ${(perf.total_pnl || 0).toFixed(0)}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Strategy Performance Summary */}
      {Object.keys(performance).length > 0 && (
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 overflow-hidden">
          <div className="px-5 py-4 border-b border-dark-400/30">
            <h2 className="text-sm font-semibold text-slate-300">Performance Comparison</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] text-slate-600 uppercase tracking-wider">
                  <th className="px-5 py-3">Strategy</th>
                  <th className="px-3 py-3">Signals</th>
                  <th className="px-3 py-3">Wins</th>
                  <th className="px-3 py-3">Losses</th>
                  <th className="px-3 py-3">Win Rate</th>
                  <th className="px-3 py-3">Avg Return</th>
                  <th className="px-3 py-3">Total P&L</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(performance).map(([name, p]: [string, any]) => {
                  const colors = getColor(name);
                  return (
                    <tr key={name} className="border-t border-dark-400/20 table-row-hover transition-colors">
                      <td className="px-5 py-3">
                        <span className={clsx('font-medium text-sm', colors.text)}>
                          {name.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-slate-400">{p.total || 0}</td>
                      <td className="px-3 py-3 text-emerald-400">{p.wins || 0}</td>
                      <td className="px-3 py-3 text-red-400">{p.losses || 0}</td>
                      <td className={clsx('px-3 py-3 font-mono', (p.win_rate || 0) >= 50 ? 'text-emerald-400' : 'text-red-400')}>
                        {(p.win_rate || 0).toFixed(1)}%
                      </td>
                      <td className={clsx('px-3 py-3 font-mono', (p.avg_return || 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                        {(p.avg_return || 0) >= 0 ? '+' : ''}{(p.avg_return || 0).toFixed(1)}%
                      </td>
                      <td className={clsx('px-3 py-3 font-mono font-medium', (p.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                        ${(p.total_pnl || 0).toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Evaluate Signal */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Evaluate Signal Against Strategies</h2>
        <div className="flex gap-2 mb-4">
          <input
            type="number"
            placeholder="Signal ID"
            value={evalId}
            onChange={(e) => setEvalId(e.target.value)}
            className="w-32 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
          />
          <button
            onClick={() => evalMutation.mutate(Number(evalId))}
            disabled={!evalId || evalMutation.isPending}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 text-sm font-medium rounded-lg hover:bg-blue-500/30 transition-colors disabled:opacity-50"
          >
            {evalMutation.isPending ? 'Evaluating...' : 'Evaluate'}
          </button>
        </div>

        {evalMutation.isSuccess && evalMutation.data && (
          <div className="space-y-2">
            {(evalMutation.data.results || evalMutation.data.strategies || []).length === 0 ? (
              <p className="text-sm text-slate-500">No strategies matched this signal.</p>
            ) : (
              (evalMutation.data.results || evalMutation.data.strategies || []).map((r: any, i: number) => {
                const colors = getColor(r.strategy || r.name);
                return (
                  <div key={i} className={clsx('p-3 rounded-lg border', colors.bg, colors.border)}>
                    <div className="flex items-center justify-between">
                      <div>
                        <span className={clsx('text-sm font-medium', colors.text)}>
                          {(r.strategy || r.name || '').replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                        </span>
                        {r.eligible === false && (
                          <span className="text-xs text-slate-500 ml-2">(Not eligible)</span>
                        )}
                      </div>
                      {r.position_size && (
                        <span className="text-xs font-mono text-white">${r.position_size}</span>
                      )}
                    </div>
                    {r.reason && <p className="text-xs text-slate-400 mt-1">{r.reason}</p>}
                    {r.exit_rules && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {Object.entries(r.exit_rules).map(([k, v]) => (
                          <span key={k} className="text-[10px] bg-dark-600 text-slate-400 px-1.5 py-0.5 rounded">
                            {k}: {String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {evalMutation.isError && (
          <p className="text-sm text-red-400">Failed to evaluate. Signal may not exist.</p>
        )}
      </div>
    </div>
  );
}
