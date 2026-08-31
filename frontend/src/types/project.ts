export interface Project {
  _id: string;
  name: string;
  description: string;
  location: string;
  startDate: string;
  plannedEndDate: string;
  createdAt: string;
  updatedAt: string;
}

export interface DashboardData {
  project: Project;
  totalActivities: number;
  completedToday: number;
  inProgress: number;
  needsAttention: number;
  progress: number;
  recentUpdates: RecentUpdate[];
}

export interface RecentUpdate {
  _id: string;
  activityId: string;
  reportId: string;
  previousStatus?: string;
  newStatus?: string;
  previousProgress?: number;
  newProgress?: number;
  message: string;
  createdAt: string;
  activity: {
    _id: string;
    name: string;
    status: string;
  };
}
