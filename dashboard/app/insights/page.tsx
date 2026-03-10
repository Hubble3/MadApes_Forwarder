'use client';
import { useInsights } from '@/lib/hooks';
import { SkeletonCard } from '@/components/Skeleton';
import StatCard from '@/components/StatCard';
import clsx from 'clsx';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-dark-800 border border-dark-400 rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="text-xs font-medium" style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(1) : p.value}
        </p>
      ))}
    </div>
  );
}

const TIER_COLORS: Record<string, string> = {
  gold: '#f59e0b',
  silver: '#94a3b8',
  bronze: '#d97706',
  skip: '#6b7280',
};

const TIER_EMOJI: Record<string, string> = {
  gold: '\u{1f947}',
  silver: '\u{1f948}',
  bronze: '\u{1f949}',
  skip: '\u26d4',
};

export default function InsightsPage() {
  const { data, isLoading } = useInsights();

  const readiness = data?.data_readiness;
  const byCaller = data?.by_caller || [];
  const byChain = data?.by_chain || [];
  const byMc = data?.by_mc || [];
  const byHour = data?.by_hour || [];
  const byTier = data?.by_tier || [];
  const bySession = data?.by_session || [];
  const topSignals = data?.top_signals || [];
  const takeaways = data?.takeaways || [];

  // Prepare hour chart data (fill in all 24 hours)
  const hourMap: Record<number, any> = {};
  byHour.forEach((h: any) => { hourMap[h.hour] = h; });
  const hourChartData = Array.from({ length: 24 }, (_, i) => {
    const d = hourMap[i];
    return {
      hour: `${i}:00`,
      win_rate: d?.win_rate ?? 0,
      total: d?.total ?? 0,
    };
  });

  // Radar data for session performance
  const sessionRadar = bySession.map((s: any) => ({
    session: s.session.toUpperCase(),
    win_rate: s.win_rate,
    signals: s.total,
  }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Insights</h1>
        <p className="text-sm text-slate-500 mt-1">
          Statistical intelligence from your signal history — what works, what doesn&apos;t, and why
        </p>
      </div>

      {/* Data Readiness */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Checked Signals"
              value={readiness?.checked_signals ?? 0}
              subtext={`of ${readiness?.total_signals ?? 0} total`}
              color="blue"
            />
            <StatCard
              label="ML Progress"
              value={`${readiness?.progress_pct ?? 0}%`}
              subtext={readiness?.ml_ready ? 'Ready to train' : `Need ${readiness?.ml_min_samples - (readiness?.checked_signals ?? 0)} more`}
              color={readiness?.ml_ready ? 'green' : 'yellow'}
            />
            <StatCard
              label="6h Data"
              value={readiness?.signals_with_6h ?? 0}
              subtext="signals with 6h check"
              color="purple"
            />
            <StatCard
              label="Runners Found"
              value={readiness?.runners_detected ?? 0}
              color="yellow"
            />
          </div>

          {/* Progress bar */}
          <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-slate-300">Data Collection Progress</h2>
              <span className="text-xs text-slate-500">
                {readiness?.checked_signals ?? 0} / {readiness?.ml_recommended ?? 200} recommended for ML
              </span>
            </div>
            <div className="w-full bg-dark-600 rounded-full h-3 overflow-hidden">
              <div
                className={clsx(
                  'h-3 rounded-full transition-all duration-500',
                  (readiness?.progress_pct ?? 0) >= 100
                    ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                    : (readiness?.progress_pct ?? 0) >= 50
                    ? 'bg-gradient-to-r from-blue-500 to-blue-400'
                    : 'bg-gradient-to-r from-amber-500 to-amber-400'
                )}
                style={{ width: `${Math.min(100, readiness?.progress_pct ?? 0)}%` }}
              />
            </div>
            <div className="flex justify-between mt-2 text-[10px] text-slate-600">
              <span>0</span>
              <span className="text-slate-500">20 (min)</span>
              <span className="text-slate-500">100</span>
              <span>200 (recommended)</span>
            </div>
          </div>

          {/* Takeaways */}
          {takeaways.length > 0 && (
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-3">Key Takeaways</h2>
              <div className="space-y-2">
                {takeaways.map((t: any, i: number) => (
                  <div
                    key={i}
                    className={clsx(
                      'flex items-start gap-3 px-4 py-3 rounded-lg text-sm',
                      t.type === 'success' && 'bg-emerald-500/10 border border-emerald-500/20',
                      t.type === 'warning' && 'bg-amber-500/10 border border-amber-500/20',
                      t.type === 'info' && 'bg-blue-500/10 border border-blue-500/20',
                    )}
                  >
                    <span className="text-base mt-0.5">
                      {t.type === 'success' ? '\u2705' : t.type === 'warning' ? '\u26a0\ufe0f' : '\u{1f4ca}'}
                    </span>
                    <span className={clsx(
                      t.type === 'success' && 'text-emerald-300',
                      t.type === 'warning' && 'text-amber-300',
                      t.type === 'info' && 'text-blue-300',
                    )}>
                      {t.text}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tier Accuracy */}
          {byTier.length > 0 && (
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">Tier Accuracy — Is the System Predictive?</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {byTier.map((t: any) => (
                  <div
                    key={t.tier}
                    className="rounded-lg border p-4 text-center"
                    style={{ borderColor: `${TIER_COLORS[t.tier] || '#6b7280'}40` }}
                  >
                    <div className="text-2xl mb-1">{TIER_EMOJI[t.tier] || ''}</div>
                    <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: TIER_COLORS[t.tier] }}>
                      {t.tier}
                    </div>
                    <div className={clsx(
                      'text-2xl font-bold',
                      t.win_rate >= 60 ? 'text-emerald-400' : t.win_rate >= 40 ? 'text-amber-400' : 'text-red-400'
                    )}>
                      {t.win_rate}%
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      {t.wins}W / {t.total - t.wins}L ({t.total} signals)
                    </div>
                    <div className={clsx(
                      'text-xs font-mono mt-1',
                      (t.avg_return || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                    )}>
                      {t.avg_return >= 0 ? '+' : ''}{t.avg_return}% avg
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Win Rate by Chain */}
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">Win Rate by Chain</h2>
              {byChain.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={byChain.map((c: any) => ({ ...c, chain: c.chain?.toUpperCase() }))} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} />
                    <YAxis dataKey="chain" type="category" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} width={80} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="win_rate" name="Win Rate %" fill="#3b82f6" radius={[0, 4, 4, 0]} opacity={0.8} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-sm text-slate-600">No data yet</div>
              )}
            </div>

            {/* Win Rate by Hour */}
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">Win Rate by Hour (UTC)</h2>
              {byHour.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={hourChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="hour" tick={{ fontSize: 8, fill: '#475569' }} axisLine={false} interval={2} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="win_rate" name="Win Rate %" fill="#8b5cf6" radius={[4, 4, 0, 0]} opacity={0.7}>
                      {hourChartData.map((entry, i) => (
                        <rect key={i} fill={entry.win_rate >= 50 ? '#10b981' : entry.win_rate > 0 ? '#ef4444' : '#334155'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-sm text-slate-600">No data yet</div>
              )}
            </div>
          </div>

          {/* MC Range + Session */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* MC Range */}
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 overflow-hidden">
              <div className="px-5 py-4 border-b border-dark-400/30">
                <h2 className="text-sm font-semibold text-slate-300">Win Rate by Market Cap Range</h2>
                <p className="text-[10px] text-slate-600 mt-0.5">Which MC entry zones are most profitable?</p>
              </div>
              {byMc.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-[10px] text-slate-600 uppercase tracking-wider">
                        <th className="px-5 py-3">MC Range</th>
                        <th className="px-3 py-3">Signals</th>
                        <th className="px-3 py-3">Win Rate</th>
                        <th className="px-3 py-3">Avg Return</th>
                        <th className="px-3 py-3">Runners</th>
                      </tr>
                    </thead>
                    <tbody>
                      {byMc.map((row: any) => (
                        <tr key={row.bucket} className="border-t border-dark-400/20 table-row-hover transition-colors">
                          <td className="px-5 py-3 font-medium text-slate-300">{row.bucket}</td>
                          <td className="px-3 py-3 text-slate-400">{row.total}</td>
                          <td className={clsx('px-3 py-3 font-mono font-semibold', row.win_rate >= 50 ? 'text-emerald-400' : 'text-red-400')}>
                            {row.win_rate}%
                          </td>
                          <td className={clsx('px-3 py-3 font-mono', row.avg_return >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                            {row.avg_return >= 0 ? '+' : ''}{row.avg_return}%
                          </td>
                          <td className="px-3 py-3 text-amber-400 font-mono">{row.runners}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="h-32 flex items-center justify-center text-sm text-slate-600">No data yet</div>
              )}
            </div>

            {/* Session Performance */}
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-1">Performance by Trading Session</h2>
              <p className="text-[10px] text-slate-600 mb-4">Asia / EU / US session win rates</p>
              {sessionRadar.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <RadarChart data={sessionRadar}>
                    <PolarGrid stroke="#1e293b" />
                    <PolarAngleAxis dataKey="session" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#475569' }} />
                    <Radar name="Win Rate" dataKey="win_rate" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
                  </RadarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-sm text-slate-600">No session data yet</div>
              )}
            </div>
          </div>

          {/* Caller Performance */}
          {byCaller.length > 0 && (
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 overflow-hidden">
              <div className="px-5 py-4 border-b border-dark-400/30">
                <h2 className="text-sm font-semibold text-slate-300">Caller Win Rates</h2>
                <p className="text-[10px] text-slate-600 mt-0.5">Who gives the best signals?</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[10px] text-slate-600 uppercase tracking-wider">
                      <th className="px-5 py-3">Caller</th>
                      <th className="px-3 py-3">Signals</th>
                      <th className="px-3 py-3">Win Rate</th>
                      <th className="px-3 py-3">Avg Return</th>
                      <th className="px-3 py-3">Runners</th>
                      <th className="px-3 py-3">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byCaller.map((row: any) => (
                      <tr key={row.sender_id} className="border-t border-dark-400/20 table-row-hover transition-colors">
                        <td className="px-5 py-3 font-medium text-slate-300">{row.sender_name}</td>
                        <td className="px-3 py-3 text-slate-400">{row.total}</td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-16 bg-dark-600 rounded-full h-2 overflow-hidden">
                              <div
                                className={clsx(
                                  'h-2 rounded-full',
                                  row.win_rate >= 60 ? 'bg-emerald-400' : row.win_rate >= 40 ? 'bg-amber-400' : 'bg-red-400'
                                )}
                                style={{ width: `${Math.min(100, row.win_rate)}%` }}
                              />
                            </div>
                            <span className={clsx(
                              'font-mono font-semibold text-xs',
                              row.win_rate >= 60 ? 'text-emerald-400' : row.win_rate >= 40 ? 'text-amber-400' : 'text-red-400'
                            )}>
                              {row.win_rate}%
                            </span>
                          </div>
                        </td>
                        <td className={clsx('px-3 py-3 font-mono', row.avg_return >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {row.avg_return >= 0 ? '+' : ''}{row.avg_return}%
                        </td>
                        <td className="px-3 py-3 text-amber-400 font-mono">{row.runners}</td>
                        <td className="px-3 py-3">
                          <span className={clsx(
                            'px-2 py-0.5 rounded-full text-xs font-semibold',
                            row.score >= 70 ? 'bg-emerald-500/20 text-emerald-400' :
                            row.score >= 40 ? 'bg-amber-500/20 text-amber-400' :
                            'bg-slate-500/20 text-slate-400'
                          )}>
                            {row.score}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Top Signals */}
          {topSignals.length > 0 && (
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 overflow-hidden">
              <div className="px-5 py-4 border-b border-dark-400/30">
                <h2 className="text-sm font-semibold text-slate-300">Top Performing Signals</h2>
                <p className="text-[10px] text-slate-600 mt-0.5">Best returns from checked signals</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[10px] text-slate-600 uppercase tracking-wider">
                      <th className="px-5 py-3">Token</th>
                      <th className="px-3 py-3">Chain</th>
                      <th className="px-3 py-3">Tier</th>
                      <th className="px-3 py-3">Entry MC</th>
                      <th className="px-3 py-3">Return</th>
                      <th className="px-3 py-3">Caller</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topSignals.map((s: any) => (
                      <tr key={s.id} className="border-t border-dark-400/20 table-row-hover transition-colors">
                        <td className="px-5 py-3 font-medium text-white">
                          {s.token}
                          {s.is_runner && <span className="ml-1.5 text-amber-400 text-[10px]">RUNNER</span>}
                        </td>
                        <td className="px-3 py-3 text-slate-400 uppercase text-xs">{s.chain}</td>
                        <td className="px-3 py-3">
                          {s.tier && (
                            <span style={{ color: TIER_COLORS[s.tier] || '#94a3b8' }} className="text-xs font-semibold uppercase">
                              {TIER_EMOJI[s.tier] || ''} {s.tier}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-slate-400 font-mono text-xs">
                          {s.mc ? `$${(s.mc / 1000).toFixed(0)}K` : 'N/A'}
                        </td>
                        <td className={clsx(
                          'px-3 py-3 font-mono font-bold',
                          (s.return_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                        )}>
                          {s.return_pct >= 0 ? '+' : ''}{s.return_pct?.toFixed(1)}%
                          {s.multiplier && s.multiplier > 1 && (
                            <span className="text-amber-400 text-[10px] ml-1">({s.multiplier.toFixed(1)}x)</span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-slate-400 text-xs">{s.caller}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Empty state */}
          {(readiness?.checked_signals ?? 0) === 0 && (
            <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-12 text-center">
              <div className="text-4xl mb-4">{'\u{1f4ca}'}</div>
              <h2 className="text-lg font-semibold text-white mb-2">No Insights Yet</h2>
              <p className="text-sm text-slate-500 max-w-md mx-auto">
                Insights will appear here as your bot processes signals and their 1h/6h performance checks complete.
                Keep the bot running — every checked signal makes these insights more reliable.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
