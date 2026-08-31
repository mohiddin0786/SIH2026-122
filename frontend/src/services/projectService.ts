import { api } from './api';
import { Project } from '../types/project';

export const projectService = {
  getProjects: () => api.get<Project[]>('/projects'),
  getProject: (id: string) => api.get<Project>(`/projects/${id}`),
};
