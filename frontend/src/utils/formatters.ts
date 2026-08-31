export function formatDate(dateString: string): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatDateTime(dateString: string): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  if (isToday) {
    return 'Today · ' + date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return 'Yesterday · ' + date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
  return formatDate(dateString);
}

export function formatRelative(dateString: string): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateString);
}

export function formatStatus(status: string): string {
  const map: Record<string, string> = {
    NOT_STARTED: 'Not Started',
    IN_PROGRESS: 'In Progress',
    COMPLETED: 'Completed',
    NEEDS_REVIEW: 'Needs Review',
    SUCCESS: 'Processed',
    UNMATCHED: 'Unmatched',
    PROCESSING: 'Processing',
  };
  return map[status] ?? status;
}

export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}
