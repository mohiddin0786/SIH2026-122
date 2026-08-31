import React from 'react';
import { FieldReport } from '../../types/report';
import { StatusBadge } from '../ui/StatusBadge';
import { formatDateTime, truncate } from '../../utils/formatters';

interface ReportCardProps {
  report: FieldReport;
}

export function ReportCard({ report }: ReportCardProps) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-start justify-between mb-2">
        <span
          className="text-xs font-bold font-mono text-accent-teal"
        >
          {report.reportId}
        </span>
        <StatusBadge status={report.status} size="sm" />
      </div>
      <p className="text-sm leading-relaxed text-secondary">
        {truncate(report.text, 120)}
      </p>
      {report.matchedActivityId && (
        <div className="mt-1.5 text-xs text-accent-green">
          ✓ Activity linked
        </div>
      )}
      <div className="mt-2 text-xs font-medium text-muted">
        {formatDateTime(report.submittedAt)}
      </div>
    </div>
  );
}
