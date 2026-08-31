import React, { useState } from 'react';
import { SubmitReportResponse } from '../../types/report';
import { CheckCircle2, AlertTriangle, HelpCircle, ArrowRight, RotateCcw } from 'lucide-react';
import { Link } from 'react-router-dom';

interface ReportResultProps {
  result: SubmitReportResponse;
  onConfirm?: (activityId: string) => void;
  onReject?: () => void;
  onReset: () => void;
}

export function ReportResult({ result, onConfirm, onReject, onReset }: ReportResultProps) {
  const [selectedCandidate, setSelectedCandidate] = useState<string>('');

  if (result.status === 'SUCCESS') {
    return (
      <div className="glass-panel p-7 flex flex-col items-center text-center animate-fade-in h-full justify-center">
        <div
          className="w-14 h-14 rounded-full flex items-center justify-center mb-5"
          style={{
            background: 'rgba(38,98,64,0.09)',
            border: '1px solid rgba(38,98,64,0.22)',
          }}
        >
          <CheckCircle2 size={28} className="text-accent-green" />
        </div>
        <div
          className="text-[10px] font-bold tracking-[0.20em] uppercase mb-3 text-accent-green"
        >
          Report Processed
        </div>
        <div className="text-xl font-bold mb-1 text-primary">
          {result.activity?.name}
        </div>
        <div className="text-sm mb-6 font-medium text-secondary">
          {result.update?.message}
        </div>
        <div
          className="w-full max-w-xs mb-6 p-4 rounded-xl"
          style={{
            background: 'rgba(255,255,255,0.50)',
            border: '1px solid rgba(190,180,160,0.25)',
          }}
        >
          <div className="flex justify-between text-xs mb-2">
            <span style={{ fontWeight: 600 }}>Progress</span>
            <span style={{ fontWeight: 700 }}>{result.update?.newProgress}%</span>
          </div>
          <div className="glass-progress-bar h-1.5">
            <div
              className="glass-progress-fill h-1.5"
              style={{ width: `${result.update?.newProgress || 0}%` }}
            />
          </div>
        </div>
        <Link
          to={`/activities/${result.activity?._id}`}
          className="glass-button-teal px-6 py-2.5 text-sm flex items-center gap-2 mb-3"
        >
          VIEW ACTIVITY <ArrowRight size={14} />
        </Link>
        <button onClick={onReset} className="glass-button-ghost text-xs flex items-center gap-1.5">
          <RotateCcw size={11} /> Submit another report
        </button>
      </div>
    );
  }

  if (result.status === 'NEEDS_REVIEW') {
    return (
      <div
        className="glass-panel p-6 flex flex-col animate-fade-in h-full"
        style={{ borderColor: 'rgba(184,122,32,0.28)' }}
      >
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle size={18} className="text-accent-amber" />
          <span className="font-bold text-sm text-accent-amber">CONFIRM ACTIVITY</span>
        </div>
        <p className="text-sm mb-5 font-medium text-secondary">
          We found more than one possible activity. Please select the correct one:
        </p>
        <div className="space-y-2.5 flex-1 overflow-y-auto">
          {result.candidates?.map((candidate) => (
            <label
              key={candidate.activityId}
              className="flex items-center p-4 rounded-xl cursor-pointer transition-all"
              style={{
                background:
                  selectedCandidate === candidate.activityId
                    ? 'rgba(42,124,111,0.08)'
                    : 'rgba(255,255,255,0.45)',
                border: `1px solid ${
                  selectedCandidate === candidate.activityId
                    ? 'rgba(42,124,111,0.30)'
                    : 'rgba(190,180,160,0.25)'
                }`,
              }}
            >
              <input
                type="radio"
                name="candidate"
                value={candidate.activityId}
                checked={selectedCandidate === candidate.activityId}
                onChange={() => setSelectedCandidate(candidate.activityId)}
                className="sr-only"
              />
              <div
                className="w-4 h-4 rounded-full border mr-3 flex-shrink-0 flex items-center justify-center"
                style={{
                  borderColor:
                    selectedCandidate === candidate.activityId
                      ? '#16796E'
                      : 'rgba(80,74,66,0.30)',
                  background:
                    selectedCandidate === candidate.activityId ? '#16796E' : 'transparent',
                }}
              >
                {selectedCandidate === candidate.activityId && (
                  <div className="w-1.5 h-1.5 bg-white rounded-full" />
                )}
              </div>
              <span
                className="text-sm font-medium"
                style={{
                  color:
                    selectedCandidate === candidate.activityId ? '#16796E' : '#3A3630',
                }}
              >
                {candidate.activityName}
              </span>
            </label>
          ))}
        </div>
        <div className="mt-5 space-y-2">
          <button
            onClick={() => onConfirm && onConfirm(selectedCandidate)}
            disabled={!selectedCandidate}
            className="glass-button-primary w-full py-3 text-sm flex justify-center items-center gap-2"
          >
            CONFIRM SELECTION <ArrowRight size={14} />
          </button>
          <button
            onClick={onReject}
            className="glass-button-secondary w-full py-2.5 text-sm"
          >
            NONE OF THESE
          </button>
        </div>
      </div>
    );
  }

  // UNMATCHED
  return (
    <div className="glass-panel p-7 flex flex-col items-center text-center animate-fade-in h-full justify-center">
      <div
        className="w-14 h-14 rounded-full flex items-center justify-center mb-5"
        style={{
          background: 'rgba(92,87,80,0.08)',
          border: '1px solid rgba(190,180,160,0.30)',
        }}
      >
        <HelpCircle size={28} className="text-secondary" />
      </div>
      <div
        className="text-[10px] font-bold tracking-[0.20em] uppercase mb-3 text-secondary"
      >
        Activity Not Found
      </div>
      <div className="text-xl font-bold mb-2 text-primary">Could Not Match Report</div>
      <p className="text-sm mb-8 font-medium text-secondary">
        We could not connect this report to an existing project activity. It has been saved for review.
      </p>
      <Link
        to="/attention"
        className="glass-button-secondary px-6 py-2.5 text-sm flex items-center gap-2 mb-3"
      >
        REVIEW REPORTS
      </Link>
      <button onClick={onReset} className="glass-button-ghost text-xs flex items-center gap-1.5">
        <RotateCcw size={11} /> Submit another report
      </button>
    </div>
  );
}
