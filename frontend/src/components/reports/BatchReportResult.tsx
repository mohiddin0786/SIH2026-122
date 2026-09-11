import React from 'react';
import { BatchSubmitResponse } from '../../types/report';
import { CheckCircle2, AlertTriangle, HelpCircle, ShieldAlert, XCircle, RotateCcw } from 'lucide-react';
import { truncate } from '../../utils/formatters';

interface BatchReportResultProps {
  result: BatchSubmitResponse;
  onReset: () => void;
}

const STATUS_META: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  SUCCESS: { icon: <CheckCircle2 size={15} />, color: '#266240', label: 'Matched' },
  NEEDS_REVIEW: { icon: <AlertTriangle size={15} />, color: '#B87A20', label: 'Needs Review' },
  SCHEDULE_VIOLATION: { icon: <ShieldAlert size={15} />, color: '#A03828', label: 'Schedule Violation' },
  UNMATCHED: { icon: <HelpCircle size={15} />, color: '#5C5750', label: 'Unmatched' },
  ERROR: { icon: <XCircle size={15} />, color: '#A03828', label: 'Error' },
};

export function BatchReportResult({ result, onReset }: BatchReportResultProps) {
  const { summary, results, batchOrdering } = result;

  return (
    <div className="glass-panel p-6 flex flex-col animate-fade-in h-full">
      <span className="section-label">BATCH RESULTS</span>

      <div className="grid grid-cols-5 gap-2 my-4">
        <SummaryStat label="Matched" value={summary.success} color="#266240" />
        <SummaryStat label="Review" value={summary.needsReview} color="#B87A20" />
        <SummaryStat label="Violations" value={summary.scheduleViolation} color="#A03828" />
        <SummaryStat label="Unmatched" value={summary.unmatched} color="#5C5750" />
        <SummaryStat label="Errors" value={summary.errors} color="#A03828" />
      </div>

      <div className="flex-1 overflow-y-auto space-y-2">
        {results.map((r, idx) => {
          const meta = STATUS_META[r.status] || STATUS_META.ERROR;
          return (
            <div key={idx} className="glass-card p-3 flex items-start gap-3">
              <div style={{ color: meta.color }} className="mt-0.5">{meta.icon}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold" style={{ color: meta.color }}>
                    {meta.label}
                  </span>
                  {r.reportId && (
                    <span className="text-xs font-mono text-muted">{r.reportId}</span>
                  )}
                </div>
                {r.status === 'SUCCESS' && r.activity && (
                  <div className="text-sm font-medium text-primary mt-0.5">{r.activity.name}</div>
                )}
                {r.status === 'NEEDS_REVIEW' && r.candidates && (
                  <div className="text-xs text-secondary mt-0.5">
                    {r.candidates.length} candidate{r.candidates.length !== 1 ? 's' : ''} found
                  </div>
                )}
                {r.status === 'SCHEDULE_VIOLATION' && r.violation && (
                  <div className="text-xs text-secondary mt-0.5">
                    Blocked by predecessor {r.violation.predecessorId}
                  </div>
                )}
                {r.status === 'ERROR' && r.error && (
                  <div className="text-xs text-secondary mt-0.5">{truncate(r.error, 100)}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {batchOrdering.length > 0 && (
        <div className="mt-4 text-xs text-secondary">
          <div className="section-label mb-2">DEPENDENCY ORDER</div>
          {batchOrdering.map((group, index) => (
            <div key={index} className="glass-card px-3 py-2 mb-1">
              {group.join(' -> ')}
            </div>
          ))}
        </div>
      )}

      <button onClick={onReset} className="glass-button-ghost text-xs flex items-center gap-1.5 mt-4">
        <RotateCcw size={11} /> Submit another batch
      </button>
    </div>
  );
}

function SummaryStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="glass-card p-2.5 text-center">
      <div className="text-lg font-bold" style={{ color }}>{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
    </div>
  );
}
