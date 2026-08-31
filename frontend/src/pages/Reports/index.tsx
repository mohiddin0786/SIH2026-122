import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useProjectId } from '../../hooks/useProject';
import { reportService } from '../../services/reportService';
import { ReportForm } from '../../components/reports/ReportForm';
import { ReportResult } from '../../components/reports/ReportResult';
import { ReportCard } from '../../components/reports/ReportCard';
import { BatchReportForm } from '../../components/reports/BatchReportForm';
import { BatchReportResult } from '../../components/reports/BatchReportResult';
import { SubmitReportResponse, BatchSubmitResponse } from '../../types/report';
import { SkeletonCard } from '../../components/ui/LoadingSkeleton';

type EntryMode = 'single' | 'batch';

export default function Reports() {
  const projectId = useProjectId();
  const queryClient = useQueryClient();
  const [entryMode, setEntryMode] = useState<EntryMode>('single');
  const [submissionResult, setSubmissionResult] = useState<SubmitReportResponse | null>(null);
  const [batchResult, setBatchResult] = useState<BatchSubmitResponse | null>(null);

  const { data: reports = [], isLoading } = useQuery({
    queryKey: ['reports', projectId],
    queryFn: () => reportService.getReports(projectId!),
    enabled: !!projectId,
    refetchInterval: 60000,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['reports'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    queryClient.invalidateQueries({ queryKey: ['attention'] });
    queryClient.invalidateQueries({ queryKey: ['activities'] });
  };

  const handleSuccess = (result: SubmitReportResponse) => {
    setSubmissionResult(result);
    invalidateAll();
  };

  const handleBatchSuccess = (result: BatchSubmitResponse) => {
    setBatchResult(result);
    invalidateAll();
  };

  const handleConfirm = async (activityId: string) => {
    if (!submissionResult) return;
    try {
      const newResult = await reportService.confirmActivity(submissionResult.reportId, activityId);
      setSubmissionResult(newResult);
      invalidateAll();
    } catch (err) { console.error(err); }
  };

  const handleReject = async () => {
    if (!submissionResult) return;
    try {
      await reportService.rejectReport(submissionResult.reportId);
      setSubmissionResult(null);
      queryClient.invalidateQueries({ queryKey: ['reports'] });
      queryClient.invalidateQueries({ queryKey: ['attention'] });
    } catch (err) { console.error(err); }
  };

  const handleModeChange = (mode: EntryMode) => {
    setEntryMode(mode);
    setSubmissionResult(null);
    setBatchResult(null);
  };

  const activeResult = entryMode === 'single' ? submissionResult : batchResult;

  return (
    <div className="animate-fade-in max-w-5xl mx-auto">
      <header className="mb-6">
        <span className="page-number">02 / DATA ENTRY</span>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3 text-on-dark-heading">
          FIELD REPORTS
          <span
            className="text-sm font-semibold px-3 py-1 rounded-full"
            style={{
              background: 'rgba(22,121,110,0.09)',
              border: '1px solid rgba(22,121,110,0.24)',
              }}
          >
            {reports.length}
          </span>
        </h1>
      </header>

      <div className="flex gap-2 mb-4">
        <button
          onClick={() => handleModeChange('single')}
          className={entryMode === 'single' ? 'glass-button-teal' : 'glass-button-ghost'}
          style={{ fontSize: '11px', padding: '8px 14px' }}
        >
          SINGLE REPORT
        </button>
        <button
          onClick={() => handleModeChange('batch')}
          className={entryMode === 'batch' ? 'glass-button-teal' : 'glass-button-ghost'}
          style={{ fontSize: '11px', padding: '8px 14px' }}
        >
          BULK UPLOAD
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5" style={{ minHeight: '460px' }}>
          {entryMode === 'single' ? (
            submissionResult ? (
              <ReportResult
                result={submissionResult}
                onConfirm={handleConfirm}
                onReject={handleReject}
                onReset={() => setSubmissionResult(null)}
              />
            ) : (
              <ReportForm projectId={projectId!} onSuccess={handleSuccess} />
            )
          ) : batchResult ? (
            <BatchReportResult result={batchResult} onReset={() => setBatchResult(null)} />
          ) : (
            <BatchReportForm projectId={projectId!} onSuccess={handleBatchSuccess} />
          )}
        </div>
        <div className="lg:col-span-7">
          <span className="section-label">RECENT SUBMISSIONS</span>
          <div className="space-y-3 max-h-[580px] overflow-y-auto pr-1">
            {isLoading ? (
              <><SkeletonCard /><SkeletonCard /><SkeletonCard /></>
            ) : reports.length > 0 ? (
              reports.map((r) => <ReportCard key={r._id} report={r} />)
            ) : (
              <div
                className="glass-card p-8 text-center text-sm text-primary"
              >
                No reports submitted yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
