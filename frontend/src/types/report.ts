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
