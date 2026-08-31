import React from 'react';
import { Link } from 'react-router-dom';
import { RecentUpdate } from '../../types/project';
import { formatDateTime } from '../../utils/formatters';
import { CheckCircle2, RefreshCw, AlertTriangle } from 'lucide-react';

interface RecentUpdatesProps {
  updates: RecentUpdate[];
}

export function RecentUpdates({ updates }: RecentUpdatesProps) {
  return (
    <div className="glass-panel p-6 flex flex-col h-full">
      <span className="section-label">RECENT PROJECT UPDATES</span>

      {updates.length === 0 ? (
        <div
          className="flex-1 flex items-center justify-center text-sm font-medium text-secondary"
        >
          No recent updates
        </div>
      ) : (
        <div className="flex-1 relative overflow-y-auto">
          <div className="glass-timeline-line" />
          <div className="space-y-5 relative">
            {updates.map((update) => {
              const isCompleted = update.newStatus === 'COMPLETED';
              const isReview = update.newStatus === 'NEEDS_REVIEW';
              const color = isCompleted ? '#266240' : isReview ? '#7A5010' : '#16796E';
              const Icon = isCompleted ? CheckCircle2 : isReview ? AlertTriangle : RefreshCw;
              return (
                <div key={update._id} className="flex gap-4 relative pl-1">
                  <div
                    className="relative z-10 flex-shrink-0 mt-0.5"
                    style={{ color }}
                  >
                    <Icon size={22} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start gap-2">
                      <Link
                        to={`/activities/${update.activityId}`}
                        className="font-semibold text-sm truncate transition-colors text-primary"
                        onMouseOver={(e) => (e.currentTarget.style.color = '#16796E')}
                        onMouseOut={(e) => (e.currentTarget.style.color = '#1C1A18')}
                      >
                        {update.activity.name}
                      </Link>
                      <span className="text-xs flex-shrink-0 font-medium text-muted">
                        {formatDateTime(update.createdAt)}
                      </span>
                    </div>
                    <p className="text-xs mt-0.5 font-medium text-secondary">{update.message}</p>
                    <span
                      className="text-[10px] font-mono text-secondary"
                    >
                      REF: {update.reportId}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-4 pt-4 glass-divider">
        <Link to="/reports" className="glass-button-ghost text-sm mt-3 inline-block">
          View all reports →
        </Link>
      </div>
    </div>
  );
}
