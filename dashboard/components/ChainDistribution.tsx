'use client';
import clsx from 'clsx';

const chainColors: Record<string, { bar: string; text: string }> = {
  solana: { bar: 'bg-purple-500', text: 'text-purple-400' },
  ethereum: { bar: 'bg-blue-500', text: 'text-blue-400' },
  bsc: { bar: 'bg-yellow-500', text: 'text-yellow-400' },
  base: { bar: 'bg-sky-500', text: 'text-sky-400' },
  arbitrum: { bar: 'bg-indigo-500', text: 'text-indigo-400' },
  polygon: { bar: 'bg-violet-500', text: 'text-violet-400' },
};

export default function ChainDistribution({ chains }: { chains: Record<string, number> }) {
  const total = Object.values(chains).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const sorted = Object.entries(chains).sort(([, a], [, b]) => b - a);

  return (
    <div className="space-y-3">
      {sorted.map(([chain, count]) => {
        const pct = (count / total) * 100;
        const cc = chainColors[chain.toLowerCase()] || { bar: 'bg-slate-500', text: 'text-slate-400' };
        return (
          <div key={chain}>
            <div className="flex items-center justify-between mb-1">
              <span className={clsx('text-xs font-medium uppercase', cc.text)}>{chain}</span>
              <span className="text-[11px] text-slate-500">{count} ({pct.toFixed(0)}%)</span>
            </div>
            <div className="h-1.5 bg-dark-500 rounded-full overflow-hidden">
              <div
                className={clsx('h-full rounded-full transition-all duration-700', cc.bar)}
                style={{ width: `${pct}%`, opacity: 0.7 }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
