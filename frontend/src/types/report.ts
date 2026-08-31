export type ReportStatus = 'PROCESSING' | 'SUCCESS' | 'NEEDS_REVIEW' | 'UNMATCHED';

export interface Candidate {
  activityId: string;
  activityName: string;
}

export interface FieldReport {
  _id: string;
  reportId: string;
  projectId: string;
  text: string;
  submittedAt: string;
  status: ReportStatus;
  matchedActivityId?: string;
  candidateActivities: Candidate[];
  userDecision?: string;
  reviewNote?: string;
  createdAt: string;
  updatedAt: string;
}

export interface SubmitReportResponse {
  status: 'SUCCESS' | 'NEEDS_REVIEW' | 'UNMATCHED';
  reportId: string;
  activity?: import('./activity').Activity;
  update?: import('./activity').ActivityUpdate;
  candidates?: Candidate[];
}

export interface BatchItem {
  text: string;
  sourceType?: string;
  reportDate?: string;
}

export interface BatchResultItem {
  status: 'SUCCESS' | 'NEEDS_REVIEW' | 'UNMATCHED' | 'ERROR';
  reportId?: string;
  activity?: import('./activity').Activity;
  update?: import('./activity').ActivityUpdate;
  candidates?: Candidate[];
  error?: string;
}

export interface BatchSummary {
  total: number;
  success: number;
  needsReview: number;
  unmatched: number;
  errors: number;
}

export interface BatchSubmitResponse {
  results: BatchResultItem[];
  summary: BatchSummary;
}

export interface ParsedUploadResponse {
  items: BatchItem[];
  count: number;
}
