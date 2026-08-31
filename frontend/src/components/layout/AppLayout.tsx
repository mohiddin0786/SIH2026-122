import React from 'react';
import { Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useProjectId } from '../../hooks/useProject';
import { reportService } from '../../services/reportService';
import { ToastContainer } from '../ui/Toast';
import { useToast } from '../../hooks/useToast';
import { useDarkMode } from '../../hooks/useDarkMode';

export function AppLayout() {
  const projectId = useProjectId();
  const { toasts, removeToast } = useToast();
  const { isDark, toggle } = useDarkMode();

  const { data: attentionReports } = useQuery({
    queryKey: ['attention', projectId],
    queryFn: () => reportService.getAttentionReports(projectId!),
    enabled: !!projectId,
    refetchInterval: 30000,
  });

  const attentionCount = attentionReports?.length || 0;

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ fontFamily: "'Inter', system-ui, sans-serif" }}
    >
      {/* Fixed construction site background */}
      <div className="bg-construction" />
      <div className="bg-overlay" />

      {/* Glass sidebar */}
      <Sidebar attentionCount={attentionCount} />

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <Header attentionCount={attentionCount} isDark={isDark} onToggleDark={toggle} />
        <main className="flex-1 overflow-y-auto overflow-x-hidden pb-20 md:pb-8">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8 py-6 md:py-8">
            <Outlet context={{ toasts }} />
          </div>
        </main>
      </div>

      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
}
