'use client';
import clsx from 'clsx';

interface StatCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  color?: 'green' | 'red' | 'blue' | 'yellow' | 'purple' | 'default';
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | null;
}

const colorConfig = {
  green: {
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    glow: 'glow-green',
    gradient: 'from-emerald-500/20 to-transparent',
  },
  red: {
    text: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    glow: 'glow-red',
    gradient: 'from-red-500/20 to-transparent',
  },
  blue: {
    text: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    glow: 'glow-blue',
    gradient: 'from-blue-500/20 to-transparent',
  },
  yellow: {
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    glow: 'glow-yellow',
    gradient: 'from-amber-500/20 to-transparent',
  },
  purple: {
    text: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    glow: 'glow-purple',
    gradient: 'from-purple-500/20 to-transparent',
  },
  default: {
    text: 'text-white',
    bg: 'bg-dark-700',
    border: 'border-dark-400/50',
    glow: '',
    gradient: 'from-slate-500/10 to-transparent',
  },
};

export default function StatCard({ label, value, subtext, color = 'default', icon, trend }: StatCardProps) {
  const c = colorConfig[color];
  return (
    <div
      className={clsx(
        'relative overflow-hidden rounded-xl border p-4 transition-all duration-300 hover:scale-[1.02]',
        c.border,
        c.glow,
        'bg-dark-700'
      )}
    >
      {/* Gradient overlay */}
      <div className={clsx('absolute inset-0 bg-gradient-to-br opacity-50', c.gradient)} />

      <div className="relative">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">{label}</p>
          {icon && <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', c.bg)}>{icon}</div>}
        </div>
        <p className={clsx('text-2xl font-bold tracking-tight', c.text)}>{value}</p>
        {subtext && (
          <p className="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
            {trend === 'up' && <span className="text-emerald-400">+</span>}
            {trend === 'down' && <span className="text-red-400">-</span>}
            {subtext}
          </p>
        )}
      </div>
    </div>
  );
}
