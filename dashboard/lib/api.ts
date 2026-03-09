const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Signal types
export interface Signal {
  id: number;
  token_address: string;
  chain: string;
  token_name: string | null;
  token_symbol: string | null;
  status: string;
  original_price: number | null;
  current_price: number | null;
  original_market_cap: number | null;
  current_market_cap: number | null;
  original_liquidity: number | null;
  original_volume: number | null;
  price_change_percent: number | null;
  multiplier: number | null;
  sender_name: string;
  sender_id: number | null;
  source_group: string;
  original_timestamp: string;
  runner_alerted: number;
  destination_type: string | null;
  confidence_score: number | null;
  tags: string | null;
  original_dexscreener_link: string | null;
  signal_link: string | null;
}

export interface Caller {
  sender_id: number;
  sender_name: string;
  total_signals: number;
  win_count: number;
  loss_count: number;
  runner_count: number;
  avg_return: number;
  best_return: number;
  worst_return: number;
  composite_score: number;
  last_signal_at: string | null;
}

export interface PortfolioSummary {
  total_open: number;
  total_closed: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  total_pnl: number;
  total_invested_open: number;
  win_rate: number;
  wins: number;
  losses: number;
  best_pnl_pct: number;
  worst_pnl_pct: number;
  max_drawdown_pct: number;
}

export interface Overview {
  total_signals: number;
  active: number;
  wins: number;
  losses: number;
  runners: number;
  win_rate: number;
  today_signals: number;
  checked_signals?: number;
  chains: Record<string, number>;
}

export interface LeaderboardEntry {
  rank: number;
  sender_id: number;
  sender_name: string;
  total_signals: number;
  wins: number;
  losses: number;
  runners: number;
  win_rate: number;
  avg_return: number;
  best_return: number;
  worst_return: number;
}

// API functions
export const api = {
  health: () => fetchApi<{ status: string }>('/api/health'),

  signals: {
    list: (params?: { status?: string; chain?: string; search?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.status) qs.set('status', params.status);
      if (params?.chain) qs.set('chain', params.chain);
      if (params?.search) qs.set('search', params.search);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      return fetchApi<{ signals: Signal[]; total: number }>(`/api/signals/?${qs}`);
    },
    recent: (limit = 20) =>
      fetchApi<{ signals: Signal[] }>(`/api/signals/recent?limit=${limit}`),
    stats: () => fetchApi<{ total: number; active: number; wins: number; losses: number; win_rate: number }>('/api/signals/stats'),
    get: (id: number) => fetchApi<{ signal: Signal }>(`/api/signals/${id}`),
  },

  callers: {
    list: (minSignals = 1) =>
      fetchApi<{ callers: Caller[] }>(`/api/callers/?min_signals=${minSignals}`),
    get: (senderId: number) =>
      fetchApi<{ caller: Caller }>(`/api/callers/${senderId}`),
  },

  portfolio: {
    summary: () => fetchApi<PortfolioSummary>('/api/portfolio/summary'),
    open: () => fetchApi<{ positions: any[] }>('/api/portfolio/open'),
    closed: (limit = 50) =>
      fetchApi<{ positions: any[] }>(`/api/portfolio/closed?limit=${limit}`),
    byChain: () => fetchApi<Record<string, any>>('/api/portfolio/by-chain'),
  },

  analytics: {
    overview: () => fetchApi<Overview>('/api/analytics/overview'),
    attribution: () => fetchApi<any>('/api/analytics/attribution'),
    daily: (limit = 30) =>
      fetchApi<{ days: any[] }>(`/api/analytics/daily?limit=${limit}`),
  },

  leaderboard: {
    get: (window = 'all', limit = 20) =>
      fetchApi<{ window: string; leaderboard: LeaderboardEntry[] }>(
        `/api/leaderboard/?window=${window}&limit=${limit}`
      ),
  },

  runners: {
    list: (limit = 20) =>
      fetchApi<{ runners: Signal[] }>(`/api/runners/?limit=${limit}`),
    stats: () => fetchApi<any>('/api/runners/stats'),
  },

  settings: {
    get: () => fetchApi<any>('/api/settings/'),
    update: (data: Record<string, any>) =>
      fetchApi<any>('/api/settings/', { method: 'POST', body: JSON.stringify(data) }),
    health: () => fetchApi<any>('/api/settings/health'),
    exportSignals: () => fetchApi<any>('/api/settings/export/signals'),
    exportCallers: () => fetchApi<any>('/api/settings/export/callers'),
    deleteSignal: (signal_id: number) =>
      fetchApi<any>(`/api/settings/signals/${signal_id}`, { method: 'DELETE' }),
  },

  strategies: {
    list: () => fetchApi<{ strategies: any[] }>('/api/strategies/'),
    evaluate: (signal_id: number) =>
      fetchApi<any>('/api/strategies/evaluate', { method: 'POST', body: JSON.stringify({ signal_id }) }),
    performance: () => fetchApi<any>('/api/strategies/performance'),
  },
};
