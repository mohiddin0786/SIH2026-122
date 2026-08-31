import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity } from '../../types/activity';
import { StatusBadge } from '../ui/StatusBadge';
import { formatDate } from '../../utils/formatters';
import { MapPin, Calendar, ChevronRight } from 'lucide-react';

interface ActivityCardProps {
  activity: Activity;
}

export function ActivityCard({ activity }: ActivityCardProps) {
  const navigate = useNavigate();
  return (
    <div
      className="glass-card p-4 cursor-pointer"
      onClick={() => navigate(`/activities/${activity._id}`)}
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1 pr-2">
          <div className="font-semibold text-sm text-primary">{activity.name}</div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={activity.status} size="sm" />
          <ChevronRight size={13} className="text-muted" />
        </div>
      </div>
      <div className="glass-progress-bar h-1 mb-3">
        <div
          className="glass-progress-fill h-1"
          style={{ width: `${activity.progress}%` }}
        />
      </div>
      <div
        className="flex items-center justify-between text-xs text-secondary"
      >
        <span className="flex items-center gap-1"><MapPin size={10} />{activity.location}</span>
        <span className="flex items-center gap-1"><Calendar size={10} />{formatDate(activity.plannedFinish)}</span>
        <span style={{ fontWeight: 600 }}>{activity.progress}%</span>
      </div>
    </div>
  );
}
