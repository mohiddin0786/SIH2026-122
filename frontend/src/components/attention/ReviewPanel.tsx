import React, { useState } from 'react';
import { FieldReport, PredecessorStatusItem, ResolveViolationItem } from '../../types/report';
import { reportService } from '../../services/reportService';
import { X, AlertTriangle, HelpCircle, ShieldAlert, Loader2, ArrowRight, CheckSquare } from 'lucide-react';

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

  // Violation-resolution state
  // Per-predecessor action selections, keyed by activityId
  const [rowActions, setRowActions] = useState<Record<string, 'log_report' | 'mark_resolved'>>({});
  // Bulk override (Option 2)
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkNote, setBulkNote] = useState('');

  const isUnmatched = report.status === 'UNMATCHED';
  const isViolation = report.status === 'SCHEDULE_VIOLATION';

  // Build the predecessor list: use predecessorChain if available (backend-dependent, may not
  // be returned yet), otherwise fall back to the single predecessor fields.
  const predecessorRows: PredecessorStatusItem[] = (() => {
    if (report.violation?.predecessorChain && report.violation.predecessorChain.length > 0) {
      return report.violation.predecessorChain;
    }
    if (report.violation?.predecessorId) {
      return [
        {
          activityId: report.violation.predecessorId,
          activityName: undefined,
          status: report.violation.predecessorStatus,
        },
      ];
    }
    return [];
  })();

  const allRowsSelected =
    predecessorRows.length > 0 &&
    predecessorRows.every((row) => rowActions[row.activityId] !== undefined);

  const canSubmitViolation = bulkMode || allRowsSelected;

  const handleRowActionChange = (
    activityId: string,
    action: 'log_report' | 'mark_resolved'
  ) => {
    setRowActions((prev) => ({ ...prev, [activityId]: action }));
  };

  const handleViolationSubmit = async () => {
    if (!canSubmitViolation) return;
    setIsSubmitting(true);
    try {
      if (bulkMode) {
        const predecessorIds = predecessorRows.map((r) => r.activityId);
        await reportService.bulkCompleteChain(report.reportId, predecessorIds, bulkNote || undefined);
      } else {
        const items: ResolveViolationItem[] = predecessorRows.map((row) => ({
          predecessorId: row.activityId,
          action: rowActions[row.activityId],
        }));
        await reportService.resolveViolation(report.reportId, items);
      }
      onResolved();
    } catch (err) {
      console.error(err);
      setIsSubmitting(false);
    }
  };

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
      <div className="glass-modal w-full md:w-[620px] max-h-[90vh] md:max-h-[85vh] flex flex-col animate-slide-up rounded-t-2xl md:rounded-2xl">
        {/* Header */}
        <div
          className="flex items-center justify-between p-5 pb-4"
          style={{ borderBottom: '1px solid rgba(190,180,160,0.22)' }}
        >
          <div className="flex items-center gap-2">
            {isViolation ? (
              <ShieldAlert size={17} style={{ color: '#A03828' }} />
            ) : isUnmatched ? (
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

          {isViolation ? (
            <div className="animate-fade-in">
              {/* Violation summary */}
              <span className="section-label">VIOLATION DETAIL</span>
              <div
                className="p-4 rounded-xl text-sm mb-4"
                style={{ background: 'rgba(160,56,40,0.06)', border: '1px solid rgba(160,56,40,0.22)' }}
              >
                {report.violation?.message}
              </div>
              <p className="text-xs text-muted mb-5">
                Report matched activity <strong>{report.matchedActivityId}</strong> with high
                confidence, but was blocked because predecessor(s) are not yet complete. Choose
                how to resolve each predecessor, or use the bulk override below.
              </p>

              {/* ── Option 1: Per-predecessor itemized resolution ── */}
              {!showRejectNote && (
                <>
                  <span className="section-label">RESOLVE PREDECESSORS</span>
                  {predecessorRows.length > 0 ? (
                    <div className="space-y-2 mb-5">
                      {predecessorRows.map((row) => {
                        const selected = rowActions[row.activityId];
                        const disabled = bulkMode;
                        return (
                          <div
                            key={row.activityId}
                            className="p-4 rounded-xl text-sm"
                            style={{
                              background: disabled
                                ? 'rgba(190,180,160,0.06)'
                                : 'rgba(255,255,255,0.45)',
                              border: '1px solid rgba(190,180,160,0.22)',
                              opacity: disabled ? 0.45 : 1,
                            }}
                          >
                            {/* Row header */}
                            <div className="flex items-center justify-between mb-3">
                              <div>
                                <span className="font-medium text-primary">
                                  {row.activityName ?? row.activityId}
                                </span>
                                {row.activityName && (
                                  <span className="ml-2 text-xs font-mono text-muted">
                                    {row.activityId}
                                  </span>
                                )}
                              </div>
                              <span
                                className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                                style={{
                                  background: 'rgba(160,56,40,0.09)',
                                  border: '1px solid rgba(160,56,40,0.22)',
                                  color: '#A03828',
                                }}
                              >
                                {row.status}
                              </span>
                            </div>
                            {/* Per-row action selector */}
                            <div className="flex gap-3">
                              {(
                                [
                                  { value: 'log_report', label: 'Log Field Report' },
                                  { value: 'mark_resolved', label: 'Mark Resolved' },
                                ] as const
                              ).map((opt) => (
                                <label
                                  key={opt.value}
                                  className="flex items-center gap-2 cursor-pointer"
                                  style={{ pointerEvents: disabled ? 'none' : 'auto' }}
                                >
                                  <input
                                    type="radio"
                                    name={`action-${row.activityId}`}
                                    value={opt.value}
                                    checked={selected === opt.value}
                                    onChange={() =>
                                      handleRowActionChange(row.activityId, opt.value)
                                    }
                                    disabled={disabled}
                                    className="sr-only"
                                  />
                                  <div
                                    className="w-4 h-4 rounded-full border flex-shrink-0 flex items-center justify-center"
                                    style={{
                                      borderColor:
                                        selected === opt.value
                                          ? '#2A7C6F'
                                          : 'rgba(92,87,80,0.30)',
                                      background:
                                        selected === opt.value ? '#2A7C6F' : 'transparent',
                                    }}
                                  >
                                    {selected === opt.value && (
                                      <div className="w-1.5 h-1.5 bg-white rounded-full" />
                                    )}
                                  </div>
                                  <span
                                    className="text-xs font-medium"
                                    style={{
                                      color:
                                        selected === opt.value ? '#1F6055' : '#5C5750',
                                    }}
                                  >
                                    {opt.label}
                                  </span>
                                </label>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-sm text-center py-4 mb-4 text-muted">
                      No predecessor data available.
                    </div>
                  )}

                  {/* ── Option 2: Bulk override ── */}
                  <div
                    className="p-4 rounded-xl mb-5"
                    style={{
                      background: 'rgba(184,122,32,0.07)',
                      border: '1px solid rgba(184,122,32,0.30)',
                    }}
                  >
                    <label className="flex items-start gap-3 cursor-pointer">
                      <div className="mt-0.5 flex-shrink-0">
                        <input
                          type="checkbox"
                          checked={bulkMode}
                          onChange={(e) => setBulkMode(e.target.checked)}
                          className="sr-only"
                        />
                        <div
                          className="w-4 h-4 rounded border-2 flex items-center justify-center"
                          style={{
                            borderColor: bulkMode ? '#B87A20' : 'rgba(184,122,32,0.50)',
                            background: bulkMode ? '#B87A20' : 'transparent',
                          }}
                        >
                          {bulkMode && <CheckSquare size={10} style={{ color: '#fff' }} />}
                        </div>
                      </div>
                      <div>
                        <span className="text-sm font-semibold" style={{ color: '#8A5A10' }}>
                          All predecessors are actually done — mark all as completed
                        </span>
                        <p className="text-xs mt-0.5" style={{ color: '#A07030' }}>
                          Override: use only when you've confirmed outside the system that every
                          predecessor in the chain is finished.
                        </p>
                      </div>
                    </label>
                    {bulkMode && (
                      <textarea
                        value={bulkNote}
                        onChange={(e) => setBulkNote(e.target.value)}
                        className="glass-input w-full p-3 text-sm resize-none h-20 mt-3"
                        placeholder="Optional note for the bulk override..."
                      />
                    )}
                  </div>

                  {/* ── Option 3: Existing mark-unresolved path ── */}
                  <div className="flex items-center gap-2 my-4">
                    <div className="flex-1 glass-divider" />
                    <span className="text-xs text-muted">OR</span>
                    <div className="flex-1 glass-divider" />
                  </div>
                  <button
                    onClick={() => setShowRejectNote(true)}
                    className="glass-button-ghost text-sm w-full py-2"
                  >
                    REPORT IS WRONG — MARK AS UNRESOLVED
                  </button>
                </>
              )}

              {/* Unresolved note view (Option 3 expanded) */}
              {showRejectNote && (
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
                    ← Back to resolution options
                  </button>
                </div>
              )}
            </div>
          ) : !showRejectNote ? (
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
                      <div className="min-w-0">
  <div
    className="text-[11px] font-mono font-semibold mb-0.5"
    style={{
      color:
        selectedCandidate === candidate.activityId
          ? '#1F6055'
          : '#6B655D',
    }}
  >
    {candidate.activityId}
  </div>

  <div
    className="text-sm font-medium"
    style={{
      color:
        selectedCandidate === candidate.activityId
          ? '#1F6055'
          : '#3C3830',
    }}
  >
    {candidate.activityName}
    {candidate.activityArea && (
  <div className="text-xs text-muted mt-1">
    Area: {candidate.activityArea}
  </div>
)}
  </div>
</div>
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
          {isViolation ? (
            showRejectNote ? (
              <button
                onClick={handleReject}
                disabled={isSubmitting}
                className="glass-button-secondary w-full py-3 text-sm flex justify-center items-center gap-2"
                style={{ borderColor: 'rgba(160,56,40,0.28)' }}
              >
                {isSubmitting ? <Loader2 size={17} className="animate-spin" /> : 'MARK AS UNRESOLVED'}
              </button>
            ) : (
              <button
                onClick={handleViolationSubmit}
                disabled={!canSubmitViolation || isSubmitting}
                className="glass-button-primary w-full py-3 text-sm flex justify-center items-center gap-2"
              >
                {isSubmitting ? (
                  <Loader2 size={17} className="animate-spin" />
                ) : bulkMode ? (
                  <>MARK ALL PREDECESSORS COMPLETE <ArrowRight size={14} /></>
                ) : (
                  <>SUBMIT RESOLUTION <ArrowRight size={14} /></>
                )}
              </button>
            )
          ) : !showRejectNote ? (
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

