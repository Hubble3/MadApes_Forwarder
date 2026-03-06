'use client';
import { useState } from 'react';
import CallerRow from '@/components/CallerRow';
import { useCallers, useLeaderboard } from '@/lib/hooks';

const windows = ['all', '24h', '7d', '30d'];

export default function CallersPage() {
  const [window, setWindow] = useState('all');
  const { data: callerData, isLoading: loadingCallers } = useCallers(2);
  const { data: lbData, isLoading: loadingLb } = useLeaderboard(window);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Caller Leaderboard</h1>

      <div className="flex gap-2">
        {windows.map((w) => (
          <button
            key={w}
            onClick={() => setWindow(w)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              window === w
                ? 'bg-blue-500 text-white'
                : 'bg-[#334155] text-slate-400 hover:text-white'
            }`}
          >
            {w.toUpperCase()}
          </button>
        ))}
      </div>

      {loadingLb ? (
        <p className="text-slate-400">Loading leaderboard...</p>
      ) : (
        <div className="space-y-2">
          {lbData?.leaderboard.map((entry) => {
            const caller = callerData?.callers.find((c) => c.sender_id === entry.sender_id);
            if (!caller) {
              return (
                <div key={entry.sender_id} className="bg-[#1e293b] rounded-lg p-3 border border-[#334155] flex items-center gap-4">
                  <span className="text-lg w-8 text-center">{entry.rank}.</span>
                  <div className="flex-1">
                    <span className="font-medium text-sm">{entry.sender_name}</span>
                    <div className="flex gap-4 text-xs text-slate-400 mt-1">
                      <span>{entry.total_signals} signals</span>
                      <span className="text-green-400">{entry.wins}W</span>
                      <span className="text-red-400">{entry.losses}L</span>
                      <span>WR: {entry.win_rate}%</span>
                    </div>
                  </div>
                  <span className={`text-sm font-medium ${entry.avg_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {entry.avg_return >= 0 ? '+' : ''}{entry.avg_return.toFixed(1)}% avg
                  </span>
                </div>
              );
            }
            return <CallerRow key={caller.sender_id} caller={caller} rank={entry.rank} />;
          })}
          {(!lbData?.leaderboard || lbData.leaderboard.length === 0) && (
            <p className="text-slate-500">No caller data yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
