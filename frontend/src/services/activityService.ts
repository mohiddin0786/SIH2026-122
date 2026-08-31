import { api } from './api';
import { Activity, ActivityUpdate } from '../types/activity';

export const activityService = {
  getActivities: (projectId: string) =>
    api.get<Activity[]>(`/projects/${projectId}/activities`),
  getActivity: (activityId: string) =>
    api.get<Activity>(`/activities/${activityId}`),
  getActivityUpdates: (activityId: string) =>
    api.get<ActivityUpdate[]>(`/activities/${activityId}/updates`),
};
