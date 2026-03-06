import type { Signal } from '@/lib/api';

const chainColors: Record<string, string> = {
  solana: 'bg-purple-500/20 text-purple-400',
  ethereum: 'bg-blue-500/20 text-blue-400',
  bsc: 'bg-yellow-500/20 text-yellow-400',
  base: 'bg-blue-500/20 text-blue-300',
  arbitrum: 'bg-blue-500/20 text-blue-400',
  polygon: 'bg-purple-500/20 text-purple-300',
};

const statusColors: Record<string, string> = {
  active: 'bg-slate-500/20 text-slate-400',
  win: 'bg-green-500/20 text-green-400',
  loss: 'bg-red-500/20 text-red-400',
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

function shortAddr(addr: string): string {
  if (!addr || addr.length < 12) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function SignalCard({ signal }: { signal: Signal }) {
  const chain = (signal.chain || '').toLowerCase();
  const chainClass = chainColors[chain] || 'bg-slate-500/20 text-slate-400';
  const statusClass = statusColors[signal.status] || statusColors.active;
  const pnl = signal.price_change_percent;

  return (
    <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155] hover:border-[#475569] transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${chainClass}`}>
            {(chain || 'ETH').toUpperCase()}
          </span>
          <span className="font-medium text-sm">
            {signal.token_symbol || signal.token_name || shortAddr(signal.token_address)}
          </span>
          {signal.runner_alerted === 1 && (
            <span className="px-1.5 py-0.5 rounded text-xs bg-orange-500/20 text-orange-400">RUNNER</span>
          )}
        </div>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusClass}`}>
          {signal.status.toUpperCase()}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs text-slate-400 mb-2">
        <div>
          <span className="text-slate-500">Entry:</span>{' '}
          {formatPrice(signal.original_price)}
        </div>
        <div>
          <span className="text-slate-500">Now:</span>{' '}
          {formatPrice(signal.current_price)}
        </div>
        <div>
          <span className="text-slate-500">MC:</span>{' '}
          {formatCurrency(signal.original_market_cap)}
        </div>
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-500">
          {signal.sender_name} | {timeAgo(signal.original_timestamp)}
        </span>
        {pnl !== null && (
          <span className={`font-medium ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
            {signal.multiplier && ` (${signal.multiplier.toFixed(2)}x)`}
          </span>
        )}
      </div>
    </div>
  );
}
