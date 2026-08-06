import {
  LayoutDashboard, Users, Users2, BookOpen, BarChart3, GraduationCap,
  AlertTriangle, Settings, FileText, Upload, School, BookMarked,
  ClipboardList, ClipboardCheck, Layers, Trash2, Bell,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  /** Matches useSiteSettingsStore().getPage(key).enabled — null means always shown. */
  pageKey: string | null;
  adminOnly?: boolean;
}

/**
 * The full set of top-level destinations in the app, shared by the sidebar
 * and the command palette (Ctrl/Cmd+K) so the two never drift out of sync.
 */
export const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard',   pageKey: 'dashboard' },
  { to: '/classrooms', icon: School,          label: 'Classrooms',  pageKey: 'classrooms' },
  { to: '/students',   icon: GraduationCap,   label: 'Students',    pageKey: 'students' },
  { to: '/exams',      icon: BookOpen,        label: 'Exams',       pageKey: 'exams' },
  { to: '/import',     icon: Upload,          label: 'Bulk Import', pageKey: 'import' },
  { to: '/groups',     icon: Users2,          label: 'Peer Groups', pageKey: null },
  { to: '/analytics',  icon: BarChart3,       label: 'Analytics',   pageKey: 'analytics' },
  { to: '/at-risk',    icon: AlertTriangle,   label: 'At Risk',     pageKey: 'at_risk' },
  { to: '/reports',    icon: FileText,        label: 'Reports',     pageKey: 'reports' },
  { to: '/notifications', icon: Bell,         label: 'Notifications', pageKey: null },
  { to: '/exams/pending-review', icon: ClipboardCheck, label: 'Pending Review', pageKey: null, adminOnly: true },
  { to: '/exams/trash', icon: Trash2,         label: 'Exam Trash',  pageKey: null, adminOnly: true },
  { to: '/users',      icon: Users,           label: 'Users',       pageKey: 'users', adminOnly: true },
  { to: '/subjects',   icon: BookMarked,      label: 'Subjects',    pageKey: null, adminOnly: true },
  { to: '/grade-levels', icon: Layers,        label: 'Grade Levels', pageKey: null, adminOnly: true },
  { to: '/audit-log',  icon: ClipboardList,   label: 'Audit Log',   pageKey: null, adminOnly: true },
  { to: '/settings',   icon: Settings,        label: 'Settings',    pageKey: null, adminOnly: true },
];

const RECENTS_KEY = 'mathplatform:recent-pages';
const MAX_RECENTS = 5;

/** Records a top-level nav visit for the command palette's "Recent" section.
 * Only called for exact NAV_ITEMS matches — detail pages (e.g. /students/42)
 * aren't tracked here since they don't have a stable label to show. */
export function recordRecentPage(path: string) {
  const match = NAV_ITEMS.find(n => n.to === path);
  if (!match) return;
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    const existing: string[] = raw ? JSON.parse(raw) : [];
    const next = [path, ...existing.filter(p => p !== path)].slice(0, MAX_RECENTS);
    localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
  } catch { /* localStorage unavailable — recents just won't persist */ }
}

export function getRecentPages(): NavItem[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    const paths: string[] = raw ? JSON.parse(raw) : [];
    return paths
      .map(p => NAV_ITEMS.find(n => n.to === p))
      .filter((n): n is NavItem => !!n);
  } catch {
    return [];
  }
}
