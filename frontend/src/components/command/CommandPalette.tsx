import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Search, CornerDownLeft, ArrowUp, ArrowDown, Sparkles, Clock, Plus,
  GraduationCap, BookOpen, School, Moon, Sun, Command,
} from 'lucide-react';
import { studentsApi, examsApi } from '../../api';
import { useAuthStore } from '../../store/auth';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useThemeStore } from '../../store/theme';
import { useCanManage } from '../../hooks/useCanManage';
import { NAV_ITEMS, getRecentPages, recordRecentPage } from '../../lib/commandNav';
import { EXAM_TYPE_LABELS, formatDate, cn } from '../../utils';
import type { StudentProfile, Exam, Classroom, PaginatedResponse } from '../../types';

type ResultItem = {
  key: string;
  icon: typeof Search;
  label: string;
  sub?: string;
  group: string;
  onSelect: () => void;
  accent?: string;
};

/** Small debounce — avoids firing a search request on every keystroke. */
function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { user } = useAuthStore();
  const { getPage } = useSiteSettingsStore();
  const { theme, toggleTheme } = useThemeStore();
  const isAdmin = user?.role === 'super_admin';
  const canAddStudent  = useCanManage('students', 'add');
  const canAddExam     = useCanManage('exams', 'add');
  const canAddClassroom = useCanManage('classrooms', 'add');

  const debouncedQuery = useDebounced(query, 250);
  const searching = debouncedQuery.trim().length >= 2;

  // ── Global open/close shortcut ──────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(o => !o);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  const go = (path: string) => {
    recordRecentPage(path);
    navigate(path);
    setOpen(false);
  };

  // ── Live entity search (students / exams / classrooms) ─────────────────
  const { data: studentResults } = useQuery<PaginatedResponse<StudentProfile> | StudentProfile[]>({
    queryKey: ['cmdk-students', debouncedQuery],
    queryFn: () => studentsApi.students({ search: debouncedQuery, page_size: 5 }).then(r => r.data),
    enabled: open && searching,
  });
  const { data: examResults } = useQuery<PaginatedResponse<Exam> | Exam[]>({
    queryKey: ['cmdk-exams', debouncedQuery],
    queryFn: () => examsApi.exams({ search: debouncedQuery, page_size: 5 }).then(r => r.data),
    enabled: open && searching,
  });
  const { data: classroomResults } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['cmdk-classrooms', debouncedQuery],
    queryFn: () => studentsApi.classrooms({ search: debouncedQuery, page_size: 5 }).then(r => r.data),
    enabled: open && searching,
  });

  const asArray = <T,>(d?: PaginatedResponse<T> | T[]): T[] =>
    Array.isArray(d) ? d : d?.results ?? [];

  // ── Build the flat, ordered list of everything currently on screen ─────
  const sections = useMemo(() => {
    const q = query.trim().toLowerCase();
    const groups: { title: string; items: ResultItem[] }[] = [];

    if (!searching) {
      // Quick actions
      const actions: ResultItem[] = [];
      if (canAddExam) actions.push({
        key: 'action-exam', icon: Plus, label: 'Create Exam', group: 'Quick Actions',
        onSelect: () => go('/exams/new'), accent: 'text-azure-400',
      });
      if (canAddStudent) actions.push({
        key: 'action-student', icon: Plus, label: 'Add Student', group: 'Quick Actions',
        onSelect: () => go('/students/new'), accent: 'text-emerald-400',
      });
      if (canAddClassroom) actions.push({
        key: 'action-classroom', icon: Plus, label: 'New Classroom', group: 'Quick Actions',
        onSelect: () => go('/classrooms/new'), accent: 'text-violet-400',
      });
      actions.push({
        key: 'action-theme', icon: theme === 'dark' ? Sun : Moon, group: 'Quick Actions',
        label: theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode',
        onSelect: () => { toggleTheme(); setOpen(false); },
      });
      if (actions.length) groups.push({ title: 'Quick Actions', items: actions });

      // Recently visited
      const recents = getRecentPages();
      if (recents.length) {
        groups.push({
          title: 'Recent',
          items: recents.map(r => ({
            key: `recent-${r.to}`, icon: Clock, label: r.label, group: 'Recent',
            onSelect: () => go(r.to),
          })),
        });
      }

      // All pages
      groups.push({
        title: 'Go to',
        items: NAV_ITEMS
          .filter(n => (!n.adminOnly || isAdmin) && (!n.pageKey || getPage(n.pageKey).enabled))
          .map(n => ({ key: `page-${n.to}`, icon: n.icon, label: n.label, group: 'Go to', onSelect: () => go(n.to) })),
      });
    } else {
      // Matching pages
      const pageMatches = NAV_ITEMS.filter(n =>
        (!n.adminOnly || isAdmin) && (!n.pageKey || getPage(n.pageKey).enabled) &&
        n.label.toLowerCase().includes(q)
      );
      if (pageMatches.length) {
        groups.push({
          title: 'Pages',
          items: pageMatches.map(n => ({ key: `page-${n.to}`, icon: n.icon, label: n.label, group: 'Pages', onSelect: () => go(n.to) })),
        });
      }

      const students = asArray(studentResults);
      if (students.length) {
        groups.push({
          title: 'Students',
          items: students.map(s => ({
            key: `student-${s.id}`, icon: GraduationCap, group: 'Students',
            label: s.full_name, sub: [s.student_id, s.classroom_name].filter(Boolean).join(' · '),
            onSelect: () => go(`/students/${s.id}`),
          })),
        });
      }

      const exams = asArray(examResults);
      if (exams.length) {
        groups.push({
          title: 'Exams',
          items: exams.map(e => ({
            key: `exam-${e.id}`, icon: BookOpen, group: 'Exams',
            label: e.title,
            sub: [e.subject_name, EXAM_TYPE_LABELS[e.exam_type], formatDate(e.exam_date)].filter(Boolean).join(' · '),
            onSelect: () => go(`/exams/${e.id}`),
          })),
        });
      }

      const classrooms = asArray(classroomResults);
      if (classrooms.length) {
        groups.push({
          title: 'Classrooms',
          items: classrooms.map(c => ({
            key: `classroom-${c.id}`, icon: School, group: 'Classrooms',
            label: c.name, sub: [c.grade_level_name, `${c.student_count} students`].filter(Boolean).join(' · '),
            onSelect: () => go(`/classrooms/${c.id}`),
          })),
        });
      }

      if (!groups.length) {
        groups.push({
          title: 'No results', items: [{
            key: 'no-results', icon: Search, label: `No matches for "${query}"`, group: 'No results',
            onSelect: () => {},
          }],
        });
      }
    }
    return groups;
  }, [query, searching, studentResults, examResults, classroomResults, isAdmin, canAddExam, canAddStudent, canAddClassroom, theme]);

  const flatItems = useMemo(() => sections.flatMap(s => s.items), [sections]);

  useEffect(() => { setActiveIndex(0); }, [query]);

  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${activeIndex}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, flatItems.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      flatItems[activeIndex]?.onSelect();
    }
  };

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[100] flex items-start justify-center pt-[10vh] px-4"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />
            <motion.div
              className="relative w-full max-w-xl card shadow-2xl overflow-hidden flex flex-col max-h-[70vh]"
              initial={{ opacity: 0, y: -12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -12, scale: 0.97 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
              onKeyDown={handleKeyDown}
            >
              {/* Search input */}
              <div className="flex items-center gap-3 px-4 py-3.5 border-b border-surface flex-shrink-0" style={{ borderColor: 'var(--border)' }}>
                <Search size={17} className="text-secondary flex-shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Search students, exams, classrooms, or jump to a page…"
                  className="flex-1 bg-transparent outline-none text-sm text-primary placeholder:text-muted"
                />
                <kbd className="hidden sm:flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-surface-700 text-[10px] text-secondary font-mono flex-shrink-0">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div ref={listRef} className="overflow-y-auto flex-1 py-2">
                {sections.map(section => (
                  <div key={section.title} className="mb-1 last:mb-0">
                    <p className="px-4 pt-2 pb-1 text-[10px] font-display font-semibold text-secondary uppercase tracking-widest">
                      {section.title}
                    </p>
                    {section.items.map(item => {
                      const idx = flatItems.indexOf(item);
                      const isActive = idx === activeIndex;
                      return (
                        <button
                          key={item.key}
                          data-idx={idx}
                          onMouseEnter={() => setActiveIndex(idx)}
                          onClick={item.onSelect}
                          disabled={item.key === 'no-results'}
                          className={cn(
                            'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
                            item.key === 'no-results' ? 'cursor-default' : 'cursor-pointer',
                            isActive && item.key !== 'no-results' ? 'bg-azure-500/12' : ''
                          )}
                        >
                          <item.icon size={15} className={cn('flex-shrink-0', item.accent || 'text-secondary')} />
                          <span className="flex-1 min-w-0">
                            <span className={cn('block text-sm font-display font-medium truncate', item.key === 'no-results' ? 'text-secondary' : 'text-primary')}>
                              {item.label}
                            </span>
                            {item.sub && <span className="block text-xs text-secondary truncate">{item.sub}</span>}
                          </span>
                          {isActive && item.key !== 'no-results' && (
                            <CornerDownLeft size={12} className="text-azure-400 flex-shrink-0" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>

              {/* Footer hints */}
              <div className="flex items-center gap-4 px-4 py-2.5 border-t border-surface flex-shrink-0 text-[10px] text-secondary" style={{ borderColor: 'var(--border)' }}>
                <span className="flex items-center gap-1"><ArrowUp size={10} /><ArrowDown size={10} /> Navigate</span>
                <span className="flex items-center gap-1"><CornerDownLeft size={10} /> Select</span>
                <span className="ml-auto flex items-center gap-1"><Sparkles size={10} /> Command Palette</span>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/** Fires the same synthetic Ctrl/Cmd+K keydown the global listener above
 * listens for — used by any custom trigger button (sidebar, mobile bar). */
export function openCommandPalette() {
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform ?? navigator.userAgent);
  window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: isMac, ctrlKey: !isMac }));
}

/** Discoverable trigger button — drop this in the sidebar / mobile top bar. */
export function CommandPaletteTrigger({ className }: { className?: string }) {
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform ?? navigator.userAgent);
  return (
    <button
      onClick={openCommandPalette}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-xl border text-sm text-secondary hover:text-primary transition-colors w-full',
        'bg-surface-800 border-surface hover:border-azure-500/40',
        className
      )}
      style={{ borderColor: 'var(--border)' }}
    >
      <Search size={14} className="flex-shrink-0" />
      <span className="flex-1 text-left truncate">Search…</span>
      <kbd className="hidden sm:flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-surface-700 text-[10px] font-mono flex-shrink-0">
        {isMac ? <Command size={9} /> : 'Ctrl'}K
      </kbd>
    </button>
  );
}
