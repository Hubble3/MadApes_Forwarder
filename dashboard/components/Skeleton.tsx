import clsx from 'clsx';

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={clsx('rounded-xl bg-dark-700 border border-dark-400/30 p-4', className)}>
      <div className="h-3 w-24 rounded animate-shimmer mb-3" />
      <div className="h-7 w-16 rounded animate-shimmer" />
    </div>
  );
}

export function SkeletonSignal() {
  return (
    <div className="rounded-xl bg-dark-700 border border-dark-400/30 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <div className="h-5 w-16 rounded animate-shimmer" />
        <div className="h-4 w-20 rounded animate-shimmer" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="h-4 rounded animate-shimmer" />
        <div className="h-4 rounded animate-shimmer" />
        <div className="h-4 rounded animate-shimmer" />
      </div>
      <div className="h-3 w-32 rounded animate-shimmer" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="rounded-xl bg-dark-700 border border-dark-400/30 p-4 flex items-center gap-4">
      <div className="w-10 h-10 rounded-xl animate-shimmer shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-4 w-32 rounded animate-shimmer" />
        <div className="h-3 w-48 rounded animate-shimmer" />
      </div>
      <div className="h-5 w-16 rounded animate-shimmer" />
    </div>
  );
}
