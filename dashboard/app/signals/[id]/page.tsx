'use client';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useSignal } from '@/lib/hooks';
import clsx from 'clsx';
import { formatPrice, formatCurrency, formatTime, shortAddr } from '@/lib/format';

const chainConfig: Record<string, { bg: string; text: string }> = {
  solana: { bg: 'bg-purple-500/15', text: 'text-purple-400' },
  ethereum: { bg: 'bg-blue-500/15', text: 'text-blue-400' },
  bsc: { bg: 'bg-yellow-500/15', text: 'text-yellow-400' },
  base: { bg: 'bg-sky-500/15', text: 'text-sky-400' },
  arbitrum: { bg: 'bg-sky-500/15', text: 'text-sky-300' },
};

export default function SignalDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const { data, isLoading, error } = useSignal(id);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 rounded animate-shimmer" />
        <div className="h-64 rounded-xl animate-shimmer" />
      </div>
    );
  }

  if (error || !data?.signal) {
    return (
      <div className="space-y-4">
        <Link href="/signals" className="text-sm text-blue-400 hover:text-blue-300">&larr; Back to Signals</Link>
        <div className="py-12 text-center text-slate-600">Signal not found.</div>
      </div>
    );
  }

  const s = data.signal;
  const chain = (s.chain || '').toLowerCase();
  const cc = chainConfig[chain] || { bg: 'bg-slate-500/15', text: 'text-slate-400' };
  const pnl = s.price_change_percent;
  const isWin = pnl !== null && pnl > 0;
  const isLoss = pnl !== null && pnl < 0;

  const detailRows = [
    { label: 'Token Address', value: s.token_address, mono: true },
    { label: 'Token Name', value: s.token_name || 'Unknown' },
    { label: 'Token Symbol', value: s.token_symbol || 'Unknown' },
    { label: 'Chain', value: chain.toUpperCase() },
    { label: 'Status', value: s.status.toUpperCase() },
    { label: 'Entry Price', value: formatPrice(s.original_price), mono: true },
    { label: 'Current Price', value: formatPrice(s.current_price), mono: true },
    { label: 'Market Cap (Entry)', value: formatCurrency(s.original_market_cap) },
    { label: 'Current Market Cap', value: formatCurrency(s.current_market_cap) },
    { label: 'Liquidity', value: formatCurrency(s.original_liquidity) },
    { label: 'Volume', value: formatCurrency(s.original_volume) },
    { label: 'P&L', value: pnl !== null ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}%` : 'N/A', color: isWin ? 'text-emerald-400' : isLoss ? 'text-red-400' : undefined },
    { label: 'Multiplier', value: s.multiplier !== null ? `${s.multiplier.toFixed(2)}x` : 'N/A' },
    { label: 'Caller', value: s.sender_name },
    { label: 'Source Group', value: s.source_group || 'N/A' },
    { label: 'Destination', value: s.destination_type || 'N/A' },
    { label: 'Detected At', value: formatTime(s.original_timestamp) },
    { label: 'Runner Alert', value: s.runner_alerted ? 'Yes' : 'No', color: s.runner_alerted ? 'text-orange-400' : undefined },
    { label: 'Confidence', value: s.confidence_score !== null && s.confidence_score !== undefined ? `${s.confidence_score}/100` : 'N/A' },
    { label: 'Tags', value: s.tags || 'None' },
  ];

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link href="/signals" className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300 transition-colors">
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Signals
      </Link>

      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className={clsx('px-2.5 py-1 rounded-lg text-xs font-bold', cc.bg, cc.text)}>
          {chain.toUpperCase()}
        </span>
        <h1 className="text-2xl font-bold text-white">
          {s.token_symbol || s.token_name || shortAddr(s.token_address)}
        </h1>
        <span className={clsx(
          'px-2 py-0.5 rounded text-[10px] font-bold tracking-wider',
          s.status === 'win' && 'bg-emerald-500/15 text-emerald-400',
          s.status === 'loss' && 'bg-red-500/15 text-red-400',
          s.status === 'active' && 'bg-slate-500/15 text-slate-400',
        )}>
          {s.status.toUpperCase()}
        </span>
        {s.runner_alerted === 1 && (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-orange-500/20 text-orange-400">RUNNER</span>
        )}
      </div>

      {/* Quick Links */}
      {(s.original_dexscreener_link || s.signal_link) && (
        <div className="flex items-center gap-3">
          {s.original_dexscreener_link && (
            <a
              href={s.original_dexscreener_link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm font-medium hover:bg-green-500/20 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
              DexScreener
            </a>
          )}
          {s.signal_link && (
            <a
              href={s.signal_link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium hover:bg-blue-500/20 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
              Telegram Source
            </a>
          )}
        </div>
      )}

      {/* P&L Hero */}
      {pnl !== null && (
        <div className={clsx(
          'rounded-xl border p-6 text-center',
          isWin && 'bg-emerald-500/5 border-emerald-500/20 glow-green',
          isLoss && 'bg-red-500/5 border-red-500/20 glow-red',
          !isWin && !isLoss && 'bg-dark-700 border-dark-400/30',
        )}>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Price Change</p>
          <p className={clsx('text-4xl font-bold font-mono', isWin ? 'text-emerald-400' : isLoss ? 'text-red-400' : 'text-white')}>
            {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
          </p>
          {s.multiplier !== null && (
            <p className="text-sm text-slate-500 mt-1">{s.multiplier.toFixed(2)}x multiplier</p>
          )}
        </div>
      )}

      {/* Detail grid */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 overflow-hidden">
        <div className="px-5 py-4 border-b border-dark-400/30">
          <h2 className="text-sm font-semibold text-slate-300">Signal Details</h2>
        </div>
        <div className="divide-y divide-dark-400/20">
          {detailRows.map((row) => (
            <div key={row.label} className="flex items-center justify-between px-5 py-3 table-row-hover transition-colors">
              <span className="text-xs text-slate-500">{row.label}</span>
              <span className={clsx(
                'text-sm',
                row.color || 'text-slate-300',
                row.mono && 'font-mono text-xs',
              )}>
                {row.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
