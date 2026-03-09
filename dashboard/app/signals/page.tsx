'use client';
import { useState } from 'react';
import SignalCard from '@/components/SignalCard';
import { SkeletonSignal } from '@/components/Skeleton';
import { useSignals, useLivePrices } from '@/lib/hooks';
import clsx from 'clsx';

const statusFilters = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'win', label: 'Win' },
  { key: 'loss', label: 'Loss' },
];

const chainFilters = [
  { key: '', label: 'All Chains' },
  { key: 'solana', label: 'Solana' },
  { key: 'ethereum', label: 'Ethereum' },
  { key: 'bsc', label: 'BSC' },
  { key: 'base', label: 'Base' },
];

export default function SignalsPage() {
  const [status, setStatus] = useState('all');
  const [chain, setChain] = useState('');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const { data, isLoading } = useSignals({
    status: status === 'all' ? undefined : status,
    chain: chain || undefined,
    search: search || undefined,
    limit: 50,
  });

  const { data: livePriceData } = useLivePrices();
  const livePrices = livePriceData?.prices || {};

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Signals</h1>
          {data && (
            <p className="text-sm text-slate-500 mt-1">{data.total} signals total</p>
          )}
        </div>
        {livePriceData && (
          <div className="flex items-center gap-1.5 text-[11px] text-slate-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live prices (30s)
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 min-w-[200px] max-w-md">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search token name, symbol, or address..."
              className="w-full bg-dark-700 border border-dark-400/30 rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all"
            />
            {search && (
              <button
                type="button"
                onClick={() => { setSearch(''); setSearchInput(''); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </form>

        {/* Status filter */}
        <div className="flex items-center gap-1 bg-dark-700 rounded-lg p-1 border border-dark-400/30">
          {statusFilters.map((f) => (
            <button
              key={f.key}
              onClick={() => setStatus(f.key)}
              className={clsx(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200',
                status === f.key
                  ? 'bg-blue-500/20 text-blue-400 shadow-sm'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-dark-600'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Chain filter */}
        <select
          value={chain}
          onChange={(e) => setChain(e.target.value)}
          className="bg-dark-700 border border-dark-400/30 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-blue-500/50 appearance-none cursor-pointer"
        >
          {chainFilters.map((f) => (
            <option key={f.key} value={f.key}>{f.label}</option>
          ))}
        </select>
      </div>

      {/* Signals grid */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonSignal key={i} />)}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data?.signals.map((signal) => (
            <SignalCard
              key={signal.id}
              signal={signal}
              livePrice={livePrices[String(signal.id)]}
            />
          ))}
          {(!data?.signals || data.signals.length === 0) && (
            <div className="col-span-2 py-12 text-center">
              <svg className="w-10 h-10 mx-auto mb-3 text-slate-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <p className="text-slate-600">No signals found.</p>
              {search && <p className="text-xs text-slate-700 mt-1">Try a different search term</p>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
