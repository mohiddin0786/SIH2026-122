import { api } from './api';
import {
  BatchItem,
  BatchSubmitResponse,
  FieldReport,
  ParsedUploadResponse,
  SubmitReportResponse,
} from '../types/report';

export const reportService = {
  getReports: (projectId: string) =>
    api.get<FieldReport[]>(`/projects/${projectId}/reports`),
  getReport: (reportId: string) =>
    api.get<FieldReport>(`/reports/${reportId}`),
  submitReport: (projectId: string, text: string) =>
    api.post<SubmitReportResponse>(`/projects/${projectId}/reports`, { text }),
  submitBatch: (projectId: string, items: BatchItem[]) =>
    api.post<BatchSubmitResponse>(`/projects/${projectId}/reports/batch`, { items }),
  parseUpload: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.postForm<ParsedUploadResponse>(`/projects/${projectId}/reports/parse`, formData);
  },
  parseText: (projectId: string, text: string) => {
    const formData = new FormData();
    formData.append('text', text);
    return api.postForm<ParsedUploadResponse>(`/projects/${projectId}/reports/parse`, formData);
  },
  getAttentionReports: (projectId: string) =>
    api.get<FieldReport[]>(`/projects/${projectId}/attention`),
  confirmActivity: (reportId: string, activityId: string) =>
    api.post<SubmitReportResponse>(`/reports/${reportId}/confirm`, { activityId }),
  rejectReport: (reportId: string, note?: string) =>
    api.post<{ status: string; reportId: string }>(`/reports/${reportId}/reject`, { note }),
};
