import React from 'react';
import { CheckCircle2, RefreshCw, Circle, AlertTriangle, HelpCircle } from 'lucide-react';
import { formatStatus } from '../../utils/formatters';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const getClass = () => {
    switch (status) {
      case 'COMPLETED':
      case 'SUCCESS':
        return 'glass-badge-green';
      case 'IN_PROGRESS':
        return 'glass-badge-teal';
      case 'NEEDS_REVIEW':
        return 'glass-badge-amber';
      case 'NOT_STARTED':
      case 'UNMATCHED':
        return 'glass-badge-gray';
      default:
        return 'glass-badge-gray';
    }
  };

  const getIcon = () => {
    const sz = size === 'sm' ? 11 : 13;
    switch (status) {
      case 'COMPLETED':
      case 'SUCCESS':
        return <CheckCircle2 size={sz} />;
      case 'IN_PROGRESS':
        return <RefreshCw size={sz} />;
      case 'NOT_STARTED':
        return <Circle size={sz} />;
      case 'NEEDS_REVIEW':
        return <AlertTriangle size={sz} />;
      case 'UNMATCHED':
        return <HelpCircle size={sz} />;
      default:
        return <Circle size={sz} />;
    }
  };

  const padding = size === 'sm' ? 'px-2 py-0.5' : 'px-3 py-1';
  const text = size === 'sm' ? 'text-[11px]' : 'text-xs';

  return (
    <span className={`${getClass()} ${padding} ${text} font-semibold`}>
      {getIcon()}
      {formatStatus(status)}
    </span>
  );
}
