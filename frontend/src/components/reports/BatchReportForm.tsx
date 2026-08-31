import React, { useState } from 'react';
import { reportService } from '../../services/reportService';
import { BatchItem, BatchSubmitResponse } from '../../types/report';
import { Loader2, ArrowRight, Upload, FileText, Plus, X, Trash2 } from 'lucide-react';

type InputMode = 'paste' | 'file' | 'multi';

interface BatchReportFormProps {
  projectId: string;
  onSuccess: (result: BatchSubmitResponse) => void;
}

export function BatchReportForm({ projectId, onSuccess }: BatchReportFormProps) {
  const [mode, setMode] = useState<InputMode>('paste');
  const [pasteText, setPasteText] = useState('');
  const [multiEntries, setMultiEntries] = useState<string[]>(['']);
  const [file, setFile] = useState<File | null>(null);

  const [preview, setPreview] = useState<BatchItem[] | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resetPreview = () => {
    setPreview(null);
    setError(null);
  };

  const handleModeChange = (m: InputMode) => {
    setMode(m);
    resetPreview();
  };

  const handleParse = async () => {
    setError(null);
    setIsParsing(true);
    try {
      const res =
        mode === 'file' && file
          ? await reportService.parseUpload(projectId, file)
          : await reportService.parseText(projectId, pasteText);
      setPreview(res.items);
    } catch (err: any) {
      setError(err.message || 'Failed to parse input');
    } finally {
      setIsParsing(false);
    }
  };

  const updatePreviewItem = (idx: number, text: string) => {
    if (!preview) return;
    const next = [...preview];
    next[idx] = { ...next[idx], text };
    setPreview(next);
  };

  const removePreviewItem = (idx: number) => {
    if (!preview) return;
    setPreview(preview.filter((_, i) => i !== idx));
  };

  const updateMultiEntry = (idx: number, value: string) => {
    const next = [...multiEntries];
    next[idx] = value;
    setMultiEntries(next);
  };

  const addMultiEntry = () => setMultiEntries([...multiEntries, '']);

  const removeMultiEntry = (idx: number) => {
    if (multiEntries.length === 1) return;
    setMultiEntries(multiEntries.filter((_, i) => i !== idx));
  };

  const handleSubmit = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      let items: BatchItem[];
      if (mode === 'multi') {
        items = multiEntries
          .map((t) => t.trim())
          .filter(Boolean)
          .map((text) => ({ text, sourceType: 'ui_multi' }));
      } else {
        if (!preview) {
          setError('Parse the input first to preview reports.');
          setIsSubmitting(false);
          return;
        }
        items = preview.filter((i) => i.text.trim());
      }

      if (items.length === 0) {
        setError('No reports to submit.');
        setIsSubmitting(false);
        return;
      }

      const result = await reportService.submitBatch(projectId, items);
      onSuccess(result);
    } catch (err: any) {
      setError(err.message || 'Failed to submit batch');
    } finally {
      setIsSubmitting(false);
    }
  };

  const canParse = (mode === 'paste' && pasteText.trim()) || (mode === 'file' && file);
  const canSubmit =
    mode === 'multi'
      ? multiEntries.some((t) => t.trim())
      : preview !== null && preview.some((i) => i.text.trim());

  return (
    <div className="glass-panel p-6 h-full flex flex-col">
      <span className="section-label">BULK FIELD REPORTS</span>

      <div className="flex gap-2 my-4">
        <TabButton active={mode === 'paste'} onClick={() => handleModeChange('paste')} icon={<FileText size={14} />}>
          Paste Text
        </TabButton>
        <TabButton active={mode === 'file'} onClick={() => handleModeChange('file')} icon={<Upload size={14} />}>
          Upload File
        </TabButton>
        <TabButton active={mode === 'multi'} onClick={() => handleModeChange('multi')} icon={<Plus size={14} />}>
          Multiple Entries
        </TabButton>
      </div>

      <div className="flex-1 overflow-y-auto">
        {mode === 'paste' && !preview && (
          <textarea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            className="glass-input w-full p-4 text-sm leading-relaxed resize-none"
            style={{ minHeight: '220px', fontFamily: 'Inter, system-ui' }}
            placeholder={`Paste multiple field updates — e.g. one per line, or separated by dates:\n\n2026-08-28: SP101 installation completed in Area A.\n2026-08-29: Hydrotest started on FT-102.`}
            disabled={isParsing}
          />
        )}

        {mode === 'file' && !preview && (
          <label
            className="glass-input w-full flex flex-col items-center justify-center gap-2 cursor-pointer text-center"
            style={{ minHeight: '220px', border: '1px dashed rgba(190,180,160,0.45)' }}
          >
            <Upload size={22} className="text-muted" />
            <span className="text-sm font-medium text-secondary">
              {file ? file.name : 'Click to select an Excel (.xlsx/.csv) or PDF file'}
            </span>
            <input
              type="file"
              accept=".xlsx,.xls,.csv,.pdf"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
        )}

        {mode === 'multi' && (
          <div className="space-y-3">
            {multiEntries.map((entry, idx) => (
              <div key={idx} className="flex gap-2 items-start">
                <textarea
                  value={entry}
                  onChange={(e) => updateMultiEntry(idx, e.target.value)}
                  className="glass-input flex-1 p-3 text-sm leading-relaxed resize-none"
                  style={{ minHeight: '80px', fontFamily: 'Inter, system-ui' }}
                  placeholder={`Report #${idx + 1}...`}
                />
                <button
                  onClick={() => removeMultiEntry(idx)}
                  disabled={multiEntries.length === 1}
                  className="glass-button-ghost p-2 mt-1"
                  title="Remove"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
            <button onClick={addMultiEntry} className="glass-button-secondary w-full py-2 text-xs flex items-center justify-center gap-1.5">
              <Plus size={13} /> ADD ANOTHER REPORT
            </button>
          </div>
        )}

        {preview && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-widest mb-2 text-muted">
              Detected {preview.length} report{preview.length !== 1 ? 's' : ''} — review before submitting
            </div>
            <div className="space-y-2.5">
              {preview.map((item, idx) => (
                <div key={idx} className="glass-card p-3 flex gap-2 items-start">
                  <span className="text-xs font-bold font-mono text-accent-teal mt-2">#{idx + 1}</span>
                  <textarea
                    value={item.text}
                    onChange={(e) => updatePreviewItem(idx, e.target.value)}
                    className="glass-input flex-1 p-2 text-sm leading-relaxed resize-none"
                    style={{ minHeight: '60px', fontFamily: 'Inter, system-ui' }}
                  />
                  <button onClick={() => removePreviewItem(idx)} className="glass-button-ghost p-1.5 mt-1" title="Remove">
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
            <button onClick={resetPreview} className="glass-button-ghost text-xs mt-3">
              ← Start over
            </button>
          </div>
        )}
      </div>

      {error && (
        <div
          className="mt-4 p-3 rounded-lg text-sm"
          style={{ background: 'rgba(160,56,40,0.07)', border: '1px solid rgba(160,56,40,0.22)' }}
        >
          {error}
        </div>
      )}

      <div className="mt-4">
        {(mode === 'paste' || mode === 'file') && !preview ? (
          <button
            onClick={handleParse}
            disabled={!canParse || isParsing}
            className="glass-button-primary w-full py-3 text-sm flex items-center justify-center gap-2"
          >
            {isParsing ? (
              <><Loader2 className="animate-spin" size={17} /> PARSING...</>
            ) : (
              <>PREVIEW REPORTS <ArrowRight size={15} /></>
            )}
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isSubmitting}
            className="glass-button-primary w-full py-3 text-sm flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <><Loader2 className="animate-spin" size={17} /> PROCESSING BATCH...</>
            ) : (
              <>SUBMIT ALL <ArrowRight size={15} /></>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={active ? 'glass-button-teal' : 'glass-button-ghost'}
      style={{ fontSize: '11px', padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
    >
      {icon}
      {children}
    </button>
  );
}
