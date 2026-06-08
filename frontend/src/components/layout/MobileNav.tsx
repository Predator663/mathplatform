import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, GraduationCap, BookOpen,
  BarChart3, FileText, School,
} from 'lucide-react';
import { cn } from '../../utils';

const navItems = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Home' },
  { to: '/classrooms', icon: School,          label: 'Classes' },
  { to: '/students',   icon: GraduationCap,   label: 'Students' },
  { to: '/exams',      icon: BookOpen,         label: 'Exams' },
  { to: '/analytics',  icon: BarChart3,        label: 'Analytics' },
  { to: '/reports',    icon: FileText,         label: 'Reports' },
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
