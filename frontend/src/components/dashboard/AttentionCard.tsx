import React from 'react';
import { AlertTriangle, CheckCircle2, ArrowRight } from 'lucide-react';
import { FieldReport } from '../../types/report';
import { truncate } from '../../utils/formatters';

interface AttentionCardProps {
  reports: FieldReport[];
  onReviewClick: () => void;
}

export function AttentionCard({ reports, onReviewClick }: AttentionCardProps) {
  if (reports.length === 0) {
    return (
      <div className="glass-panel p-6 flex flex-col items-center justify-center text-center h-full">
        <CheckCircle2 size={36} className="mb-3 text-accent-green" />
        <div className="font-semibold mb-1 text-primary">Everything is Up to Date</div>
        <div className="text-sm font-medium text-secondary">No reports require your attention.</div>
      </div>
    );
  }

  return (
    <div
      className="glass-panel p-6 flex flex-col h-full"
      style={{
        borderColor: 'rgba(184,122,32,0.28)',
        boxShadow: '0 8px 32px rgba(30,25,15,0.10), inset 0 1px 0 rgba(255,255,255,0.70)',
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle size={16} className="text-accent-amber" />
        <span className="section-label mb-0 text-accent-amber">ATTENTION REQUIRED</span>
      </div>
      <div className="text-sm mb-4 font-medium text-secondary">
        {reports.length} report{reports.length > 1 ? 's' : ''} need{reports.length === 1 ? 's' : ''} your confirmation
      </div>
      <div className="space-y-2.5 flex-1">
        {reports.slice(0, 3).map((r) => (
          <div
            key={r._id}
            className="flex items-start gap-2 py-2"
            style={{ borderBottom: '1px solid rgba(190,180,160,0.15)' }}
          >
            <span className="mt-0.5 text-sm text-accent-amber">•</span>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-primary">{r.reportId}</div>
              <div className="text-xs truncate font-medium text-secondary">{truncate(r.text, 55)}</div>
            </div>
          </div>
        ))}
      </div>
      <button
        onClick={onReviewClick}
        className="glass-button-primary mt-4 w-full py-2.5 text-sm flex items-center justify-center gap-2"
      >
        REVIEW NOW <ArrowRight size={14} />
      </button>
    </div>
  );
}
