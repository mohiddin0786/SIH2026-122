import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useProjectId } from '../../hooks/useProject';
import { dashboardService } from '../../services/dashboardService';
import { SummaryCard } from '../../components/dashboard/SummaryCard';
import { ProjectProgress } from '../../components/dashboard/ProjectProgress';
import { RecentUpdates } from '../../components/dashboard/RecentUpdates';
import { AttentionCard } from '../../components/dashboard/AttentionCard';
import { SkeletonDashboard } from '../../components/ui/LoadingSkeleton';
import { EmptyState } from '../../components/ui/EmptyState';
import { reportService } from '../../services/reportService';
import { Activity, CheckCircle, RefreshCw, AlertTriangle } from 'lucide-react';

export default function Dashboard() {
  const projectId = useProjectId();
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard', projectId],
    queryFn: () => dashboardService.getDashboard(projectId!),
    enabled: !!projectId,
    refetchInterval: 30000,
  });

  const { data: attentionReports = [] } = useQuery({
    queryKey: ['attention', projectId],
    queryFn: () => reportService.getAttentionReports(projectId!),
    enabled: !!projectId,
    refetchInterval: 30000,
  });

  if (isLoading) return <SkeletonDashboard />;
  if (error || !data) {
    return (
      <EmptyState
        title="Unable to load dashboard"
        description="Could not fetch project data. Please try again."
        action={{ label: 'Try Again', onClick: () => refetch() }}
      />
    );
  }

  return (
    <div className="space-y-6 md:space-y-8 animate-fade-in">
      <header className="mb-6">
        <span className="page-number">01 / PROJECT OVERVIEW</span>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ color: 'inherit' }}>
          {data.project.name}
        </h1>
        <p className="mt-2 text-sm max-w-3xl leading-relaxed opacity-75">
          {data.project.description}
        </p>
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-5">
        <SummaryCard label="Total Activities"  value={data.totalActivities}  icon={<Activity size={17} />}     accent="teal"  trend="All activities" />
        <SummaryCard label="Completed Today"   value={data.completedToday}   icon={<CheckCircle size={17} />}  accent="green" trend={data.completedToday === 0 ? 'No activities completed' : 'Activities completed'} />
        <SummaryCard label="In Progress"       value={data.inProgress}       icon={<RefreshCw size={17} />}    accent="teal"  trend="Ongoing activities" />
        <SummaryCard
          label="Need Attention"
          value={data.needsAttention}
          icon={<AlertTriangle size={17} />}
          accent="amber"
          trend={data.needsAttention > 0 ? 'Requires review' : 'All clear'}
        />
      </div>

      <ProjectProgress progress={data.progress} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" style={{ minHeight: '360px' }}>
        <RecentUpdates updates={data.recentUpdates || []} />
        <AttentionCard
          reports={attentionReports}
          onReviewClick={() => navigate('/attention')}
        />
      </div>
    </div>
  );
}
