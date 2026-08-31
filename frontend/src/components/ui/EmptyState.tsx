import React from 'react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="glass-panel flex flex-col items-center justify-center text-center py-16 px-8">
      {icon && (
        <div className="mb-4 text-accent-teal">
          {icon}
        </div>
      )}
      <h3 className="font-semibold text-lg mb-2 text-primary">{title}</h3>
      {description && (
        <p className="text-sm mb-6 font-medium text-secondary">{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="glass-button-primary px-6 py-2.5 text-sm"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
