import os

files = {
    "src/services/dashboardService.ts": """import { api } from './api';
import { DashboardData } from '../types/project';

export const dashboardService = {
  getDashboard: (projectId: string) =>
    api.get<DashboardData>(`/projects/${projectId}/dashboard`),
};""",
    "src/services/activityService.ts": """import { api } from './api';
import { Activity, ActivityUpdate } from '../types/activity';

export const activityService = {
  getActivities: (projectId: string) =>
    api.get<Activity[]>(`/projects/${projectId}/activities`),
  getActivity: (activityId: string) =>
    api.get<Activity>(`/activities/${activityId}`),
  getActivityUpdates: (activityId: string) =>
    api.get<ActivityUpdate[]>(`/activities/${activityId}/updates`),
};""",
    "src/services/reportService.ts": """import { api } from './api';
import { FieldReport, SubmitReportResponse } from '../types/report';

export const reportService = {
  getReports: (projectId: string) =>
    api.get<FieldReport[]>(`/projects/${projectId}/reports`),
  getReport: (reportId: string) =>
    api.get<FieldReport>(`/reports/${reportId}`),
  submitReport: (projectId: string, text: string) =>
    api.post<SubmitReportResponse>(`/projects/${projectId}/reports`, { text }),
  getAttentionReports: (projectId: string) =>
    api.get<FieldReport[]>(`/projects/${projectId}/attention`),
  confirmActivity: (reportId: string, activityId: string) =>
    api.post<SubmitReportResponse>(`/reports/${reportId}/confirm`, { activityId }),
  rejectReport: (reportId: string, note?: string) =>
    api.post<{ status: string; reportId: string }>(`/reports/${reportId}/reject`, { note }),
};""",
    "src/utils/formatters.ts": """export function formatDate(dateString: string): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatDateTime(dateString: string): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  if (isToday) {
    return 'Today · ' + date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return 'Yesterday · ' + date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
  return formatDate(dateString);
}

export function formatRelative(dateString: string): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateString);
}

export function formatStatus(status: string): string {
  const map: Record<string, string> = {
    NOT_STARTED: 'Not Started',
    IN_PROGRESS: 'In Progress',
    COMPLETED: 'Completed',
    NEEDS_REVIEW: 'Needs Review',
    SUCCESS: 'Processed',
    UNMATCHED: 'Unmatched',
    PROCESSING: 'Processing',
  };
  return map[status] ?? status;
}

export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}""",
    "src/hooks/useProject.ts": """import { useQuery } from '@tanstack/react-query';
import { projectService } from '../services/projectService';

export function useProjectId() {
  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectService.getProjects(),
    staleTime: 1000 * 60 * 10,
  });
  return projects?.[0]?._id ?? null;
}""",
    "src/hooks/useToast.ts": """import { useState, useCallback } from 'react';

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, addToast, removeToast };
}""",
    "src/app/providers.tsx": """import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { Router } from './router';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Router />
      </BrowserRouter>
    </QueryClientProvider>
  );
}""",
    "src/app/router.tsx": """import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import Dashboard from '../pages/Dashboard';
import Reports from '../pages/Reports';
import Activities from '../pages/Activities';
import ActivityDetail from '../pages/ActivityDetail';
import Attention from '../pages/Attention';

export function Router() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="reports" element={<Reports />} />
        <Route path="activities" element={<Activities />} />
        <Route path="activities/:activityId" element={<ActivityDetail />} />
        <Route path="attention" element={<Attention />} />
      </Route>
    </Routes>
  );
}""",
    "src/components/ui/StatusBadge.tsx": """import React from 'react';
import { Check, CheckCircle2, RefreshCw, Circle, AlertTriangle, HelpCircle } from 'lucide-react';
import { formatStatus } from '../../utils/formatters';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const getBadgeStyles = () => {
    switch (status) {
      case 'COMPLETED':
      case 'SUCCESS':
        return 'badge-completed';
      case 'IN_PROGRESS':
        return 'badge-in-progress';
      case 'NOT_STARTED':
        return 'badge-not-started';
      case 'NEEDS_REVIEW':
        return 'badge-needs-review';
      case 'UNMATCHED':
        return 'badge-not-started';
      default:
        return 'badge-not-started';
    }
  };

  const getIcon = () => {
    const iconProps = { size: size === 'sm' ? 14 : 16, className: 'mr-1.5' };
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle2 {...iconProps} />;
      case 'SUCCESS':
        return <Check {...iconProps} />;
      case 'IN_PROGRESS':
        return <RefreshCw {...iconProps} />;
      case 'NOT_STARTED':
        return <Circle {...iconProps} />;
      case 'NEEDS_REVIEW':
        return <AlertTriangle {...iconProps} />;
      case 'UNMATCHED':
        return <HelpCircle {...iconProps} />;
      default:
        return <Circle {...iconProps} />;
    }
  };

  const sizeStyles = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span className={`inline-flex items-center font-medium rounded-full ${getBadgeStyles()} ${sizeStyles}`}>
      {getIcon()}
      {formatStatus(status)}
    </span>
  );
}""",
    "src/components/ui/LoadingSkeleton.tsx": """import React from 'react';

export const SkeletonCard = () => (
  <div className="card-padded animate-pulse flex flex-col gap-4">
    <div className="h-4 bg-ivory-300 rounded w-1/3"></div>
    <div className="h-10 bg-ivory-300 rounded w-1/2"></div>
    <div className="h-4 bg-ivory-300 rounded w-2/3"></div>
  </div>
);

export const SkeletonRow = () => (
  <div className="animate-pulse flex items-center justify-between py-4 border-b border-ivory-300">
    <div className="flex flex-col gap-2 w-1/3">
      <div className="h-4 bg-ivory-300 rounded w-3/4"></div>
      <div className="h-3 bg-ivory-300 rounded w-1/2"></div>
    </div>
    <div className="h-6 bg-ivory-300 rounded-full w-24"></div>
  </div>
);

export const SkeletonText = ({ className = 'w-1/2' }: { className?: string }) => (
  <div className={`animate-pulse h-4 bg-ivory-300 rounded ${className}`}></div>
);

export const SkeletonDashboard = () => (
  <div className="space-y-6">
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
    </div>
    <div className="h-32 bg-white border border-[#E8E4DC] rounded-md animate-pulse"></div>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="h-64 bg-white border border-[#E8E4DC] rounded-md animate-pulse"></div>
      <div className="h-64 bg-white border border-[#E8E4DC] rounded-md animate-pulse"></div>
    </div>
  </div>
);

export const SkeletonTable = () => (
  <div className="card">
    <div className="divide-y divide-ivory-300 px-6">
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
    </div>
  </div>
);""",
    "src/components/ui/EmptyState.tsx": """import React, { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center card bg-white">
      {icon && <div className="text-teal-300 mb-4">{icon}</div>}
      <h3 className="text-lg font-medium text-charcoal-800 mb-2">{title}</h3>
      {description && <p className="text-charcoal-500 mb-6 max-w-md">{description}</p>}
      {action && (
        <button onClick={action.onClick} className="btn-primary">
          {action.label}
        </button>
      )}
    </div>
  );
}""",
    "src/components/ui/Toast.tsx": """import React from 'react';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';
import { Toast as ToastType } from '../../hooks/useToast';

interface ToastProps {
  toast: ToastType;
  onRemove: (id: string) => void;
}

export function Toast({ toast, onRemove }: ToastProps) {
  const getIcon = () => {
    switch (toast.type) {
      case 'success':
        return <CheckCircle className="text-green-600" size={20} />;
      case 'error':
        return <XCircle className="text-red-600" size={20} />;
      case 'info':
        return <Info className="text-teal-600" size={20} />;
    }
  };

  const getBg = () => {
    switch (toast.type) {
      case 'success':
        return 'bg-green-50 border-green-200';
      case 'error':
        return 'bg-red-50 border-red-200';
      case 'info':
        return 'bg-teal-50 border-teal-200';
    }
  };

  return (
    <div className={`flex items-start p-4 rounded-md border shadow-card animate-fade-in ${getBg()}`}>
      <div className="flex-shrink-0 mr-3">{getIcon()}</div>
      <div className="flex-1 text-sm font-medium text-charcoal-800 mr-4">{toast.message}</div>
      <button onClick={() => onRemove(toast.id)} className="text-charcoal-400 hover:text-charcoal-600">
        <X size={16} />
      </button>
    </div>
  );
}

export function ToastContainer({ toasts, onRemove }: { toasts: ToastType[]; onRemove: (id: string) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>
  );
}""",
    "src/components/layout/Sidebar.tsx": """import React from 'react';
import { NavLink } from 'react-router-dom';
import { Home, FileText, Calendar, AlertTriangle } from 'lucide-react';

interface SidebarProps {
  attentionCount: number;
}

export function Sidebar({ attentionCount }: SidebarProps) {
  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: Home },
    { to: '/reports', label: 'Reports', icon: FileText },
    { to: '/activities', label: 'Activities', icon: Calendar },
    { to: '/attention', label: 'Needs Attention', icon: AlertTriangle, badge: attentionCount },
  ];

  return (
    <aside className="hidden md:flex flex-col w-[220px] bg-ivory-50 border-r border-[#E8E4DC] h-screen sticky top-0">
      <div className="p-6">
        <h1 className="font-editorial text-xl font-medium tracking-tight text-charcoal-900 leading-tight">
          PROJECT EXECUTION<br />
          <span className="text-teal-600 text-lg">UPDATE SYSTEM</span>
        </h1>
      </div>
      <nav className="flex-1 px-4 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-teal-50 text-teal-700 border-l-4 border-teal-500'
                  : 'text-charcoal-600 hover:bg-ivory-200 hover:text-charcoal-900 border-l-4 border-transparent'
              }`
            }
          >
            <item.icon className="mr-3 h-5 w-5" />
            <span className="flex-1">{item.label}</span>
            {item.badge !== undefined && item.badge > 0 && (
              <span className="ml-auto bg-amber-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}""",
    "src/components/layout/Header.tsx": """import React from 'react';
import { NavLink } from 'react-router-dom';
import { Home, FileText, Calendar, AlertTriangle, Menu } from 'lucide-react';

interface HeaderProps {
  attentionCount: number;
}

export function Header({ attentionCount }: HeaderProps) {
  const dateStr = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' });

  return (
    <>
      <header className="md:hidden bg-white border-b border-[#E8E4DC] p-4 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center">
          <button className="text-charcoal-600 mr-4">
            <Menu className="h-6 w-6" />
          </button>
          <h1 className="font-editorial text-lg font-medium text-charcoal-900 truncate">
            PE Update System
          </h1>
        </div>
        <div className="h-8 w-8 bg-gold-200 rounded-full flex items-center justify-center text-gold-800 font-bold text-xs">
          PM
        </div>
      </header>

      {/* Desktop Top Header Info */}
      <div className="hidden md:flex items-center justify-end px-8 py-4 bg-transparent w-full">
        <div className="text-sm text-charcoal-500 mr-6 font-medium">{dateStr}</div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-sm font-medium text-charcoal-900">Project Manager</div>
            <div className="text-xs text-charcoal-500">SIH 2K26</div>
          </div>
          <div className="h-9 w-9 bg-gold-200 rounded-full flex items-center justify-center text-gold-800 font-bold text-sm">
            PM
          </div>
        </div>
      </div>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-[#E8E4DC] flex justify-around items-center h-16 z-30 pb-safe">
        {[
          { to: '/dashboard', label: 'Home', icon: Home },
          { to: '/reports', label: 'Reports', icon: FileText },
          { to: '/activities', label: 'Activity', icon: Calendar },
          { to: '/attention', label: 'Review', icon: AlertTriangle, badge: attentionCount },
        ].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center w-full h-full space-y-1 ${
                isActive ? 'text-teal-600' : 'text-charcoal-500'
              }`
            }
          >
            <div className="relative">
              <item.icon className="h-5 w-5" />
              {item.badge !== undefined && item.badge > 0 && (
                <span className="absolute -top-1 -right-2 bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[16px] text-center">
                  {item.badge}
                </span>
              )}
            </div>
            <span className="text-[10px] font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  );
}""",
    "src/components/layout/AppLayout.tsx": """import React from 'react';
import { Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useProjectId } from '../../hooks/useProject';
import { reportService } from '../../services/reportService';
import { ToastContainer } from '../ui/Toast';
import { useToast } from '../../hooks/useToast';

export function AppLayout() {
  const projectId = useProjectId();
  const { toasts, removeToast } = useToast();

  const { data: attentionReports } = useQuery({
    queryKey: ['attention', projectId],
    queryFn: () => reportService.getAttentionReports(projectId!),
    enabled: !!projectId,
    refetchInterval: 30000,
  });

  const attentionCount = attentionReports?.length || 0;

  return (
    <div className="flex h-screen overflow-hidden bg-ivory-100">
      <Sidebar attentionCount={attentionCount} />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto overflow-x-hidden relative pb-16 md:pb-0">
        <Header attentionCount={attentionCount} />
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 md:px-8 py-6 md:py-8">
          <Outlet context={{ toasts }} />
        </main>
      </div>
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
}"""
}

for path, content in files.items():
    full_path = os.path.join(r"y:\Projects\SIH 2K26\frontend", path.replace("/", "\\\\"))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\\n")
