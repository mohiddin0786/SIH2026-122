import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity } from '../../types/activity';
import { StatusBadge } from '../ui/StatusBadge';
import { formatDate } from '../../utils/formatters';
import { ChevronRight } from 'lucide-react';

interface ActivityTableProps {
  activities: Activity[];
}

export function ActivityTable({ activities }: ActivityTableProps) {
  const navigate = useNavigate();
  return (
    <div className="glass-table hidden md:block">
      <table className="w-full">
        <thead>
          <tr>
            <th>Activity Name</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Location</th>
            <th>Planned Finish</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {activities.map((activity) => (
            <tr
              key={activity._id}
              className="glass-table-row"
              onClick={() => navigate(`/activities/${activity._id}`)}
            >
              <td>
                <div className="font-medium text-primary">{activity.name}</div>
                {activity.priority === 'CRITICAL' && (
                  <span className="text-[10px] font-bold uppercase text-accent-amber">Critical</span>
                )}
              </td>
              <td>
                <StatusBadge status={activity.status} size="sm" />
              </td>
              <td>
                <div className="flex items-center gap-2.5">
                  <div className="glass-progress-bar w-16 h-1.5">
                    <div
                      className="glass-progress-fill h-1.5"
                      style={{ width: `${activity.progress}%` }}
                    />
                  </div>
                  <span
                    className="text-xs font-semibold text-accent-teal"
                  >
                    {activity.progress}%
                  </span>
                </div>
              </td>
              <td className="text-secondary">{activity.location}</td>
              <td className="text-secondary">{formatDate(activity.plannedFinish)}</td>
              <td>
                <ChevronRight size={15} className="text-muted" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
