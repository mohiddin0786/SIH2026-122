import React from 'react';
import { CheckCircle2, XCircle, Info, X } from 'lucide-react';
import { Toast } from '../../hooks/useToast';

interface ToastItemProps {
  toast: Toast;
  onRemove: (id: string) => void;
}

function ToastItem({ toast, onRemove }: ToastItemProps) {
  const config = {
    success: {
      border: 'rgba(45,106,71,0.25)',
      icon: <CheckCircle2 size={17} style={{ flexShrink: 0 }} />,
    },
    error: {
      border: 'rgba(160,56,40,0.25)',
      icon: <XCircle size={17} style={{ flexShrink: 0 }} />,
    },
    info: {
      border: 'rgba(42,124,111,0.25)',
      icon: <Info size={17} style={{ flexShrink: 0 }} />,
    },
  };
  const c = config[toast.type];
  return (
    <div
      className="flex items-start gap-3 px-4 py-3 rounded-xl min-w-[280px] max-w-sm animate-slide-up"
      style={{
        background: 'rgba(252,249,242,0.94)',
        backdropFilter: 'blur(20px)',
        border: `1px solid ${c.border}`,
        boxShadow: '0 8px 32px rgba(30,25,15,0.12)',
      }}
    >
      {c.icon}
      <span className="flex-1 text-sm text-primary">{toast.message}</span>
      <button
        onClick={() => onRemove(toast.id)}
        className="text-muted hover:text-charcoal transition-colors flex-shrink-0"
      >
        <X size={15} />
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onRemove: (id: string) => void;
}

export function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  return (
    <div className="fixed bottom-20 md:bottom-6 right-6 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onRemove={onRemove} />
      ))}
    </div>
  );
}
