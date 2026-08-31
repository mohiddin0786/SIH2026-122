export type ActivityStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED' | 'NEEDS_REVIEW';
export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface Activity {
  _id: string;
  projectId: string;
  name: string;
  description: string;
  status: ActivityStatus;
  progress: number;
  plannedStart: string;
  plannedFinish: string;
  actualStart?: string;
  actualFinish?: string;
  location: string;
  priority: Priority;
  assignedTo?: string;
  latestReportId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ActivityUpdate {
  _id: string;
  activityId: string;
  reportId: string;
  previousStatus?: ActivityStatus;
  newStatus?: ActivityStatus;
  previousProgress?: number;
  newProgress?: number;
  message: string;
  createdAt: string;
}
