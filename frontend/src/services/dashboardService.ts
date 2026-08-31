import { api } from './api';
import { DashboardData } from '../types/project';

export const dashboardService = {
  getDashboard: (projectId: string) =>
    api.get<DashboardData>(`/projects/${projectId}/dashboard`),
};
