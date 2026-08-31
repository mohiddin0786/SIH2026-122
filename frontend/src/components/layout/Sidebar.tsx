import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FileText, ClipboardList, AlertTriangle } from 'lucide-react';

interface SidebarProps {
  attentionCount: number;
}

export function Sidebar({ attentionCount }: SidebarProps) {
  const navItems = [
    { to: '/dashboard',  label: 'Dashboard',       icon: LayoutDashboard },
    { to: '/reports',    label: 'Field Reports',    icon: FileText },
    { to: '/activities', label: 'Activities',       icon: ClipboardList },
    { to: '/attention',  label: 'Needs Attention',  icon: AlertTriangle, badge: attentionCount },
  ];

  return (
    <aside className="hidden md:flex flex-col w-[240px] flex-shrink-0 glass-sidebar h-screen sticky top-0 z-40">
      {/* Brand */}
      <div className="p-7 pb-6">
        <div className="text-[10px] font-bold tracking-[0.22em] uppercase mb-3 section-label" style={{ marginBottom: '0.5rem' }}>
          Project Control
        </div>
        <h1 className="font-bold text-sm leading-snug tracking-tight" style={{ color: 'currentColor' }}>
          PROJECT EXECUTION
        </h1>
        <h2 className="font-medium text-xs tracking-widest mt-0.5 text-accent-teal">
          CONTROL CENTER
        </h2>
      </div>

      <div className="glass-divider mx-5 mb-5" />

      {/* Navigation */}
      <nav className="flex-1 px-4 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `glass-nav-item px-3 py-2.5 text-sm ${isActive ? 'active' : ''}`
            }
          >
            <item.icon size={16} className="mr-3 flex-shrink-0" />
            <span className="flex-1">{item.label}</span>
            {item.badge !== undefined && item.badge > 0 && (
              <span className="ml-2 glass-badge-amber">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer info */}
      <div className="glass-divider mx-5 mb-4" />
      <div className="p-5 pt-4">
        <div className="text-[10px] font-bold tracking-[0.18em] uppercase mb-1.5 section-label" style={{ marginBottom: '0.35rem' }}>
          Active Project
        </div>
        <div className="text-xs font-semibold leading-snug">
          Alkhobar Industrial Complex
        </div>
        <div className="flex items-center gap-1.5 mt-2.5">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#16796E' }} />
          <span className="text-xs font-medium text-accent-teal">System Online</span>
        </div>
      </div>
    </aside>
  );
}
