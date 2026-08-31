import React from 'react';

interface SummaryCardProps {
  label: string;
  value: number | string;
  icon?: React.ReactNode;
  accent?: 'teal' | 'gold' | 'amber' | 'green';
  trend?: string;
}

export function SummaryCard({ label, value, icon, accent = 'teal', trend }: SummaryCardProps) {
  const colorKey = accent === 'gold' ? 'amber' : accent;
  
  return (
    <div className="glass-card p-5 relative overflow-hidden">
      <div className="flex items-start justify-between mb-4">
        <span className="section-label mb-0">{label}</span>
        {icon && (
          <div className={`p-2 rounded-lg flex-shrink-0 text-accent-${colorKey} bg-accent-${colorKey}-bg border border-accent-${colorKey}-border`}>
            {icon}
          </div>
        )}
      </div>
      <div
        className="text-4xl font-bold tracking-tight text-primary"
        style={{ fontVariantNumeric: 'tabular-nums' }}
      >
        {value}
      </div>
      {trend && (
        <div className="text-xs font-medium mt-2 text-muted">{trend}</div>
      )}
    </div>
  );
}
