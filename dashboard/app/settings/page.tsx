'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import clsx from 'clsx';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.settings.get(),
  });
  const { data: health } = useQuery({
    queryKey: ['settings', 'health'],
    queryFn: () => api.settings.health(),
    refetchInterval: 30000,
  });
  const { data: blockedData } = useQuery({
    queryKey: ['settings', 'blocked'],
    queryFn: () => api.settings.blockedCallers(),
  });
  const { data: blacklistData } = useQuery({
    queryKey: ['settings', 'blacklist'],
    queryFn: () => api.settings.blacklist(),
  });

  // Block caller form
  const [blockForm, setBlockForm] = useState({ sender_id: '', sender_name: '', reason: '' });
  const blockMutation = useMutation({
    mutationFn: () => api.settings.blockCaller(Number(blockForm.sender_id), blockForm.sender_name, blockForm.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'blocked'] });
      setBlockForm({ sender_id: '', sender_name: '', reason: '' });
    },
  });

  const unblockMutation = useMutation({
    mutationFn: (sender_id: number) => api.settings.unblockCaller(sender_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings', 'blocked'] }),
  });

  // Blacklist form
  const [blForm, setBlForm] = useState({ address: '', chain: 'solana', reason: '' });
  const addBlMutation = useMutation({
    mutationFn: () => api.settings.addBlacklist(blForm.address, blForm.chain, blForm.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'blacklist'] });
      setBlForm({ address: '', chain: 'solana', reason: '' });
    },
  });
  const removeBlMutation = useMutation({
    mutationFn: (address: string) => api.settings.removeBlacklist(address),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings', 'blacklist'] }),
  });

  // Signal override form
  const [overrideForm, setOverrideForm] = useState({ signal_id: '', status: 'win' });
  const overrideMutation = useMutation({
    mutationFn: () => api.settings.overrideSignalStatus(Number(overrideForm.signal_id), overrideForm.status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
      setOverrideForm({ signal_id: '', status: 'win' });
    },
  });

  // Note form
  const [noteForm, setNoteForm] = useState({ signal_id: '', note: '' });
  const noteMutation = useMutation({
    mutationFn: () => api.settings.addSignalNote(Number(noteForm.signal_id), noteForm.note),
    onSuccess: () => setNoteForm({ signal_id: '', note: '' }),
  });

  const blocked = blockedData?.blocked || blockedData?.callers || [];
  const blacklist = blacklistData?.blacklist || blacklistData?.tokens || [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Settings</h1>
        <p className="text-sm text-slate-500 mt-1">Bot configuration and management tools</p>
      </div>

      {/* System Health */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">System Health</h2>
        {health ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Database</p>
              <p className="text-sm font-medium text-emerald-400">Connected</p>
              {health.total_signals != null && (
                <p className="text-[10px] text-slate-600">{health.total_signals} signals</p>
              )}
            </div>
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Redis</p>
              <p className={clsx('text-sm font-medium', health.redis_connected ? 'text-emerald-400' : 'text-yellow-400')}>
                {health.redis_connected ? 'Connected' : 'Offline (optional)'}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Uptime</p>
              <p className="text-sm font-medium text-white">{health.uptime || 'N/A'}</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Active Callers</p>
              <p className="text-sm font-medium text-white">{health.total_callers ?? 'N/A'}</p>
            </div>
          </div>
        ) : (
          <div className="h-16 animate-shimmer rounded" />
        )}
      </div>

      {/* Current Settings */}
      {settings && (
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Current Configuration</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            {Object.entries(settings).filter(([k]) => !k.startsWith('_')).map(([key, value]) => (
              <div key={key} className="flex justify-between items-center py-2 border-b border-dark-400/20">
                <span className="text-slate-400 font-mono text-xs">{key}</span>
                <span className="text-white font-mono text-xs truncate max-w-[200px]">
                  {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value ?? 'N/A')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Blocked Callers */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Blocked Callers</h2>

          <div className="space-y-3 mb-4">
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="Sender ID"
                value={blockForm.sender_id}
                onChange={(e) => setBlockForm({ ...blockForm, sender_id: e.target.value })}
                className="flex-1 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
              />
              <input
                placeholder="Name"
                value={blockForm.sender_name}
                onChange={(e) => setBlockForm({ ...blockForm, sender_name: e.target.value })}
                className="flex-1 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
              />
            </div>
            <div className="flex gap-2">
              <input
                placeholder="Reason"
                value={blockForm.reason}
                onChange={(e) => setBlockForm({ ...blockForm, reason: e.target.value })}
                className="flex-1 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
              />
              <button
                onClick={() => blockMutation.mutate()}
                disabled={!blockForm.sender_id || blockMutation.isPending}
                className="px-4 py-2 bg-red-500/20 text-red-400 text-sm font-medium rounded-lg hover:bg-red-500/30 transition-colors disabled:opacity-50"
              >
                Block
              </button>
            </div>
          </div>

          {blocked.length > 0 ? (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {blocked.map((c: any) => (
                <div key={c.sender_id} className="flex items-center justify-between py-2 px-3 bg-dark-600 rounded-lg">
                  <div>
                    <span className="text-sm text-white">{c.sender_name}</span>
                    <span className="text-xs text-slate-600 ml-2">ID: {c.sender_id}</span>
                    {c.reason && <p className="text-[10px] text-slate-500">{c.reason}</p>}
                  </div>
                  <button
                    onClick={() => unblockMutation.mutate(c.sender_id)}
                    className="text-xs text-emerald-400 hover:text-emerald-300"
                  >
                    Unblock
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No blocked callers.</p>
          )}
        </div>

        {/* Contract Blacklist */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Contract Blacklist</h2>

          <div className="space-y-3 mb-4">
            <input
              placeholder="Contract address"
              value={blForm.address}
              onChange={(e) => setBlForm({ ...blForm, address: e.target.value })}
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50 font-mono"
            />
            <div className="flex gap-2">
              <select
                value={blForm.chain}
                onChange={(e) => setBlForm({ ...blForm, chain: e.target.value })}
                className="bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50"
              >
                <option value="solana">Solana</option>
                <option value="ethereum">Ethereum</option>
                <option value="bsc">BSC</option>
                <option value="base">Base</option>
                <option value="arbitrum">Arbitrum</option>
              </select>
              <input
                placeholder="Reason"
                value={blForm.reason}
                onChange={(e) => setBlForm({ ...blForm, reason: e.target.value })}
                className="flex-1 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
              />
              <button
                onClick={() => addBlMutation.mutate()}
                disabled={!blForm.address || addBlMutation.isPending}
                className="px-4 py-2 bg-red-500/20 text-red-400 text-sm font-medium rounded-lg hover:bg-red-500/30 transition-colors disabled:opacity-50"
              >
                Add
              </button>
            </div>
          </div>

          {blacklist.length > 0 ? (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {blacklist.map((item: any) => (
                <div key={item.address} className="flex items-center justify-between py-2 px-3 bg-dark-600 rounded-lg">
                  <div>
                    <span className="text-xs text-white font-mono">{item.address.slice(0, 8)}...{item.address.slice(-6)}</span>
                    <span className="text-[10px] text-slate-500 ml-2 uppercase">{item.chain}</span>
                    {item.reason && <p className="text-[10px] text-slate-500">{item.reason}</p>}
                  </div>
                  <button
                    onClick={() => removeBlMutation.mutate(item.address)}
                    className="text-xs text-emerald-400 hover:text-emerald-300"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No blacklisted contracts.</p>
          )}
        </div>
      </div>

      {/* Signal Management */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Override Status */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Override Signal Status</h2>
          <div className="flex gap-2">
            <input
              type="number"
              placeholder="Signal ID"
              value={overrideForm.signal_id}
              onChange={(e) => setOverrideForm({ ...overrideForm, signal_id: e.target.value })}
              className="w-28 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
            />
            <select
              value={overrideForm.status}
              onChange={(e) => setOverrideForm({ ...overrideForm, status: e.target.value })}
              className="bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50"
            >
              <option value="win">Win</option>
              <option value="loss">Loss</option>
              <option value="active">Active</option>
              <option value="neutral">Neutral</option>
            </select>
            <button
              onClick={() => overrideMutation.mutate()}
              disabled={!overrideForm.signal_id || overrideMutation.isPending}
              className="px-4 py-2 bg-blue-500/20 text-blue-400 text-sm font-medium rounded-lg hover:bg-blue-500/30 transition-colors disabled:opacity-50"
            >
              Override
            </button>
          </div>
          {overrideMutation.isSuccess && <p className="text-xs text-emerald-400 mt-2">Status updated.</p>}
          {overrideMutation.isError && <p className="text-xs text-red-400 mt-2">Failed to update.</p>}
        </div>

        {/* Add Note */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Add Signal Note</h2>
          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="Signal ID"
                value={noteForm.signal_id}
                onChange={(e) => setNoteForm({ ...noteForm, signal_id: e.target.value })}
                className="w-28 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
              />
              <input
                placeholder="Note text"
                value={noteForm.note}
                onChange={(e) => setNoteForm({ ...noteForm, note: e.target.value })}
                className="flex-1 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
              />
              <button
                onClick={() => noteMutation.mutate()}
                disabled={!noteForm.signal_id || !noteForm.note || noteMutation.isPending}
                className="px-4 py-2 bg-blue-500/20 text-blue-400 text-sm font-medium rounded-lg hover:bg-blue-500/30 transition-colors disabled:opacity-50"
              >
                Save
              </button>
            </div>
            {noteMutation.isSuccess && <p className="text-xs text-emerald-400">Note saved.</p>}
          </div>
        </div>
      </div>

      {/* Data Export */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Data Export</h2>
        <div className="flex gap-3">
          <button
            onClick={async () => {
              const data = await api.settings.exportSignals();
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `signals_export_${new Date().toISOString().slice(0, 10)}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="px-4 py-2 bg-dark-600 text-slate-300 text-sm font-medium rounded-lg hover:bg-dark-500 transition-colors border border-dark-400/50"
          >
            Export Signals
          </button>
          <button
            onClick={async () => {
              const data = await api.settings.exportCallers();
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `callers_export_${new Date().toISOString().slice(0, 10)}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="px-4 py-2 bg-dark-600 text-slate-300 text-sm font-medium rounded-lg hover:bg-dark-500 transition-colors border border-dark-400/50"
          >
            Export Callers
          </button>
        </div>
      </div>
    </div>
  );
}
