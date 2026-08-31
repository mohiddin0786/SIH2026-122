import React, { useState } from 'react';
import { FieldReport } from '../../types/report';
import { reportService } from '../../services/reportService';
import { X, AlertTriangle, HelpCircle, Loader2, ArrowRight } from 'lucide-react';

interface ReviewPanelProps {
  report: FieldReport;
  onClose: () => void;
  onResolved: () => void;
}

export function ReviewPanel({ report, onClose, onResolved }: ReviewPanelProps) {
  const [selectedCandidate, setSelectedCandidate] = useState<string>('');
  const [showRejectNote, setShowRejectNote] = useState(false);
  const [note, setNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isUnmatched = report.status === 'UNMATCHED';

  const handleConfirm = async () => {
    if (!selectedCandidate) return;
    setIsSubmitting(true);
    try {
      await reportService.confirmActivity(report.reportId, selectedCandidate);
      onResolved();
    } catch (err) {
      console.error(err);
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    try {
      await reportService.rejectReport(report.reportId, note);
      onResolved();
    } catch (err) {
      console.error(err);
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-0 md:p-6 animate-fade-in"
      style={{
        background: 'rgba(30,25,15,0.25)',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="glass-modal w-full md:w-[580px] max-h-[90vh] md:max-h-[80vh] flex flex-col animate-slide-up rounded-t-2xl md:rounded-2xl">
        {/* Header */}
        <div
          className="flex items-center justify-between p-5 pb-4"
          style={{ borderBottom: '1px solid rgba(190,180,160,0.22)' }}
        >
          <div className="flex items-center gap-2">
            {isUnmatched ? (
              <HelpCircle size={17} className="text-muted" />
            ) : (
              <AlertTriangle size={17} className="text-accent-amber" />
            )}
            <h2 className="font-semibold text-primary">
              Review Report{' '}
              <span className="text-xs font-mono ml-1 text-accent-teal">
                {report.reportId}
              </span>
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors text-muted"
            onMouseOver={(e) => ((e.currentTarget as HTMLElement).style.background = 'rgba(30,25,15,0.06)')}
            onMouseOut={(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
          >
            <X size={17} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          <div className="mb-5">
            <span className="section-label">ORIGINAL REPORT</span>
            <div
              className="p-4 rounded-xl text-sm leading-relaxed"
              style={{
                background: 'rgba(255,255,255,0.50)',
                border: '1px solid rgba(190,180,160,0.22)',
                fontStyle: 'italic',
              }}
            >
              "{report.text}"
            </div>
          </div>

          {!showRejectNote ? (
            <>
              <span className="section-label">SELECT MATCHING ACTIVITY</span>
              {report.candidateActivities?.length > 0 ? (
                <div className="space-y-2 mb-4">
                  {report.candidateActivities.map((candidate) => (
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
                            : 'rgba(190,180,160,0.22)'
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
                              ? '#2A7C6F'
                              : 'rgba(92,87,80,0.30)',
                          background:
                            selectedCandidate === candidate.activityId
                              ? '#2A7C6F'
                              : 'transparent',
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
                            selectedCandidate === candidate.activityId
                              ? '#1F6055'
                              : '#3C3830',
                        }}
                      >
                        {candidate.activityName}
                      </span>
                    </label>
                  ))}
                </div>
              ) : (
                <div
                  className="text-sm text-center py-4 mb-4 text-muted"
                >
                  No candidate activities found.
                </div>
              )}
              <div className="flex items-center gap-2 my-4">
                <div className="flex-1 glass-divider" />
                <span className="text-xs text-muted">OR</span>
                <div className="flex-1 glass-divider" />
              </div>
              <button
                onClick={() => setShowRejectNote(true)}
                className="glass-button-ghost text-sm w-full py-2"
              >
                NONE OF THESE / MARK UNRESOLVED
              </button>
            </>
          ) : (
            <div className="animate-fade-in">
              <span className="section-label">MARK AS UNRESOLVED</span>
              <p className="text-sm mb-4 text-secondary">
                Add an optional note and mark this report as unresolved.
              </p>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="glass-input w-full p-3 text-sm resize-none h-28 mb-4"
                placeholder="Optional note..."
              />
              <button
                onClick={() => setShowRejectNote(false)}
                className="glass-button-ghost text-sm"
              >
                ← Back to candidates
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="p-5 pt-4"
          style={{ borderTop: '1px solid rgba(190,180,160,0.18)' }}
        >
          {!showRejectNote ? (
            <button
              onClick={handleConfirm}
              disabled={!selectedCandidate || isSubmitting}
              className="glass-button-primary w-full py-3 text-sm flex justify-center items-center gap-2"
            >
              {isSubmitting ? (
                <Loader2 size={17} className="animate-spin" />
              ) : (
                <>CONFIRM SELECTION <ArrowRight size={14} /></>
              )}
            </button>
          ) : (
            <button
              onClick={handleReject}
              disabled={isSubmitting}
              className="glass-button-secondary w-full py-3 text-sm flex justify-center items-center gap-2"
              style={{
                borderColor: 'rgba(160,56,40,0.28)',
                }}
            >
              {isSubmitting ? (
                <Loader2 size={17} className="animate-spin" />
              ) : (
                'MARK AS UNRESOLVED'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
