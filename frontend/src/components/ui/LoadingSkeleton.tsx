import React from 'react';

export function SkeletonText({ width = 'w-full', height = 'h-4' }: { width?: string; height?: string }) {
  return <div className={`skeleton-cream ${width} ${height}`} />;
}

export function SkeletonCard() {
  return (
    <div className="glass-card p-6 space-y-3">
      <SkeletonText width="w-20" height="h-3" />
      <SkeletonText width="w-40" height="h-8" />
      <SkeletonText width="w-28" height="h-3" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <tr>
      <td className="py-4 px-5"><SkeletonText width="w-44" height="h-4" /></td>
      <td className="py-4 px-5"><SkeletonText width="w-24" height="h-5" /></td>
      <td className="py-4 px-5"><SkeletonText width="w-20" height="h-3" /></td>
      <td className="py-4 px-5"><SkeletonText width="w-24" height="h-4" /></td>
      <td className="py-4 px-5"><SkeletonText width="w-20" height="h-4" /></td>
    </tr>
  );
}

export function SkeletonTable() {
  return (
    <div className="glass-table overflow-hidden">
      <table className="w-full">
        <tbody>
          {[...Array(5)].map((_, i) => <SkeletonRow key={i} />)}
        </tbody>
      </table>
    </div>
  );
}

export function SkeletonDashboard() {
  return (
    <div className="space-y-6 animate-pulse">
      <SkeletonText width="w-72" height="h-10" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
      </div>
      <SkeletonCard />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    </div>
  );
}
