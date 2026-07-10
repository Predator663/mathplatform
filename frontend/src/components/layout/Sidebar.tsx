import { NavLink, useNavigate, Link } from 'react-router-dom';
import {
  LayoutDashboard, Users, BookOpen, BarChart3, GraduationCap,
  AlertTriangle, LogOut, Settings, FileText, Upload, School, X,
  BookMarked, ClipboardList, ClipboardCheck,
} from 'lucide-react';
import { useAuthStore } from '../../store/auth';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { authApi, examsApi } from '../../api';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { cn } from '../../utils';
import ThemeToggle from '../ui/ThemeToggle';
import SubjectSwitcher from './SubjectSwitcher';

const navItems = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard',   pageKey: 'dashboard' },
  { to: '/classrooms', icon: School,           label: 'Classrooms',  pageKey: 'classrooms' },
  { to: '/students',   icon: GraduationCap,    label: 'Students',    pageKey: 'students' },
  { to: '/exams',      icon: BookOpen,          label: 'Exams',       pageKey: 'exams' },
  { to: '/import',     icon: Upload,            label: 'Bulk Import', pageKey: 'import' },
  { to: '/analytics',  icon: BarChart3,         label: 'Analytics',   pageKey: 'analytics' },
  { to: '/at-risk',    icon: AlertTriangle,     label: 'At Risk',     pageKey: 'at_risk' },
  { to: '/reports',    icon: FileText,          label: 'Reports',     pageKey: 'reports' },
];

const adminItems = [
  { to: '/users',     icon: Users,         label: 'Users',      pageKey: 'users' },
  { to: '/subjects',  icon: BookMarked,    label: 'Subjects',   pageKey: null },
  { to: '/audit-log', icon: ClipboardList, label: 'Audit Log',  pageKey: null },
  { to: '/settings',  icon: Settings,      label: 'Settings',   pageKey: null },
];

interface SidebarProps { onClose?: () => void; }

export default function Sidebar({ onClose }: SidebarProps) {
  const { user, clearAuth, refreshToken } = useAuthStore();
  const { settings, getPage } = useSiteSettingsStore();
  const navigate = useNavigate();
  const isAdmin = user?.role === 'super_admin';

  // Live pending-review count badge — only fetched for admins.
  const { data: pendingData } = useQuery({
    queryKey: ['exams-pending'],
    queryFn: () => examsApi.pendingReview().then(r => r.data),
    enabled: isAdmin,
    refetchInterval: 60_000, // refresh every minute
  });
  const pendingCount: number = (pendingData as { count?: number })?.count ?? 0;

  const handleLogout = async () => {
    try { if (refreshToken) await authApi.logout(refreshToken); } catch { /* ignore */ }
    clearAuth(); navigate('/login');
    toast.success('Logged out');
  };

  const navLink = (to: string, Icon: React.ElementType, label: string, pageKey: string | null, badge?: number) => {
    if (pageKey && !getPage(pageKey).enabled) return null;
    return (
      <NavLink
        key={to} to={to}
        className={({ isActive }) => cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-body font-medium transition-all duration-150',
          isActive ? 'bg-azure-500/15 text-azure-400' : 'text-secondary hover:text-primary hover:bg-surface-700'
        )}
      >
        <Icon size={16} className="flex-shrink-0" />
        <span className="truncate flex-1">{label}</span>
        {badge != null && badge > 0 && (
          <span className="ml-auto min-w-[18px] h-[18px] px-1 rounded-full bg-amber-500 text-[10px] font-bold text-white flex items-center justify-center flex-shrink-0">
            {badge > 99 ? '99+' : badge}
          </span>
        )}
      </NavLink>
    );
  };

  const logoLetter = settings.logo_letter || 'Σ';
  const platformName = settings.platform_name || 'MathPlatform';
  const platformSubtitle = settings.platform_subtitle || 'Tanzania';

  return (
    <aside className="w-60 h-screen bg-surface-900 border-r border-surface flex flex-col" style={{borderColor: 'var(--border)'}}>
      {/* Logo */}
      <div className="px-5 py-4 border-b border-surface flex items-center justify-between" style={{borderColor: 'var(--border)'}}>
        <div className="flex items-center gap-2.5">
          {settings.logo_url ? (
            <img
              src={settings.logo_url}
              alt={platformName}
              className="w-8 h-8 rounded-lg object-contain flex-shrink-0"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          ) : (
            <div className="w-8 h-8 bg-azure-500 rounded-lg flex items-center justify-center flex-shrink-0">
              <span className="font-display font-black text-sm text-white">{logoLetter}</span>
            </div>
          )}
          <div>
            <p className="font-display font-bold text-sm text-primary leading-tight">{platformName}</p>
            <p className="text-[10px] text-secondary uppercase tracking-widest">{platformSubtitle}</p>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-secondary hover:text-primary transition-colors p-1 lg:hidden">
            <X size={18} />
          </button>
        )}
      </div>

      {/* Subject Switcher */}
      <div className="pt-2">
        <SubjectSwitcher />
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-3 flex flex-col gap-0.5 overflow-y-auto">
        {navItems.map(({ to, icon: Icon, label, pageKey }) => navLink(to, Icon, label, pageKey))}

        {isAdmin && (
          <>
            <div className="my-2 border-t border-surface" style={{borderColor: 'var(--border)'}} />
            <p className="px-3 mb-1 text-[10px] font-display font-semibold text-secondary uppercase tracking-widest">Admin</p>
            {navLink('/exams/pending-review', ClipboardCheck, 'Pending Review', null, pendingCount)}
            {adminItems.map(({ to, icon: Icon, label, pageKey }) => navLink(to, Icon, label, pageKey))}
          </>
        )}
      </nav>

      {/* Theme + User */}
      <div className="px-3 py-3 border-t border-surface flex flex-col gap-2">
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-xs font-display font-semibold uppercase tracking-widest text-secondary">Theme</span>
          <ThemeToggle />
        </div>
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-surface-700">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
            {user?.first_name?.[0]}{user?.last_name?.[0]}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-display font-medium text-primary truncate">{user?.full_name}</p>
            <p className="text-[10px] text-secondary capitalize">{user?.role?.replace('_', ' ')}</p>
          </div>
          <button onClick={handleLogout} className="text-secondary hover:text-rose-400 transition-colors flex-shrink-0" title="Logout">
            <LogOut size={15} />
          </button>
        </div>
        <div className="flex items-center justify-center gap-2 px-2 pt-1 flex-wrap">
          <Link to="/about" className="text-[10px] text-secondary hover:text-primary transition-colors">About</Link>
          <span className="text-[10px] text-secondary">·</span>
          <Link to="/privacy-policy" className="text-[10px] text-secondary hover:text-primary transition-colors">Privacy</Link>
          <span className="text-[10px] text-secondary">·</span>
          <Link to="/terms-of-use" className="text-[10px] text-secondary hover:text-primary transition-colors">Terms</Link>
        </div>
      </div>
    </aside>
  );
}
