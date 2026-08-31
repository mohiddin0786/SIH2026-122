import React from 'react';
import { Search } from 'lucide-react';

interface ActivityFiltersProps {
  search: string;
  onSearchChange: (v: string) => void;
  statusFilter: string;
  onStatusFilterChange: (v: string) => void;
}

const STATUSES = [
  { value: '', label: 'All' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'IN_PROGRESS', label: 'In Progress' },
  { value: 'NOT_STARTED', label: 'Not Started' },
  { value: 'NEEDS_REVIEW', label: 'Needs Review' },
];

export function ActivityFilters({
  search, onSearchChange, statusFilter, onStatusFilterChange,
}: ActivityFiltersProps) {
  return (
    <div className="flex flex-col md:flex-row gap-3 mb-6">
      <div className="relative flex-1">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
        />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search activities..."
          className="glass-input w-full pl-9 pr-4 py-2.5 text-sm"
        />
      </div>
      <div className="flex gap-2 flex-wrap">
        {STATUSES.map((s) => (
          <button
            key={s.value}
            onClick={() => onStatusFilterChange(s.value)}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg transition-all"
            style={{
              background:
                statusFilter === s.value
                  ? 'rgba(42,124,111,0.10)'
                  : 'rgba(255,255,255,0.55)',
              border: `1px solid ${
                statusFilter === s.value
                  ? 'rgba(42,124,111,0.30)'
                  : 'rgba(190,180,160,0.28)'
              }`,
              color: statusFilter === s.value ? '#1F6055' : '#5C5750',
            }}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
