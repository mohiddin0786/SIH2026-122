import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FileText, ClipboardList, AlertTriangle } from 'lucide-react';

interface HeaderProps {
  attentionCount: number;
  isDark: boolean;
  onToggleDark: () => void;
}

export function Header({ attentionCount, isDark, onToggleDark }: HeaderProps) {
  const dateStr = new Date().toLocaleDateString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  });

  return (
    <>
      {/* Mobile top bar */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 sticky top-0 z-30 glass-panel border-b border-t-0 border-r-0 border-l-0 rounded-none">
        <div>
          <div className="text-xs font-bold tracking-widest text-primary">PEUS</div>
          <div className="text-[10px] font-medium text-secondary">Project Execution</div>
        </div>
        <div className="flex items-center gap-2">
          {/* Dark mode toggle */}
          <button
            onClick={onToggleDark}
            className="h-8 w-8 rounded-full flex items-center justify-center transition-all hover:opacity-80 border"
            title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            style={{
               background: 'var(--accent-teal-bg)',
               borderColor: 'var(--accent-teal-border)',
               color: 'var(--accent-teal)'
            }}
          >
            {isDark ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            )}
          </button>
          <div
            className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold border"
             style={{
               background: 'var(--accent-teal-bg)',
               borderColor: 'var(--accent-teal-border)',
               color: 'var(--accent-teal)'
            }}
          >PM</div>
        </div>
      </header>

      {/* Desktop top strip */}
      <div className="hidden md:flex items-center justify-end px-8 py-3 border-b" style={{ borderColor: 'var(--glass-card-border)' }}>
        <span className="text-xs mr-6 font-medium text-secondary">{dateStr}</span>
        <div className="flex items-center gap-3">
          {/* Dark mode toggle */}
          <button
            onClick={onToggleDark}
            className="h-8 w-8 rounded-full flex items-center justify-center transition-all hover:scale-105 border"
            title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            style={{
               background: 'var(--accent-teal-bg)',
               borderColor: 'var(--accent-teal-border)',
               color: 'var(--accent-teal)'
            }}
          >
            {isDark ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            )}
          </button>
          <div className="text-right">
            <div className="text-xs font-semibold text-primary">Project Manager</div>
            <div className="text-[10px] font-medium text-secondary">SIH 2K26</div>
          </div>
          <div
            className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold border"
             style={{
               background: 'var(--accent-teal-bg)',
               borderColor: 'var(--accent-teal-border)',
               color: 'var(--accent-teal)'
            }}
          >PM</div>
        </div>
      </div>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 flex justify-around items-center h-16 z-40 glass-panel border-t border-b-0 border-r-0 border-l-0 rounded-none">
        {[
          { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
          { to: '/reports', label: 'Reports', icon: FileText },
          { to: '/activities', label: 'Activities', icon: ClipboardList },
          { to: '/attention', label: 'Attention', icon: AlertTriangle, badge: attentionCount },
        ].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `flex flex-col items-center gap-0.5 px-3 py-2 ${isActive ? 'text-accent-teal' : 'text-secondary'}`}
          >
            <div className="relative">
              <item.icon size={20} />
              {item.badge !== undefined && item.badge > 0 && (
                <span
                  className="absolute -top-1.5 -right-2 text-[9px] font-bold px-1 rounded-full"
                  style={{ background: 'var(--accent-amber)', color: '#fff' }}
                >
                  {item.badge}
                </span>
              )}
            </div>
            <span className="text-[10px] font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  );
}
