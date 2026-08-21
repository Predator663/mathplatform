import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, BookOpen, CalendarCheck, Users2, BarChart3,
} from 'lucide-react';
import { cn } from '../../utils';

// Curated for daily use on a small screen — the full nav (Classrooms,
// Students, Reports, Admin, etc.) is always one tap away via the hamburger
// menu, which opens the same grouped Sidebar used on desktop. This bar is
// deliberately short: the things a teacher opens most on their phone
// (marking exams, entering quiz marks, checking a group, glancing at
// analytics), not everything the platform can do.
const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Home' },
  { to: '/exams',     icon: BookOpen,         label: 'Exams' },
  { to: '/quizzes',   icon: CalendarCheck,    label: 'Quizzes' },
  { to: '/groups',    icon: Users2,           label: 'Groups' },
  { to: '/analytics', icon: BarChart3,        label: 'Analytics' },
];

export default function MobileNav() {
  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 backdrop-blur-md border-t pb-safe flex-shrink-0"
      style={{backgroundColor: 'var(--bg-900)', borderColor: 'var(--border)'}}>
      <div className="flex items-stretch overflow-x-auto no-scrollbar">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => cn(
              'flex flex-col items-center justify-center gap-0.5 px-3 py-2.5 min-w-[64px] flex-1 text-center transition-colors',
              isActive ? 'text-azure-400' : 'text-secondary hover:text-primary active:text-primary'
            )}
          >
            <Icon size={20} strokeWidth={1.8} />
            <span className="text-[10px] font-display font-semibold whitespace-nowrap">{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
