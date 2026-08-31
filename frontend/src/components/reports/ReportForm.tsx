import React, { useState } from 'react';
import { reportService } from '../../services/reportService';
import { SubmitReportResponse } from '../../types/report';
import { Loader2, ArrowRight } from 'lucide-react';

interface ReportFormProps {
  projectId: string;
  onSuccess: (result: SubmitReportResponse) => void;
}

export function ReportForm({ projectId, onSuccess }: ReportFormProps) {
  const [text, setText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await reportService.submitReport(projectId, text);
      onSuccess(response);
    } catch (err: any) {
      setError(err.message || 'Failed to submit report');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="glass-panel p-6 h-full flex flex-col">
      <span className="section-label">NEW FIELD REPORT</span>

      <form onSubmit={handleSubmit} className="flex flex-col flex-1">
        <div className="mb-4">
          <label
            className="text-xs font-semibold uppercase tracking-widest mb-2 block text-muted"
          >
            Field Update
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="glass-input w-full p-4 text-sm leading-relaxed resize-none"
            style={{ minHeight: '200px', fontFamily: 'Inter, system-ui' }}
            placeholder={`Describe the field update...
e.g. SP101 installation completed in Area A. All connections verified.`}
            disabled={isSubmitting}
            required
          />
          <div className="text-right mt-1.5 text-xs text-muted">
            {text.length} / 2000
          </div>
        </div>

        {error && (
          <div
            className="mb-4 p-3 rounded-lg text-sm"
            style={{
              background: 'rgba(160,56,40,0.07)',
              border: '1px solid rgba(160,56,40,0.22)',
              }}
          >
            {error}
          </div>
        )}

        <div className="mt-auto">
          <button
            type="submit"
            disabled={isSubmitting || !text.trim()}
            className="glass-button-primary w-full py-3 text-sm flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <><Loader2 className="animate-spin" size={17} /> PROCESSING REPORT...</>
            ) : (
              <>SUBMIT REPORT <ArrowRight size={15} /></>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
