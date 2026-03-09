'use client';
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import clsx from 'clsx';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: settingsData, isLoading } = useQuery({
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

  const settings = settingsData?.settings;

  // Editable settings state
  const [mcThreshold, setMcThreshold] = useState('');
  const [maxSignals, setMaxSignals] = useState('');
  const [forwardDelay, setForwardDelay] = useState('');
  const [runnerVelocity, setRunnerVelocity] = useState('');
  const [runnerVolAccel, setRunnerVolAccel] = useState('');
  const [runnerPollInterval, setRunnerPollInterval] = useState('');
  const [timezone, setTimezone] = useState('');

  useEffect(() => {
    if (settings) {
      setMcThreshold(String(settings.mc_threshold ?? ''));
      setMaxSignals(String(settings.max_signals ?? ''));
      setForwardDelay(String(settings.forward_delay ?? ''));
      setRunnerVelocity(String(settings.runner_velocity_min ?? ''));
      setRunnerVolAccel(String(settings.runner_vol_accel_min ?? ''));
      setRunnerPollInterval(String(settings.runner_poll_interval ?? ''));
      setTimezone(settings.display_timezone ?? '');
    }
  }, [settings]);

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, any>) => api.settings.update(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });

  // Block caller
  const [blockId, setBlockId] = useState('');
  const [blockReason, setBlockReason] = useState('');
  const blockMutation = useMutation({
    mutationFn: () => api.settings.blockCaller(Number(blockId), '', blockReason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'blocked'] });
      setBlockId('');
      setBlockReason('');
    },
  });
  const unblockMutation = useMutation({
    mutationFn: (sender_id: number) => api.settings.unblockCaller(sender_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings', 'blocked'] }),
  });

  // Blacklist
  const [blAddr, setBlAddr] = useState('');
  const [blChain, setBlChain] = useState('solana');
  const [blReason, setBlReason] = useState('');
  const addBlMutation = useMutation({
    mutationFn: () => api.settings.addBlacklist(blAddr, blChain, blReason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'blacklist'] });
      setBlAddr('');
      setBlReason('');
    },
  });
  const removeBlMutation = useMutation({
    mutationFn: (address: string) => api.settings.removeBlacklist(address),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings', 'blacklist'] }),
  });

  // Signal override
  const [overrideId, setOverrideId] = useState('');
  const [overrideStatus, setOverrideStatus] = useState('win');
  const overrideMutation = useMutation({
    mutationFn: () => api.settings.overrideSignalStatus(Number(overrideId), overrideStatus),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
      setOverrideId('');
    },
  });

  const blocked = blockedData?.blocked_callers || [];
  const blacklist = blacklistData?.blacklist || [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Settings</h1>
        <p className="text-sm text-slate-500 mt-1">Bot configuration and signal filtering</p>
      </div>

      {/* System Health */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">System Health</h2>
        {health ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Database</p>
              <p className="text-sm font-medium text-emerald-400">Connected</p>
              <p className="text-[10px] text-slate-600">{health.db?.total_signals ?? 0} signals, {health.db?.db_file_size_mb ?? 0} MB</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Active Callers</p>
              <p className="text-sm font-medium text-white">{health.db?.total_callers ?? 0}</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Redis</p>
              <p className={clsx('text-sm font-medium', health.redis_status === 'connected' ? 'text-emerald-400' : 'text-slate-500')}>
                {health.redis_status === 'connected' ? 'Connected' : 'Not configured'}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">Session Uptime</p>
              <p className="text-sm font-medium text-white">
                {health.uptime_seconds ? `${Math.floor(health.uptime_seconds / 3600)}h ${Math.floor((health.uptime_seconds % 3600) / 60)}m` : 'N/A'}
              </p>
            </div>
          </div>
        ) : (
          <div className="h-16 animate-shimmer rounded" />
        )}
      </div>

      {/* Signal Routing & Filtering */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Signal Routing & Filtering</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1">Market Cap Threshold (USD)</label>
            <p className="text-[10px] text-slate-600 mb-1.5">Signals below this go to low-cap destination, above to main</p>
            <input
              type="number"
              value={mcThreshold}
              onChange={(e) => setMcThreshold(e.target.value)}
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <div>
            <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1">Max Signals to Retain</label>
            <p className="text-[10px] text-slate-600 mb-1.5">Oldest signals deleted when over capacity</p>
            <input
              type="number"
              value={maxSignals}
              onChange={(e) => setMaxSignals(e.target.value)}
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <div>
            <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1">Forward Delay (seconds)</label>
            <p className="text-[10px] text-slate-600 mb-1.5">Delay between forwarding signals</p>
            <input
              type="number"
              step="0.1"
              value={forwardDelay}
              onChange={(e) => setForwardDelay(e.target.value)}
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <div>
            <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1">Display Timezone</label>
            <p className="text-[10px] text-slate-600 mb-1.5">Timezone for alerts and reports</p>
            <input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="America/New_York"
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50"
            />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => updateMutation.mutate({
              mc_threshold: Number(mcThreshold),
              max_signals: Number(maxSignals),
              forward_delay: Number(forwardDelay),
              display_timezone: timezone,
            })}
            disabled={updateMutation.isPending}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 text-sm font-medium rounded-lg hover:bg-blue-500/30 transition-colors disabled:opacity-50"
          >
            {updateMutation.isPending ? 'Saving...' : 'Save Routing Settings'}
          </button>
          {updateMutation.isSuccess && <span className="text-xs text-emerald-400">Saved!</span>}
        </div>
      </div>

      {/* Runner Detection Settings */}
      <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-1">Runner Detection</h2>
        <p className="text-xs text-slate-600 mb-4">Tune how aggressively the system detects runners (tokens with strong momentum)</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1">Min Velocity (%/min)</label>
            <p className="text-[10px] text-slate-600 mb-1.5">Price change speed threshold</p>
            <input
              type="number"
              step="0.1"
              value={runnerVelocity}
              onChange={(e) => setRunnerVelocity(e.target.value)}
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <div>
            <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1">Min Vol Acceleration</label>
            <p className="text-[10px] text-slate-600 mb-1.5">5m vol vs 24h average ratio</p>
            <input
              type="number"
              step="0.1"
              value={runnerVolAccel}
              onChange={(e) => setRunnerVolAccel(e.target.value)}
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <div>
            <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1">Poll Interval (seconds)</label>
            <p className="text-[10px] text-slate-600 mb-1.5">How often to check for runners</p>
            <input
              type="number"
              value={runnerPollInterval}
              onChange={(e) => setRunnerPollInterval(e.target.value)}
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/50"
            />
          </div>
        </div>
        <div className="mt-4">
          <button
            onClick={() => updateMutation.mutate({
              runner_velocity_min: Number(runnerVelocity),
              runner_vol_accel_min: Number(runnerVolAccel),
              runner_poll_interval: Number(runnerPollInterval),
            })}
            disabled={updateMutation.isPending}
            className="px-4 py-2 bg-orange-500/20 text-orange-400 text-sm font-medium rounded-lg hover:bg-orange-500/30 transition-colors disabled:opacity-50"
          >
            Save Runner Settings
          </button>
        </div>
      </div>

      {/* Source Groups */}
      {settings?.source_groups && (
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Source Groups</h2>
          <p className="text-xs text-slate-600 mb-3">Telegram groups/channels being monitored for signals</p>
          <div className="flex flex-wrap gap-2">
            {(Array.isArray(settings.source_groups) ? settings.source_groups : []).map((g: string) => (
              <span key={g} className="px-3 py-1.5 bg-dark-600 border border-dark-400/50 rounded-lg text-sm text-slate-300">
                {g}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Block Callers */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-1">Block Callers</h2>
          <p className="text-xs text-slate-600 mb-4">Ignore signals from specific senders</p>
          <div className="flex gap-2 mb-3">
            <input
              type="number"
              placeholder="Sender ID"
              value={blockId}
              onChange={(e) => setBlockId(e.target.value)}
              className="w-32 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
            />
            <input
              placeholder="Reason (optional)"
              value={blockReason}
              onChange={(e) => setBlockReason(e.target.value)}
              className="flex-1 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
            />
            <button
              onClick={() => blockMutation.mutate()}
              disabled={!blockId || blockMutation.isPending}
              className="px-3 py-2 bg-red-500/20 text-red-400 text-sm font-medium rounded-lg hover:bg-red-500/30 transition-colors disabled:opacity-50"
            >
              Block
            </button>
          </div>
          {blocked.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {blocked.map((c: any) => (
                <div key={c.sender_id} className="flex items-center justify-between py-2 px-3 bg-dark-600 rounded-lg">
                  <div>
                    <span className="text-sm text-white">{c.sender_name || `ID: ${c.sender_id}`}</span>
                    {c.reason && <p className="text-[10px] text-slate-500">{c.reason}</p>}
                  </div>
                  <button onClick={() => unblockMutation.mutate(c.sender_id)} className="text-xs text-emerald-400 hover:text-emerald-300">
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
          <h2 className="text-sm font-semibold text-slate-300 mb-1">Contract Blacklist</h2>
          <p className="text-xs text-slate-600 mb-4">Skip known scam/rug tokens</p>
          <div className="space-y-2 mb-3">
            <input
              placeholder="Contract address"
              value={blAddr}
              onChange={(e) => setBlAddr(e.target.value)}
              className="w-full bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50 font-mono"
            />
            <div className="flex gap-2">
              <select
                value={blChain}
                onChange={(e) => setBlChain(e.target.value)}
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
                value={blReason}
                onChange={(e) => setBlReason(e.target.value)}
                className="flex-1 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
              />
              <button
                onClick={() => addBlMutation.mutate()}
                disabled={!blAddr || addBlMutation.isPending}
                className="px-3 py-2 bg-red-500/20 text-red-400 text-sm font-medium rounded-lg hover:bg-red-500/30 transition-colors disabled:opacity-50"
              >
                Add
              </button>
            </div>
          </div>
          {blacklist.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {blacklist.map((item: any) => (
                <div key={item.address} className="flex items-center justify-between py-2 px-3 bg-dark-600 rounded-lg">
                  <div>
                    <span className="text-xs text-white font-mono">{item.address.slice(0, 6)}...{item.address.slice(-4)}</span>
                    <span className="text-[10px] text-slate-500 ml-2 uppercase">{item.chain}</span>
                    {item.reason && <p className="text-[10px] text-slate-500">{item.reason}</p>}
                  </div>
                  <button onClick={() => removeBlMutation.mutate(item.address)} className="text-xs text-emerald-400 hover:text-emerald-300">
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
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-1">Override Signal Status</h2>
          <p className="text-xs text-slate-600 mb-4">Manually mark a signal as win/loss if auto-detection was wrong</p>
          <div className="flex gap-2">
            <input
              type="number"
              placeholder="Signal ID"
              value={overrideId}
              onChange={(e) => setOverrideId(e.target.value)}
              className="w-28 bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
            />
            <select
              value={overrideStatus}
              onChange={(e) => setOverrideStatus(e.target.value)}
              className="bg-dark-600 border border-dark-400/50 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/50"
            >
              <option value="win">Win</option>
              <option value="loss">Loss</option>
              <option value="active">Active</option>
            </select>
            <button
              onClick={() => overrideMutation.mutate()}
              disabled={!overrideId || overrideMutation.isPending}
              className="px-4 py-2 bg-blue-500/20 text-blue-400 text-sm font-medium rounded-lg hover:bg-blue-500/30 transition-colors disabled:opacity-50"
            >
              Override
            </button>
          </div>
          {overrideMutation.isSuccess && <p className="text-xs text-emerald-400 mt-2">Status updated.</p>}
          {overrideMutation.isError && <p className="text-xs text-red-400 mt-2">Failed to update.</p>}
        </div>

        {/* Data Export */}
        <div className="bg-dark-700 rounded-xl border border-dark-400/30 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-1">Data Export</h2>
          <p className="text-xs text-slate-600 mb-4">Download signal and caller data as JSON</p>
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
    </div>
  );
}
