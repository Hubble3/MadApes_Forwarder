'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: () => api.analytics.overview(),
    refetchInterval: 30000,
  });
}

export function useSignals(params?: { status?: string; limit?: number }) {
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
