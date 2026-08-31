import React from 'react';
import { ActivityUpdate } from '../../types/activity';
import { formatDateTime } from '../../utils/formatters';
import { CheckCircle2, RefreshCw, Circle } from 'lucide-react';

interface ActivityTimelineProps {
  updates: ActivityUpdate[];
}

export function ActivityTimeline({ updates }: ActivityTimelineProps) {
  if (updates.length === 0) {
    return (
      <div className="text-center py-8 text-sm font-medium text-secondary">
        No update history for this activity.
      </div>
    );
  }
  return (
    <div className="space-y-5 relative">
      <div className="glass-timeline-line" />
      {updates.map((update) => {
        const isComplete = update.newStatus === 'COMPLETED';
        const color = isComplete ? '#2D6A47' : '#2A7C6F';
        const Icon = isComplete ? CheckCircle2 : update.newStatus === 'IN_PROGRESS' ? RefreshCw : Circle;
        return (
          <div key={update._id} className="flex gap-4 relative pl-1">
            <div className="relative z-10 flex-shrink-0 mt-0.5" style={{ color }}>
              <Icon size={22} />
            </div>
            <div className="flex-1">
              <div className="flex justify-between items-start gap-2">
                <span className="text-sm font-semibold text-primary">
                  {update.message}
                </span>
                <span className="text-xs flex-shrink-0 text-muted">
                  {formatDateTime(update.createdAt)}
                </span>
              </div>
              {update.previousProgress !== undefined && update.newProgress !== undefined && (
                <span className="text-xs text-secondary">
                  Progress: {update.previousProgress}% → {update.newProgress}%
                </span>
              )}
              <div className="text-[10px] font-mono mt-0.5 font-medium text-secondary">
                REF: {update.reportId}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
