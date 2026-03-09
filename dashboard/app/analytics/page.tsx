'use client';
import { useOverview, useAttribution, useDailyAnalytics, usePortfolioSummary } from '@/lib/hooks';
import { SkeletonCard } from '@/components/Skeleton';
import StatCard from '@/components/StatCard';
import clsx from 'clsx';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
  AreaChart, Area,
} from 'recharts';

const COLORS = ['#8b5cf6', '#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#6366f1', '#ec4899'];

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

export default function AnalyticsPage() {
  const { data: overview, isLoading: loadingOverview } = useOverview();
  const { data: attribution, isLoading: loadingAttr } = useAttribution();
  const { data: daily, isLoading: loadingDaily } = useDailyAnalytics(30);
  const { data: portfolio } = usePortfolioSummary();

  // Chain data for pie chart
  const chainData = overview?.chains
    ? Object.entries(overview.chains).map(([chain, count]) => ({
        name: chain.toUpperCase(),
        value: count,
      }))
    : [];

  // Daily chart data
  const dailyData = daily?.days
    ? [...daily.days].reverse().map((d: any) => ({
        date: d.report_date?.slice(5) || '',
        signals: d.total_signals ?? 0,
        wins: d.wins ?? 0,
        losses: d.losses ?? 0,
        winRate: d.win_rate ?? 0,
      }))
    : [];

  // Attribution by chain
  const chainAttr = attribution?.by_chain
    ? Object.entries(attribution.by_chain).map(([chain, data]: [string, any]) => ({
        chain: chain.toUpperCase(),
        signals: data.total || 0,
        winRate: data.win_rate || 0,
        avgReturn: data.avg_return || 0,
      }))
    : [];

  // Attribution by MC range
  const mcAttr = attribution?.by_mc_range
    ? Object.entries(attribution.by_mc_range).map(([range, data]: [string, any]) => ({
        range,
        signals: data.total || 0,
        winRate: data.win_rate || 0,
        avgReturn: data.avg_return || 0,
      }))
    : [];

  // Attribution by hour
  const hourAttr = attribution?.by_hour
    ? Object.entries(attribution.by_hour)
        .map(([hour, data]: [string, any]) => ({
          hour: `${hour}:00`,
          signals: data.total || 0,
          winRate: data.win_rate || 0,
        }))
        .sort((a, b) => parseInt(a.hour) - parseInt(b.hour))
    : [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Analytics</h1>
        <p className="text-sm text-slate-500 mt-1">Performance analytics and signal attribution</p>
      </div>

      {/* Summary stats */}
      {loadingOverview ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Signals" value={overview?.total_signals ?? 0} color="blue" />
          <StatCard
            label="Win Rate"
            value={`${overview?.win_rate ?? 0}%`}
            color={(overview?.win_rate ?? 0) >= 50 ? 'green' : 'red'}
            subtext={`${overview?.wins ?? 0}W / ${overview?.losses ?? 0}L`}
          />
          <StatCard
            label="Total P&L"
            value={portfolio ? `$${portfolio.total_pnl.toFixed(0)}` : '$0'}
            color={portfolio && portfolio.total_pnl >= 0 ? 'green' : 'red'}
          />
          <StatCard label="Runners" value={overview?.runners ?? 0} color="yellow" />
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chain distribution pie */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Chain Distribution</h2>
          {chainData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={chainData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {chainData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} opacity={0.8} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }}
                  formatter={(value: string) => <span className="text-slate-400">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-sm text-slate-600">No data yet</div>
          )}
        </div>

        {/* Daily signals area chart */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Daily Signals</h2>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={dailyData}>
                <defs>
                  <linearGradient id="gradGreen" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradRed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="wins" stackId="1" stroke="#10b981" fill="url(#gradGreen)" name="Wins" />
                <Area type="monotone" dataKey="losses" stackId="1" stroke="#ef4444" fill="url(#gradRed)" name="Losses" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-sm text-slate-600">No daily data yet</div>
          )}
        </div>
      </div>

      {/* Attribution tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By chain */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Performance by Chain</h2>
          {chainAttr.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chainAttr} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} />
                <YAxis dataKey="chain" type="category" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} width={80} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="winRate" name="Win Rate %" fill="#3b82f6" radius={[0, 4, 4, 0]} opacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-sm text-slate-600">No attribution data yet</div>
          )}
        </div>

        {/* By hour */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Signals by Hour (UTC)</h2>
          {hourAttr.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={hourAttr}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="hour" tick={{ fontSize: 9, fill: '#475569' }} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#475569' }} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="signals" name="Signals" fill="#8b5cf6" radius={[4, 4, 0, 0]} opacity={0.7} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-sm text-slate-600">No hour data yet</div>
          )}
        </div>
      </div>

      {/* MC range table */}
      {mcAttr.length > 0 && (
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 overflow-hidden">
          <div className="px-5 py-4 border-b border-dark-400/30">
            <h2 className="text-sm font-semibold text-slate-300">Performance by Market Cap Range</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] text-slate-600 uppercase tracking-wider">
                  <th className="px-5 py-3">MC Range</th>
                  <th className="px-3 py-3">Signals</th>
                  <th className="px-3 py-3">Win Rate</th>
                  <th className="px-3 py-3">Avg Return</th>
                </tr>
              </thead>
              <tbody>
                {mcAttr.map((row) => (
                  <tr key={row.range} className="border-t border-dark-400/20 table-row-hover transition-colors">
                    <td className="px-5 py-3 font-medium text-slate-300">{row.range}</td>
                    <td className="px-3 py-3 text-slate-400">{row.signals}</td>
                    <td className={clsx('px-3 py-3 font-mono', row.winRate >= 50 ? 'text-emerald-400' : 'text-red-400')}>
                      {row.winRate.toFixed(1)}%
                    </td>
                    <td className={clsx('px-3 py-3 font-mono', row.avgReturn >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {row.avgReturn >= 0 ? '+' : ''}{row.avgReturn.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
