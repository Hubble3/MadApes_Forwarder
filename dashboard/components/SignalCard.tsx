'use client';
import type { Signal } from '@/lib/api';
import Link from 'next/link';
import clsx from 'clsx';

const chainConfig: Record<string, { bg: string; text: string; dot: string }> = {
  solana: { bg: 'bg-purple-500/15', text: 'text-purple-400', dot: 'bg-purple-400' },
  ethereum: { bg: 'bg-blue-500/15', text: 'text-blue-400', dot: 'bg-blue-400' },
  bsc: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  base: { bg: 'bg-blue-500/15', text: 'text-blue-300', dot: 'bg-blue-300' },
  arbitrum: { bg: 'bg-sky-500/15', text: 'text-sky-400', dot: 'bg-sky-400' },
  polygon: { bg: 'bg-violet-500/15', text: 'text-violet-400', dot: 'bg-violet-400' },
};

const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
  active: { bg: 'bg-slate-500/15', text: 'text-slate-400', label: 'ACTIVE' },
  win: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', label: 'WIN' },
  loss: { bg: 'bg-red-500/15', text: 'text-red-400', label: 'LOSS' },
};

function formatPrice(price: number | null): string {
  if (price === null || price === undefined) return 'N/A';
  if (price < 0.0001) return `$${price.toExponential(2)}`;
  if (price < 1) return `$${price.toFixed(6)}`;
  return `$${price.toFixed(2)}`;
}

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return 'N/A';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function SignalCard({ signal }: { signal: Signal }) {
  const chain = (signal.chain || '').toLowerCase();
  const cc = chainConfig[chain] || { bg: 'bg-slate-500/15', text: 'text-slate-400', dot: 'bg-slate-400' };
  const sc = statusConfig[signal.status] || statusConfig.active;
  const pnl = signal.price_change_percent;
  const isWin = pnl !== null && pnl > 0;
  const isLoss = pnl !== null && pnl < 0;

  return (
    <Link
      href={`/signals/${signal.id}`}
      className={clsx(
        'group relative overflow-hidden rounded-xl border bg-dark-700 p-4 transition-all duration-300 block cursor-pointer',
        'hover:bg-dark-600 hover:border-dark-300',
        signal.status === 'win' && 'border-emerald-500/20 hover:border-emerald-500/40',
        signal.status === 'loss' && 'border-red-500/20 hover:border-red-500/40',
        signal.status === 'active' && 'border-dark-400/50',
      )}
    >
      {/* Top accent line */}
      <div
        className={clsx(
          'absolute top-0 left-0 right-0 h-[2px]',
          signal.status === 'win' && 'bg-gradient-to-r from-emerald-500 to-emerald-500/0',
          signal.status === 'loss' && 'bg-gradient-to-r from-red-500 to-red-500/0',
          signal.status === 'active' && 'bg-gradient-to-r from-blue-500 to-blue-500/0',
        )}
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <span className={clsx('inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-semibold', cc.bg, cc.text)}>
            <span className={clsx('w-1.5 h-1.5 rounded-full', cc.dot)} />
            {chain.toUpperCase() || 'ETH'}
          </span>
          <span className="font-semibold text-sm text-white">
            {signal.token_symbol || signal.token_name || signal.token_address?.slice(0, 8)}
          </span>
          {signal.runner_alerted === 1 && (
            <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/20 animate-pulse">
              RUNNER
            </span>
          )}
        </div>
        <span className={clsx('px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider', sc.bg, sc.text)}>
          {sc.label}
        </span>
      </div>

      {/* Price grid */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">Entry</p>
          <p className="text-xs text-slate-300 font-mono">{formatPrice(signal.original_price)}</p>
        </div>
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">Now</p>
          <p className={clsx('text-xs font-mono', signal.current_price ? 'text-slate-300' : 'text-slate-600')}>
            {formatPrice(signal.current_price)}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">MC</p>
          <p className="text-xs text-slate-300 font-mono">{formatCurrency(signal.original_market_cap)}</p>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-dark-400/30">
        <span className="text-[11px] text-slate-600">
          {signal.sender_name} &middot; {timeAgo(signal.original_timestamp)}
        </span>
        {pnl !== null && (
          <span
            className={clsx(
              'text-sm font-bold font-mono',
              isWin && 'text-emerald-400',
              isLoss && 'text-red-400'
            )}
          >
            {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
            {signal.multiplier !== null && (
              <span className="text-[11px] font-normal text-slate-500 ml-1">
                ({signal.multiplier.toFixed(2)}x)
              </span>
            )}
          </span>
        )}
      </div>
    </Link>
  );
}
