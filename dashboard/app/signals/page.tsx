'use client';
import { useState } from 'react';
import SignalCard from '@/components/SignalCard';
import { useSignals } from '@/lib/hooks';

const statusFilters = ['all', 'active', 'win', 'loss'];

export default function SignalsPage() {
  const [status, setStatus] = useState('all');
  const { data, isLoading } = useSignals({
    status: status === 'all' ? undefined : status,
    limit: 50,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Signals</h1>
        <div className="flex gap-2">
          {statusFilters.map((f) => (
            <button
              key={f}
              onClick={() => setStatus(f)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                status === f
                  ? 'bg-blue-500 text-white'
                  : 'bg-[#334155] text-slate-400 hover:text-white'
              }`}
            >
              {f.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {data && (
        <p className="text-xs text-slate-500">{data.total} signals total</p>
      )}

      {isLoading ? (
        <p className="text-slate-400">Loading signals...</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {data?.signals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
          {(!data?.signals || data.signals.length === 0) && (
            <p className="text-slate-500">No signals found.</p>
          )}
        </div>
      )}
    </div>
  );
}
