import React from 'react';
import { FieldReport } from '../../types/report';
import { AlertTriangle, HelpCircle, ArrowRight, Clock } from 'lucide-react';
import { formatDateTime, truncate } from '../../utils/formatters';

interface AttentionListProps {
  reports: FieldReport[];
  onReview: (report: FieldReport) => void;
}

export function AttentionList({ reports, onReview }: AttentionListProps) {
  return (
    <div className="space-y-3">
      {reports.map((report) => (
        <div
          key={report._id}
          className="glass-card p-5"
          style={{ borderColor: 'rgba(184,122,32,0.20)' }}
        >
          <div className="flex items-start gap-4">
            <div
              className="mt-0.5 flex-shrink-0 text-accent-amber"
            >
              {report.status === 'NEEDS_REVIEW' ? (
                <AlertTriangle size={18} />
              ) : (
                <HelpCircle size={18} />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-1">
                <span
                  className="text-xs font-bold font-mono text-accent-teal"
                >
                  {report.reportId}
                </span>
                <span
                  className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                  style={{
                    background: 'rgba(184,122,32,0.09)',
                    border: '1px solid rgba(184,122,32,0.22)',
                    }}
                >
                  {report.status === 'NEEDS_REVIEW'
                    ? 'Multiple possible activities'
                    : 'Activity could not be identified'}
                </span>
              </div>
              <p className="text-sm mb-1.5 font-medium text-secondary">
                {truncate(report.text, 100)}
              </p>
              <div
                className="flex items-center gap-1 text-xs font-medium text-muted"
              >
                <Clock size={10} /> {formatDateTime(report.submittedAt)}
              </div>
            </div>
            <button
              onClick={() => onReview(report)}
              className="flex-shrink-0 glass-button-teal px-4 py-2 text-xs flex items-center gap-1.5"
            >
              REVIEW <ArrowRight size={12} />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
