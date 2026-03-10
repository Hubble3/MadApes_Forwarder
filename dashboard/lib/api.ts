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
  runner_potential_score: number | null;
  signal_tier: string | null;
  message_quality_score: number | null;
  momentum_check_5m: string | null;
  momentum_check_15m: string | null;
  max_price_seen: number | null;
  max_price_seen_at: string | null;
  max_market_cap_seen: number | null;
  max_market_cap_seen_at: string | null;
  signal_quality: string | null;
  tp1_hit: number;
  tp2_hit: number;
  tp3_hit: number;
  tp4_hit: number;
  tp1_hit_at: string | null;
  tp2_hit_at: string | null;
  tp3_hit_at: string | null;
  tp4_hit_at: string | null;
  checked_15m: number;
  price_15m_check: number | null;
  price_change_15m: number | null;
  multiplier_15m: number | null;
  signal_quality: string | null;
}

export interface LivePrice {
  price: number | null;
  market_cap: number | null;
  price_change_5m: number | null;
  price_change_1h: number | null;
  price_change_24h: number | null;
  volume_24h: number | null;
  liquidity: number | null;
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
  win_rate?: number;
  big_win_count?: number;
  runner_rate?: number;
  big_win_rate?: number;
  best_chain?: string | null;
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
  botStatus: () => fetchApi<{ online: boolean; seconds_ago: number | null; ws_clients: number; info: any }>('/api/bot-status'),

  signals: {
    list: (params?: { status?: string; chain?: string; search?: string; tier?: string; sort?: string; order?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.status) qs.set('status', params.status);
      if (params?.chain) qs.set('chain', params.chain);
      if (params?.search) qs.set('search', params.search);
      if (params?.tier) qs.set('tier', params.tier);
      if (params?.sort) qs.set('sort', params.sort);
      if (params?.order) qs.set('order', params.order);
      if (params?.limit) qs.set('limit', String(params.limit));
      if (params?.offset) qs.set('offset', String(params.offset));
      return fetchApi<{ signals: Signal[]; total: number }>(`/api/signals/?${qs}`);
    },
    recent: (limit = 20) =>
      fetchApi<{ signals: Signal[] }>(`/api/signals/recent?limit=${limit}`),
    stats: () => fetchApi<{ total: number; active: number; wins: number; losses: number; win_rate: number }>('/api/signals/stats'),
    get: (id: number) => fetchApi<{ signal: Signal }>(`/api/signals/${id}`),
    livePrices: () =>
      fetchApi<{ prices: Record<string, LivePrice> }>('/api/signals/live-prices'),
  },

  callers: {
    list: (minSignals = 1) =>
      fetchApi<{ callers: Caller[] }>(`/api/callers/?min_signals=${minSignals}`),
    get: (senderId: number) =>
      fetchApi<{ caller: Caller }>(`/api/callers/${senderId}`),
    signals: (senderId: number, limit = 20) =>
      fetchApi<{ signals: Signal[]; total: number }>(`/api/callers/${senderId}/signals?limit=${limit}`),
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

  insights: {
    get: () => fetchApi<any>('/api/insights/'),
  },

  strategies: {
    list: () => fetchApi<{ strategies: any[] }>('/api/strategies/'),
    evaluate: (signal_id: number) =>
      fetchApi<any>('/api/strategies/evaluate', { method: 'POST', body: JSON.stringify({ signal_id }) }),
    performance: () => fetchApi<any>('/api/strategies/performance'),
  },
};
