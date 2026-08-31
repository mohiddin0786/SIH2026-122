import React, { useEffect, useRef } from 'react';

interface ProjectProgressProps {
  progress: number;
}

export function ProjectProgress({ progress }: ProjectProgressProps) {
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (barRef.current) barRef.current.style.width = `${progress}%`;
    }, 120);
    return () => clearTimeout(timer);
  }, [progress]);

  return (
    <div className="glass-panel p-6 md:p-8">
      <div className="flex items-start justify-between mb-6">
        <div>
          <span className="section-label">PROJECT PROGRESS</span>
          <div className="flex items-end gap-2">
            <div
              className="text-5xl font-bold tracking-tight"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {progress}
            </div>
            <div className="text-2xl font-medium mb-1 text-secondary">%</div>
          </div>
          <div className="text-sm mt-1 font-medium text-secondary">Overall construction execution progress</div>
        </div>
        <div className="text-right">
          <div
            className="text-xs font-bold tracking-widest text-accent-teal"
          >
            {100 - progress}% REMAINING
          </div>
        </div>
      </div>
      <div className="glass-progress-bar h-1.5">
        <div
          ref={barRef}
          className="glass-progress-fill h-1.5"
          style={{ width: '0%' }}
        />
      </div>
    </div>
  );
}
