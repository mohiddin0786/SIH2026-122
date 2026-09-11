// TODO(backend): a new terminal status (e.g. 'RESOLVED') may be introduced after
// violation-resolution work lands on the backend. Confirm the exact string value
// with backend before adding it here — do not guess.
export type ReportStatus = 'PROCESSING' | 'SUCCESS' | 'NEEDS_REVIEW' | 'UNMATCHED' | 'SCHEDULE_VIOLATION';

export interface PredecessorStatusItem {
  activityId: string;
  activityName?: string;
  status: string; // NOT_STARTED | IN_PROGRESS | COMPLETED
}

export interface ConsistencyViolation {
  rule: 'predecessor_incomplete' | 'predecessor_not_found';
  activityId: string;
  predecessorId: string;
  predecessorStatus: string;
  message: string;
  predecessorChain?: PredecessorStatusItem[];
}

export interface ResolveViolationItem {
  predecessorId: string;
  action: 'log_report' | 'mark_resolved';
  note?: string;
}

export interface ResolveViolationRequest {
  items: ResolveViolationItem[];
}

export interface BulkCompleteChainRequest {
  predecessorIds: string[];
  note?: string;
}

export interface Candidate {
  activityId: string;
  activityName: string;
  activityArea?: string | null;
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
  violation?: ConsistencyViolation | null;
  userDecision?: string;
  reviewNote?: string;
  createdAt: string;
  updatedAt: string;
}

export interface SubmitReportResponse {
  status: 'SUCCESS' | 'NEEDS_REVIEW' | 'UNMATCHED' | 'SCHEDULE_VIOLATION';
  reportId: string;
  activity?: import('./activity').Activity;
  update?: import('./activity').ActivityUpdate;
  candidates?: Candidate[];
  violation?: ConsistencyViolation;
}

export interface BatchItem {
  text: string;
  sourceType?: string;
  reportDate?: string;
}

export interface BatchResultItem {
  status: 'SUCCESS' | 'NEEDS_REVIEW' | 'UNMATCHED' | 'SCHEDULE_VIOLATION' | 'ERROR';
  reportId?: string;
  activity?: import('./activity').Activity;
  update?: import('./activity').ActivityUpdate;
  candidates?: Candidate[];
  violation?: ConsistencyViolation;
  error?: string;
}

export interface BatchSummary {
  total: number;
  success: number;
  needsReview: number;
  scheduleViolation: number;
  unmatched: number;
  errors: number;
}

export interface BatchSubmitResponse {
  results: BatchResultItem[];
  summary: BatchSummary;
  batchOrdering: string[][];
}

export interface ParsedUploadResponse {
  items: BatchItem[];
  count: number;
}
