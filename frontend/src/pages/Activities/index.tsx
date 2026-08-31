import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useProjectId } from '../../hooks/useProject';
import { activityService } from '../../services/activityService';
import { ActivityTable } from '../../components/activities/ActivityTable';
import { ActivityCard } from '../../components/activities/ActivityCard';
import { ActivityFilters } from '../../components/activities/ActivityFilters';
import { SkeletonTable } from '../../components/ui/LoadingSkeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import { ClipboardList } from 'lucide-react';

export default function Activities() {
  const projectId = useProjectId();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const { data: activities = [], isLoading, error, refetch } = useQuery({
    queryKey: ['activities', projectId],
    queryFn: () => activityService.getActivities(projectId!),
    enabled: !!projectId,
  });

  const filtered = activities.filter((a) => {
    const matchSearch =
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.location.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter ? a.status === statusFilter : true;
    return matchSearch && matchStatus;
  });

  return (
    <div className="animate-fade-in">
      <header className="mb-6">
        <span className="page-number">03 / SCHEDULE</span>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3 text-on-dark-heading">
          ACTIVITIES
          <span
            className="text-sm font-semibold px-3 py-1 rounded-full"
            style={{
              background: 'rgba(22,121,110,0.09)',
              border: '1px solid rgba(22,121,110,0.24)',
              }}
          >
            {activities.length}
          </span>
        </h1>
      </header>

      <ActivityFilters
        search={search}
        onSearchChange={setSearch}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
      />

      {isLoading ? (
        <SkeletonTable />
      ) : error ? (
        <EmptyState
          title="Unable to load activities"
          action={{ label: 'Try Again', onClick: () => refetch() }}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<ClipboardList size={40} className="text-accent-teal" />}
          title="No activities found"
          description="Try adjusting your search or filters."
        />
      ) : (
        <>
          <ActivityTable activities={filtered} />
          <div className="md:hidden space-y-3 mt-4">
            {filtered.map((a) => <ActivityCard key={a._id} activity={a} />)}
          </div>
        </>
      )}
    </div>
  );
}
