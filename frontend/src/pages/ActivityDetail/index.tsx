import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { activityService } from '../../services/activityService';
import { ActivityTimeline } from '../../components/activities/ActivityTimeline';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { SkeletonDashboard } from '../../components/ui/LoadingSkeleton';
import { formatDate } from '../../utils/formatters';
import { ArrowLeft, Calendar, MapPin, User, Flag } from 'lucide-react';

export default function ActivityDetail() {
  const { activityId } = useParams<{ activityId: string }>();

  const { data: activity, isLoading: isActivityLoading } = useQuery({
    queryKey: ['activity', activityId],
    queryFn: () => activityService.getActivity(activityId!),
    enabled: !!activityId,
  });

  const { data: updates = [], isLoading: isUpdatesLoading } = useQuery({
    queryKey: ['activity-updates', activityId],
    queryFn: () => activityService.getActivityUpdates(activityId!),
    enabled: !!activityId,
  });

  if (isActivityLoading) return <SkeletonDashboard />;
  if (!activity) return (
    <div className="text-center py-20 text-sm text-muted">Activity not found</div>
  );

  return (
    <div className="animate-fade-in max-w-4xl mx-auto space-y-6 pb-12">
      <Link
        to="/activities"
        className="inline-flex items-center gap-2 text-sm font-medium transition-colors text-accent-teal"
        onMouseOver={(e) => (e.currentTarget.style.color = '#0F5E54')}
        onMouseOut={(e) => (e.currentTarget.style.color = '#16796E')}
      >
        <ArrowLeft size={15} /> Back to Activities
      </Link>

      {/* Hero */}
      <div className="glass-panel p-6 md:p-8">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <StatusBadge status={activity.status} size="md" />
          {activity.priority === 'CRITICAL' && (
            <span
              className="text-xs font-bold uppercase px-3 py-1 rounded-full"
              style={{
                background: 'rgba(160,56,40,0.08)',
                border: '1px solid rgba(160,56,40,0.22)',
                }}
            >
              Critical Priority
            </span>
          )}
        </div>
        <h1
          className="text-3xl md:text-4xl font-bold tracking-tight mb-3 text-primary"
        >
          {activity.name}
        </h1>
        <p className="mb-6 font-medium text-secondary">{activity.description}</p>
        <div className="flex items-center gap-4">
          <div className="text-sm font-semibold w-20 text-secondary">Progress</div>
          <div className="flex-1 max-w-sm">
            <div className="glass-progress-bar h-1.5">
              <div
                className="glass-progress-fill h-1.5"
                style={{ width: `${activity.progress}%`, transition: 'width 1s ease' }}
              />
            </div>
          </div>
          <div className="text-sm font-bold text-accent-teal">{activity.progress}%</div>
        </div>
      </div>

      {/* Schedule + Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="glass-card p-6">
          <span className="section-label flex items-center gap-2"><Calendar size={12} />SCHEDULE</span>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'Planned Start', val: formatDate(activity.plannedStart) },
              { label: 'Planned Finish', val: formatDate(activity.plannedFinish) },
              { label: 'Actual Start', val: formatDate(activity.actualStart || '') || '—' },
              { label: 'Actual Finish', val: formatDate(activity.actualFinish || '') || '—' },
            ].map((item) => (
              <div key={item.label}>
                <div className="text-[10px] uppercase tracking-wide mb-1 font-semibold text-secondary">{item.label}</div>
                <div className="font-semibold text-sm text-primary">{item.val}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="glass-card p-6">
          <span className="section-label">DETAILS</span>
          <div className="space-y-3.5">
            {[
              { icon: <MapPin size={13} />, label: 'Location', val: activity.location || 'Not specified' },
              { icon: <User size={13} />, label: 'Assigned To', val: activity.assignedTo || 'Unassigned' },
              { icon: <Flag size={13} />, label: 'Priority', val: activity.priority },
            ].map((item) => (
              <div key={item.label} className="flex items-start gap-3">
                <span style={{ marginTop: '2px' }}>{item.icon}</span>
                <div>
                  <div className="text-[10px] uppercase tracking-wide font-semibold text-secondary">{item.label}</div>
                  <div className="text-sm font-medium text-primary">{item.val}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* History */}
      <div className="glass-panel p-6">
        <span className="section-label">ACTIVITY HISTORY</span>
        {isUpdatesLoading ? (
          <div className="py-8 text-center text-sm font-medium text-secondary">Loading history...</div>
        ) : (
          <ActivityTimeline updates={updates} />
        )}
      </div>
    </div>
  );
}
