'use client';
import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useSignal, useLivePrices } from '@/lib/hooks';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
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
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = Number(params.id);
  const { data, isLoading, error } = useSignal(id);
  const { data: livePriceData } = useLivePrices();
  const livePrice = livePriceData?.prices?.[String(id)];
  const [confirmDelete, setConfirmDelete] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: () => api.settings.deleteSignal(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
      router.push('/signals');
    },
  });

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

  // Use live data if available
  const currentPrice = livePrice?.price ?? s.current_price;
  const currentMC = livePrice?.market_cap ?? s.current_market_cap;

  // Peak = max of stored peak vs live price
  const peakPrice = Math.max(s.max_price_seen ?? 0, currentPrice ?? 0) || null;
  const peakMC = Math.max(s.max_market_cap_seen ?? 0, currentMC ?? 0) || null;

  let pnl = s.price_change_percent;
  let multiplier = s.multiplier;
  if (livePrice?.price && s.original_price && s.original_price > 0) {
    pnl = ((livePrice.price - s.original_price) / s.original_price) * 100;
    multiplier = livePrice.price / s.original_price;
  }

  const isWin = pnl !== null && pnl > 0;
  const isLoss = pnl !== null && pnl < 0;

  // Dynamic status based on live P&L
  let liveStatus = s.status;
  if (pnl !== null && s.original_price) {
    liveStatus = isWin ? 'win' : isLoss ? 'loss' : 'active';
  }

  const detailRows = [
    { label: 'Token Address', value: s.token_address, mono: true },
    { label: 'Token Name', value: s.token_name || 'Unknown' },
    { label: 'Token Symbol', value: s.token_symbol || 'Unknown' },
    { label: 'Chain', value: chain.toUpperCase() },
    { label: 'Status', value: liveStatus.toUpperCase(), color: liveStatus === 'win' ? 'text-emerald-400' : liveStatus === 'loss' ? 'text-red-400' : undefined },
    { label: 'Entry Price', value: formatPrice(s.original_price), mono: true },
    { label: 'ATH Price', value: formatPrice(peakPrice), mono: true, color: peakPrice ? 'text-amber-400' : undefined },
    { label: 'Live Price', value: formatPrice(currentPrice), mono: true, color: livePrice ? 'text-white' : undefined },
    { label: 'Entry Market Cap', value: formatCurrency(s.original_market_cap) },
    { label: 'ATH Market Cap', value: formatCurrency(peakMC), color: peakMC ? 'text-amber-400' : undefined },
    { label: 'Live Market Cap', value: formatCurrency(currentMC), color: livePrice ? 'text-white' : undefined },
    { label: 'Liquidity', value: formatCurrency(livePrice?.liquidity ?? s.original_liquidity) },
    { label: 'Volume 24h', value: formatCurrency(livePrice?.volume_24h ?? s.original_volume) },
    { label: 'P&L', value: pnl !== null ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}%` : 'N/A', color: isWin ? 'text-emerald-400' : isLoss ? 'text-red-400' : undefined },
    { label: 'Multiplier', value: multiplier !== null && multiplier !== undefined ? `${multiplier.toFixed(2)}x` : 'N/A' },
    { label: 'Caller', value: s.sender_name },
    { label: 'Source Group', value: s.source_group || 'N/A' },
    { label: 'Destination', value: s.destination_type || 'N/A' },
    { label: 'Detected At', value: formatTime(s.original_timestamp) },
    { label: '15m Check', value: s.price_change_15m !== null && s.price_change_15m !== undefined ? `${s.price_change_15m >= 0 ? '+' : ''}${s.price_change_15m.toFixed(2)}% (${(s.multiplier_15m ?? 1).toFixed(2)}x)` : s.checked_15m ? 'No data' : 'Pending', color: s.price_change_15m !== null && s.price_change_15m !== undefined ? (s.price_change_15m > 0 ? 'text-emerald-400' : 'text-red-400') : undefined },
    { label: 'Runner Alert', value: s.runner_alerted ? 'Yes' : 'No', color: s.runner_alerted ? 'text-orange-400' : undefined },
    { label: 'Confidence', value: s.confidence_score !== null && s.confidence_score !== undefined ? `${s.confidence_score}/100` : 'N/A', color: s.confidence_score !== null && s.confidence_score !== undefined ? (s.confidence_score >= 50 ? 'text-emerald-400' : s.confidence_score >= 35 ? 'text-yellow-400' : 'text-red-400') : undefined },
    { label: 'Safety Score', value: s.safety_score !== null && s.safety_score !== undefined ? `${s.safety_score}/100` : 'Not checked', color: s.safety_score !== null && s.safety_score !== undefined ? (s.safety_score >= 80 ? 'text-emerald-400' : s.safety_score >= 50 ? 'text-yellow-400' : 'text-red-400') : undefined },
    { label: 'Tags', value: s.tags || 'None' },
    { label: 'Signal Quality', value: s.signal_quality ? s.signal_quality.toUpperCase() : 'N/A', color: s.signal_quality === 'valuable' ? 'text-emerald-400' : s.signal_quality === 'junk' ? 'text-red-400' : s.signal_quality === 'borderline' ? 'text-yellow-400' : undefined },
    { label: 'Take-Profit Milestones', value: [s.tp1_hit && '+30%', s.tp2_hit && '+50%', s.tp3_hit && '2x', s.tp4_hit && '3x'].filter(Boolean).join(' → ') || 'None hit', color: (s.tp3_hit || s.tp4_hit) ? 'text-yellow-400' : s.tp1_hit ? 'text-emerald-400' : undefined },
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
          liveStatus === 'win' && 'bg-emerald-500/15 text-emerald-400',
          liveStatus === 'loss' && 'bg-red-500/15 text-red-400',
          liveStatus === 'active' && 'bg-slate-500/15 text-slate-400',
        )}>
          {liveStatus.toUpperCase()}
        </span>
        {s.runner_alerted === 1 && (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-orange-500/20 text-orange-400">RUNNER</span>
        )}
        {s.signal_quality && (
          <span className={clsx(
            'px-2 py-0.5 rounded text-[10px] font-bold',
            s.signal_quality === 'valuable' && 'bg-emerald-500/15 text-emerald-400',
            s.signal_quality === 'borderline' && 'bg-yellow-500/15 text-yellow-400',
            s.signal_quality === 'junk' && 'bg-red-500/15 text-red-400',
          )}>
            {s.signal_quality.toUpperCase()}
          </span>
        )}
        {livePrice && (
          <span className="flex items-center gap-1 text-[10px] text-slate-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live
          </span>
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
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Price Change {livePrice ? '(Live)' : ''}</p>
          <p className={clsx('text-4xl font-bold font-mono', isWin ? 'text-emerald-400' : isLoss ? 'text-red-400' : 'text-white')}>
            {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
          </p>
          {multiplier !== null && multiplier !== undefined && (
            <p className="text-sm text-slate-500 mt-1">{multiplier.toFixed(2)}x multiplier</p>
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

      {/* Delete Signal */}
      <div className="bg-dark-700 rounded-xl border border-red-500/20 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-red-400">Delete Signal</h2>
            <p className="text-xs text-slate-600 mt-0.5">Remove this signal permanently from the database</p>
          </div>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="px-4 py-2 bg-red-500/10 text-red-400 text-sm font-medium rounded-lg hover:bg-red-500/20 transition-colors border border-red-500/20"
            >
              Delete
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-red-400">Are you sure?</span>
              <button
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 bg-red-500/20 text-red-400 text-sm font-bold rounded-lg hover:bg-red-500/30 transition-colors disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Yes, Delete'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-3 py-2 text-slate-400 text-sm rounded-lg hover:bg-dark-600 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
