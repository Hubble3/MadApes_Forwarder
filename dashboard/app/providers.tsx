'use client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, createContext, useContext } from 'react';
import { useWebSocket } from '@/lib/hooks';
import ToastContainer from '@/components/Toast';

// WebSocket connection status context
const WsContext = createContext(false);
export function useWsConnected() { return useContext(WsContext); }

function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const connected = useWebSocket();
  return (
    <WsContext.Provider value={connected}>
      {children}
      <ToastContainer />
    </WsContext.Provider>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5000,
        retry: 2,
      },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      <WebSocketProvider>
        {children}
      </WebSocketProvider>
    </QueryClientProvider>
  );
}
