'use client';
import { useEffect, useState, useCallback } from 'react';
import clsx from 'clsx';

export interface ToastMessage {
  id: string;
  type: 'signal' | 'runner' | 'info';
  title: string;
  body: string;
  timestamp: number;
}

let addToastGlobal: ((toast: Omit<ToastMessage, 'id' | 'timestamp'>) => void) | null = null;

export function showToast(toast: Omit<ToastMessage, 'id' | 'timestamp'>) {
  addToastGlobal?.(toast);
}

const typeConfig = {
  signal: { icon: 'S', bg: 'border-blue-500/30 bg-blue-500/5', accent: 'text-blue-400', dot: 'bg-blue-400' },
  runner: { icon: 'R', bg: 'border-orange-500/30 bg-orange-500/5', accent: 'text-orange-400', dot: 'bg-orange-400' },
  info: { icon: 'i', bg: 'border-slate-500/30 bg-slate-500/5', accent: 'text-slate-400', dot: 'bg-slate-400' },
};

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((toast: Omit<ToastMessage, 'id' | 'timestamp'>) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev.slice(-4), { ...toast, id, timestamp: Date.now() }]);
  }, []);

  useEffect(() => {
    addToastGlobal = addToast;
    return () => { addToastGlobal = null; };
  }, [addToast]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Auto-dismiss after 5 seconds
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setInterval(() => {
      const now = Date.now();
      setToasts((prev) => prev.filter((t) => now - t.timestamp < 5000));
    }, 1000);
    return () => clearInterval(timer);
  }, [toasts.length]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => {
        const tc = typeConfig[toast.type];
        return (
          <div
            key={toast.id}
            className={clsx(
              'pointer-events-auto rounded-xl border p-3 shadow-2xl backdrop-blur-sm',
              'animate-slide-in transition-all duration-300',
              tc.bg,
              'bg-dark-800/95'
            )}
          >
            <div className="flex items-start gap-3">
              <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold', `bg-dark-600 ${tc.accent}`)}>
                {tc.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={clsx('w-1.5 h-1.5 rounded-full', tc.dot)} />
                  <p className={clsx('text-xs font-semibold', tc.accent)}>{toast.title}</p>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5 truncate">{toast.body}</p>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-slate-600 hover:text-slate-400 transition-colors shrink-0"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
