import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { useProjectId } from '../../hooks/useProject';
import { reportService } from '../../services/reportService';
import { AttentionList } from '../../components/attention/AttentionList';
import { ReviewPanel } from '../../components/attention/ReviewPanel';
import { EmptyState } from '../../components/ui/EmptyState';
import { SkeletonCard } from '../../components/ui/LoadingSkeleton';
import { FieldReport } from '../../types/report';
import { CheckCircle2 } from 'lucide-react';
import { Toast } from '../../hooks/useToast';

export default function Attention() {
  const projectId = useProjectId();
  const queryClient = useQueryClient();
  const { toasts } = useOutletContext<{ toasts: Toast[] }>();
  const [selectedReport, setSelectedReport] = useState<FieldReport | null>(null);

  const { data: reports = [], isLoading } = useQuery({
    queryKey: ['attention', projectId],
    queryFn: () => reportService.getAttentionReports(projectId!),
    enabled: !!projectId,
  });

  const handleResolved = () => {
    setSelectedReport(null);
    queryClient.invalidateQueries({ queryKey: ['attention'] });
    queryClient.invalidateQueries({ queryKey: ['reports'] });
    queryClient.invalidateQueries({ queryKey: ['activities'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  };

  return (
    <div className="animate-fade-in max-w-4xl mx-auto">
      <header className="mb-6">
        <span className="page-number">04 / REVIEW</span>
        <h1 className="text-3xl font-bold tracking-tight text-on-dark-heading">
          NEEDS ATTENTION
        </h1>
        <p className="mt-2 text-sm font-medium text-on-dark-body">
          Reports requiring your confirmation before they can be processed into project updates.
        </p>
      </header>

      {isLoading ? (
        <div className="space-y-3"><SkeletonCard /><SkeletonCard /></div>
      ) : reports.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 size={44} className="text-accent-green" />}
          title="Everything is Up to Date"
          description="No reports require your attention right now."
        />
      ) : (
        <AttentionList reports={reports} onReview={setSelectedReport} />
      )}

      {selectedReport && (
        <ReviewPanel
          report={selectedReport}
          onClose={() => setSelectedReport(null)}
          onResolved={handleResolved}
        />
      )}
    </div>
  );
}
