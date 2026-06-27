import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BookMarked, ChevronDown } from 'lucide-react';
import { subjectsApi } from '../../api';
import { useSubjectStore } from '../../store/subject';
import { useAuthStore } from '../../store/auth';
import type { Subject, PaginatedResponse } from '../../types';

export default function SubjectSwitcher() {
  const { user } = useAuthStore();
  const { activeSubjectId, subjects, setActiveSubject, setSubjects } = useSubjectStore();

  const { data } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    const list: Subject[] = Array.isArray(data)
      ? data
      : (data as PaginatedResponse<Subject>)?.results ?? [];
    if (list.length > 0) {
      setSubjects(list);
      // Auto-select first subject if none selected
      if (!activeSubjectId) {
        setActiveSubject(list[0].id);
      }
    }
  }, [data]);

  if (!subjects.length) return null;
  // Teachers with only one subject: show label only
  if (user?.role === 'teacher' && subjects.length === 1) {
    const s = subjects[0];
    return (
      <div className="mx-3 mb-2 px-3 py-2 rounded-xl bg-surface-700 flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: s.color }} />
        <span className="text-xs font-medium text-primary truncate">{s.name}</span>
      </div>
    );
  }

  const active = subjects.find(s => s.id === activeSubjectId);

  return (
    <div className="mx-3 mb-2 relative">
      <div className="text-[10px] font-display font-semibold text-secondary uppercase tracking-widest px-1 mb-1">
        Subject
      </div>
      <div className="relative">
        <select
          value={activeSubjectId ?? ''}
          onChange={e => setActiveSubject(Number(e.target.value))}
          className="w-full appearance-none bg-surface-700 border border-surface rounded-xl px-3 py-2 pr-8 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500 cursor-pointer"
        >
          {user?.role === 'super_admin' && (
            <option value="">All Subjects</option>
          )}
          {subjects.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-secondary pointer-events-none" />
        {active && (
          <span
            className="absolute left-3 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full pointer-events-none"
            style={{ backgroundColor: active.color, marginLeft: '-8px' }}
          />
        )}
      </div>
    </div>
  );
}
