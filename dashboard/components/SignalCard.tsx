'use client';
import type { Signal, LivePrice } from '@/lib/api';
import Link from 'next/link';
import clsx from 'clsx';
import { formatPrice, formatCurrency, timeAgo } from '@/lib/format';

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

const tierConfig: Record<string, { bg: string; text: string; label: string; icon: string }> = {
  gold: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'GOLD', icon: '\u{1F947}' },
  silver: { bg: 'bg-slate-400/20', text: 'text-slate-300', label: 'SILVER', icon: '\u{1F948}' },
  bronze: { bg: 'bg-orange-700/20', text: 'text-orange-500', label: 'BRONZE', icon: '\u{1F949}' },
};

const momentumConfig: Record<string, { bg: string; text: string; label: string }> = {
  early_runner: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'EARLY RUNNER' },
  confirmed: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'CONFIRMED' },
  holding: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'HOLDING' },
  fading: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'FADING' },
  dumped: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'DUMPED' },
};

interface SignalCardProps {
  signal: Signal;
  livePrice?: LivePrice;
}

export default function SignalCard({ signal, livePrice }: SignalCardProps) {
  const chain = (signal.chain || '').toLowerCase();
  const cc = chainConfig[chain] || { bg: 'bg-slate-500/15', text: 'text-slate-400', dot: 'bg-slate-400' };

  // Use live data if available, otherwise fall back to DB stored values
  const currentPrice = livePrice?.price ?? signal.current_price;
  const currentMC = livePrice?.market_cap ?? signal.current_market_cap;

  // Peak = max of stored peak vs live price (live may exceed stored peak between DB updates)
  const peakPrice = Math.max(signal.max_price_seen ?? 0, currentPrice ?? 0) || null;
  const peakMC = Math.max(signal.max_market_cap_seen ?? 0, currentMC ?? 0) || null;

  // Calculate P&L from live data
  let pnl = signal.price_change_percent;
  let multiplier = signal.multiplier;
  if (livePrice?.price && signal.original_price && signal.original_price > 0) {
    pnl = ((livePrice.price - signal.original_price) / signal.original_price) * 100;
    multiplier = livePrice.price / signal.original_price;
  }

  const isWin = pnl !== null && pnl > 0;
  const isLoss = pnl !== null && pnl < 0;

  // Dynamic status: if we have live P&L, override the stored status
  let liveStatus = signal.status;
  if (pnl !== null && signal.original_price) {
    liveStatus = isWin ? 'win' : isLoss ? 'loss' : 'active';
  }
  const sc2 = statusConfig[liveStatus] || statusConfig.active;

  return (
    <Link
      href={`/signals/${signal.id}`}
      className={clsx(
        'group relative overflow-hidden rounded-xl border bg-dark-700 p-4 transition-all duration-300 block cursor-pointer',
        'hover:bg-dark-600 hover:border-dark-300',
        liveStatus === 'win' && 'border-emerald-500/20 hover:border-emerald-500/40',
        liveStatus === 'loss' && 'border-red-500/20 hover:border-red-500/40',
        liveStatus === 'active' && 'border-dark-400/50',
      )}
    >
      {/* Top accent line */}
      <div
        className={clsx(
          'absolute top-0 left-0 right-0 h-[2px]',
          liveStatus === 'win' && 'bg-gradient-to-r from-emerald-500 to-emerald-500/0',
          liveStatus === 'loss' && 'bg-gradient-to-r from-red-500 to-red-500/0',
          liveStatus === 'active' && 'bg-gradient-to-r from-blue-500 to-blue-500/0',
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
            {signal.token_symbol || signal.token_name || (
              signal.token_address
                ? `${signal.token_address.slice(0, 6)}...${signal.token_address.slice(-4)}`
                : 'Unknown'
            )}
          </span>
          {signal.signal_tier && tierConfig[signal.signal_tier] && (
            <span className={clsx('px-1.5 py-0.5 rounded-md text-[10px] font-bold border', tierConfig[signal.signal_tier].bg, tierConfig[signal.signal_tier].text,
              signal.signal_tier === 'gold' ? 'border-yellow-500/30' : 'border-transparent'
            )}>
              {tierConfig[signal.signal_tier].icon} {tierConfig[signal.signal_tier].label}
              {signal.runner_potential_score ? ` ${Math.round(signal.runner_potential_score)}` : ''}
            </span>
          )}
          {signal.runner_alerted === 1 && (
            <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/20 animate-pulse">
              RUNNER
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {livePrice && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" title="Live data" />
          )}
          <span className={clsx('px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider', sc2.bg, sc2.text)}>
            {sc2.label}
          </span>
        </div>
      </div>

      {/* Price & MC grid */}
      <div className="grid grid-cols-3 gap-2 mb-2">
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">Entry</p>
          <p className="text-xs text-slate-300 font-mono">{formatPrice(signal.original_price)}</p>
        </div>
        <div>
          <p className="text-[10px] text-amber-600 uppercase tracking-wider mb-0.5">ATH</p>
          <p className="text-xs text-amber-400 font-mono">{formatPrice(peakPrice)}</p>
        </div>
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">Now</p>
          <p className={clsx('text-xs font-mono', currentPrice ? 'text-white' : 'text-slate-600')}>
            {formatPrice(currentPrice)}
          </p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">Entry MC</p>
          <p className="text-xs text-slate-300 font-mono">{formatCurrency(signal.original_market_cap)}</p>
        </div>
        <div>
          <p className="text-[10px] text-amber-600 uppercase tracking-wider mb-0.5">ATH MC</p>
          <p className="text-xs text-amber-400 font-mono">{formatCurrency(peakMC)}</p>
        </div>
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-0.5">Live MC</p>
          <p className={clsx('text-xs font-mono', currentMC ? 'text-white' : 'text-slate-600')}>
            {formatCurrency(currentMC)}
          </p>
        </div>
      </div>

      {/* Links */}
      {(signal.original_dexscreener_link || signal.signal_link) && (
        <div className="flex items-center gap-2 mb-2">
          {signal.original_dexscreener_link && (
            <a
              href={signal.original_dexscreener_link}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-[10px] text-green-400 hover:text-green-300 bg-green-500/10 px-1.5 py-0.5 rounded transition-colors"
            >
              DexScreener
            </a>
          )}
          {signal.signal_link && (
            <a
              href={signal.signal_link}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 bg-blue-500/10 px-1.5 py-0.5 rounded transition-colors"
            >
              Telegram
            </a>
          )}
        </div>
      )}

      {/* Momentum badges */}
      {(signal.momentum_check_5m || signal.momentum_check_15m) && (
        <div className="flex items-center gap-1.5 mb-2">
          {signal.momentum_check_5m && momentumConfig[signal.momentum_check_5m] && (
            <span className={clsx('px-1.5 py-0.5 rounded text-[9px] font-bold', momentumConfig[signal.momentum_check_5m].bg, momentumConfig[signal.momentum_check_5m].text)}>
              5m: {momentumConfig[signal.momentum_check_5m].label}
            </span>
          )}
          {signal.momentum_check_15m && momentumConfig[signal.momentum_check_15m] && (
            <span className={clsx('px-1.5 py-0.5 rounded text-[9px] font-bold', momentumConfig[signal.momentum_check_15m].bg, momentumConfig[signal.momentum_check_15m].text)}>
              15m: {momentumConfig[signal.momentum_check_15m].label}
            </span>
          )}
        </div>
      )}

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
            {multiplier !== null && multiplier !== undefined && (
              <span className="text-[11px] font-normal text-slate-500 ml-1">
                ({multiplier.toFixed(2)}x)
              </span>
            )}
          </span>
        )}
      </div>
    </Link>
  );
}
