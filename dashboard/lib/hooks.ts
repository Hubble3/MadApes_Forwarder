'use client';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useCallback, useState } from 'react';
import { api, Signal, LivePrice } from './api';
import { showToast } from '@/components/Toast';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

// WebSocket hook for real-time updates + toast notifications
export function useWebSocket() {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout>();
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const t = msg.type || '';
          const d = msg.data || {};

          // Toast notifications
          if (t.includes('SignalDetected') || t.includes('signal_detected')) {
            showToast({
              type: 'signal',
              title: 'New Signal',
              body: `${d.token_symbol || d.token_name || 'Token'} on ${(d.chain || '').toUpperCase()} - MC: ${d.market_cap ? `$${(d.market_cap / 1000).toFixed(0)}K` : 'N/A'}`,
            });
          }
          if (t.includes('Runner') || t.includes('runner')) {
            showToast({
              type: 'runner',
              title: 'Runner Alert',
              body: `${d.token_symbol || d.token_name || 'Token'} is running! ${d.velocity ? `+${d.velocity.toFixed(1)}%/min` : ''}`,
            });
          }

          // Invalidate relevant queries
          if (t.includes('signal') || t.includes('Signal')) {
            queryClient.invalidateQueries({ queryKey: ['signals'] });
            queryClient.invalidateQueries({ queryKey: ['overview'] });
          }
          if (t.includes('runner') || t.includes('Runner')) {
            queryClient.invalidateQueries({ queryKey: ['runners'] });
          }
          if (t.includes('performance') || t.includes('Performance')) {
            queryClient.invalidateQueries({ queryKey: ['signals'] });
            queryClient.invalidateQueries({ queryKey: ['overview'] });
            queryClient.invalidateQueries({ queryKey: ['portfolio'] });
            queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
            queryClient.invalidateQueries({ queryKey: ['callers'] });
          }
        } catch {}
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {}
  }, [queryClient]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return connected;
}

export function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: () => api.analytics.overview(),
    refetchInterval: 30000,
  });
}

export function useSignals(params?: { status?: string; chain?: string; search?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['signals', params],
    queryFn: () => api.signals.list(params),
    refetchInterval: 15000,
  });
}

export function useRecentSignals(limit = 20) {
  return useQuery({
    queryKey: ['signals', 'recent', limit],
    queryFn: () => api.signals.recent(limit),
    refetchInterval: 10000,
  });
}

export function useSignal(id: number) {
  return useQuery({
    queryKey: ['signals', id],
    queryFn: () => api.signals.get(id),
    enabled: id > 0,
  });
}

export function useLivePrices() {
  return useQuery({
    queryKey: ['live-prices'],
    queryFn: () => api.signals.livePrices(),
    refetchInterval: 30000,
  });
}

export function useSignalStats() {
  return useQuery({
    queryKey: ['signals', 'stats'],
    queryFn: () => api.signals.stats(),
    refetchInterval: 30000,
  });
}

export function useCallers(minSignals = 1) {
  return useQuery({
    queryKey: ['callers', minSignals],
    queryFn: () => api.callers.list(minSignals),
    refetchInterval: 60000,
  });
}

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ['portfolio', 'summary'],
    queryFn: () => api.portfolio.summary(),
    refetchInterval: 30000,
  });
}

export function useLeaderboard(window = 'all') {
  return useQuery({
    queryKey: ['leaderboard', window],
    queryFn: () => api.leaderboard.get(window),
    refetchInterval: 60000,
  });
}

export function useRunners(limit = 20) {
  return useQuery({
    queryKey: ['runners', limit],
    queryFn: () => api.runners.list(limit),
    refetchInterval: 15000,
  });
}

export function useRunnerStats() {
  return useQuery({
    queryKey: ['runners', 'stats'],
    queryFn: () => api.runners.stats(),
    refetchInterval: 30000,
  });
}

export function useAttribution() {
  return useQuery({
    queryKey: ['attribution'],
    queryFn: () => api.analytics.attribution(),
    refetchInterval: 60000,
  });
}

export function useDailyAnalytics(limit = 30) {
  return useQuery({
    queryKey: ['analytics', 'daily', limit],
    queryFn: () => api.analytics.daily(limit),
    refetchInterval: 60000,
  });
}
