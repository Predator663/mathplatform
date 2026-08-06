import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  BookOpen, Plus, Search, CloudOff, SlidersHorizontal, X, Download,
  FileSpreadsheet, ChevronDown, Layers, GraduationCap, Tag, CalendarRange,
} from 'lucide-react';
import { examsApi, studentsApi, subjectsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination, Select, Reveal, StatCard } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useSubjectStore } from '../../store/subject';
import { useAuthStore } from '../../store/auth';
import { useCanManage } from '../../hooks/useCanManage';
import { useCachedExams } from '../../hooks/useOfflineData';
import {
  formatDate, EXAM_TYPE_LABELS, EXAM_TYPE_COLORS, TERM_LABELS, gradeColor, downloadBlob, cn,
} from '../../utils';
import type { Exam, Classroom, Subject, PaginatedResponse } from '../../types';

type GroupBy = 'none' | 'subject' | 'classroom' | 'type';

const SORT_OPTIONS = [
  { value: '-exam_date',  label: 'Newest exam date' },
  { value: 'exam_date',   label: 'Oldest exam date' },
  { value: 'title',       label: 'Title (A–Z)' },
  { value: '-title',      label: 'Title (Z–A)' },
  { value: '-created_at', label: 'Recently added' },
];

const GROUP_OPTIONS: { value: GroupBy; label: string; icon: typeof Layers }[] = [
  { value: 'none',      label: 'No Grouping', icon: Layers },
  { value: 'subject',   label: 'By Subject',   icon: Tag },
  { value: 'classroom', label: 'By Classroom', icon: GraduationCap },
  { value: 'type',      label: 'By Type',      icon: CalendarRange },
];

interface GroupSection { key: string; label: string; color?: string; items: Exam[] }

export default function ExamsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);
  const [groupBy, setGroupBy] = useState<GroupBy>('none');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState<'csv' | 'excel' | null>(null);

  const { getPage } = useSiteSettingsStore();
  const { activeSubjectId } = useSubjectStore();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin';
  // Admins see ALL exams from all teachers — the subject filter is a
  // teacher/student convenience, never a visibility restriction for admin.
  const effectiveSubjectId = isAdmin ? null : activeSubjectId;
  const pageSize = getPage('exams').page_size;
  const canAdd = useCanManage('exams', 'add');

  const classroomFilter = searchParams.get('classroom') ?? '';
  const subjectFilter   = searchParams.get('subject') ?? '';
  const typeFilter      = searchParams.get('exam_type') ?? '';
  const termFilter      = searchParams.get('term') ?? '';
  const yearFilter      = searchParams.get('academic_year') ?? '';
  const statusFilter    = searchParams.get('status') ?? ''; // '', 'published', 'draft'
  const ordering        = searchParams.get('ordering') ?? '-exam_date';

  // A subject picked in the toolbar overrides the sidebar's "active
  // subject" convenience filter, so people can look at a different
  // subject here without switching their global context.
  const subjectParam = subjectFilter || (effectiveSubjectId ? String(effectiveSubjectId) : '');

  const activeFilterCount = [classroomFilter, subjectFilter, typeFilter, termFilter, yearFilter, statusFilter]
    .filter(Boolean).length;

  const setFilter = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set(key, val); else next.delete(key);
    setSearchParams(next, { replace: true });
    setPage(1);
  };
  const clearFilters = () => { setSearchParams({}, { replace: true }); setPage(1); };

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
  });
  const subjects: Subject[] = Array.isArray(subjectsData)
    ? subjectsData : (subjectsData as PaginatedResponse<Subject>)?.results ?? [];

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms', 'for-exam-filter'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  // Grouped view needs enough rows on screen to group meaningfully, so it
  // fetches a larger page and hides normal pagination while active.
  const effectivePageSize = groupBy !== 'none' ? Math.max(pageSize, 200) : pageSize;

  const queryParams: Record<string, unknown> = {
    search: search || undefined,
    page: groupBy !== 'none' ? 1 : page,
    page_size: effectivePageSize,
    ordering,
    ...(subjectParam ? { subject: subjectParam } : {}),
    ...(classroomFilter ? { classrooms: classroomFilter } : {}),
    ...(typeFilter ? { exam_type: typeFilter } : {}),
    ...(termFilter ? { term: termFilter } : {}),
    ...(yearFilter ? { academic_year: yearFilter } : {}),
    ...(statusFilter ? { is_published: statusFilter === 'published' } : {}),
  };

  const { data, isLoading, isError } = useQuery<PaginatedResponse<Exam>>({
    queryKey: ['exams', queryParams],
    queryFn: () => examsApi.exams(queryParams).then(r => r.data),
    retry: 1,
  });

  // Accurate published/draft counts for the stat strip, independent of the
  // status filter and pagination — page_size:1 since only `.count` matters.
  const baseCountParams = { ...queryParams, page: 1, page_size: 1 };
  const { data: publishedCountData } = useQuery<PaginatedResponse<Exam>>({
    queryKey: ['exams-count', 'published', baseCountParams],
    queryFn: () => examsApi.exams({ ...baseCountParams, is_published: true }).then(r => r.data),
  });
  const { data: draftCountData } = useQuery<PaginatedResponse<Exam>>({
    queryKey: ['exams-count', 'draft', baseCountParams],
    queryFn: () => examsApi.exams({ ...baseCountParams, is_published: false }).then(r => r.data),
  });

  // Network list failed (most commonly: offline) — fall back to whatever was
  // last cached locally so the page isn't just blank.
  const cachedExams = useCachedExams();
  const usingOfflineData = isError;

  const offlineFiltered = usingOfflineData
    ? cachedExams
        .filter(e => !subjectParam || String(e.subject) === subjectParam)
        .filter(e => !classroomFilter || e.classrooms.includes(Number(classroomFilter)))
        .filter(e => !typeFilter || e.exam_type === typeFilter)
        .filter(e => !termFilter || e.term === termFilter)
        .filter(e => !yearFilter || e.academic_year === yearFilter)
        .filter(e => !statusFilter || e.is_published === (statusFilter === 'published'))
        .filter(e => !search || e.title.toLowerCase().includes(search.toLowerCase()))
    : [];

  const exams = usingOfflineData ? offlineFiltered : (data?.results ?? []);
  const total = usingOfflineData ? offlineFiltered.length : (data?.count ?? 0);
  const publishedCount = publishedCountData?.count ?? 0;
  const draftCount = draftCountData?.count ?? 0;

  const handleSearch = (val: string) => { setSearch(val); setPage(1); };

  const groupedSections = useMemo<GroupSection[] | null>(() => {
    if (groupBy === 'none') return null;
    const map = new Map<string, GroupSection>();
    const push = (key: string, label: string, color: string | undefined, exam: Exam) => {
      const existing = map.get(key);
      if (existing) existing.items.push(exam);
      else map.set(key, { key, label, color, items: [exam] });
    };
    for (const exam of exams) {
      if (groupBy === 'subject') {
        push(exam.subject ? `s-${exam.subject}` : 'none', exam.subject_name || 'No Subject', exam.subject_color || undefined, exam);
      } else if (groupBy === 'type') {
        push(exam.exam_type, EXAM_TYPE_LABELS[exam.exam_type] ?? exam.exam_type, undefined, exam);
      } else if (groupBy === 'classroom') {
        if (!exam.classroom_names || exam.classroom_names.length === 0) {
          push('none', 'No Classroom Assigned', undefined, exam);
        } else {
          exam.classroom_names.forEach(name => push(`c-${name}`, name, undefined, exam));
        }
      }
    }
    return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [exams, groupBy]);

  const toggleCollapsed = (key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const exportParams: Record<string, unknown> = { ...queryParams };
  delete exportParams.page;
  delete exportParams.page_size;

  const handleExport = async (kind: 'csv' | 'excel') => {
    setExporting(kind);
    try {
      const res = kind === 'csv'
        ? await examsApi.exportExamsCsv(exportParams)
        : await examsApi.exportExamsExcel(exportParams);
      const stamp = new Date().toISOString().slice(0, 10);
      downloadBlob(res.data as Blob, `exams_export_${stamp}.${kind === 'csv' ? 'csv' : 'xlsx'}`);
      toast.success(`${kind === 'csv' ? 'CSV' : 'Excel'} export downloaded`);
    } catch {
      toast.error('Export failed — check your connection and try again.');
    } finally {
      setExporting(null);
    }
  };

  const yearOptions = useMemo(() => {
    const years = new Set<string>();
    exams.forEach(e => e.academic_year && years.add(e.academic_year));
    if (yearFilter) years.add(yearFilter);
    return Array.from(years).sort().reverse();
  }, [exams, yearFilter]);

  const filterPills: { key: string; label: string }[] = [
    subjectFilter && { key: 'subject', label: `Subject: ${subjects.find(s => String(s.id) === subjectFilter)?.name ?? subjectFilter}` },
    classroomFilter && { key: 'classroom', label: `Class: ${classrooms.find(c => String(c.id) === classroomFilter)?.name ?? classroomFilter}` },
    typeFilter && { key: 'exam_type', label: EXAM_TYPE_LABELS[typeFilter as Exam['exam_type']] ?? typeFilter },
    termFilter && { key: 'term', label: TERM_LABELS[termFilter as Exam['term']] ?? termFilter },
    yearFilter && { key: 'academic_year', label: `Year: ${yearFilter}` },
    statusFilter && { key: 'status', label: statusFilter === 'published' ? 'Published' : 'Draft' },
  ].filter(Boolean) as { key: string; label: string }[];

  return (
    <div className="flex flex-col gap-4 md:gap-6 page-enter">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Exams</h1>
          <p className="text-muted mt-0.5">{total} total</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-1">
            <Button
              variant="secondary" size="sm" loading={exporting === 'csv'}
              disabled={exporting !== null || total === 0}
              onClick={() => handleExport('csv')}
            >
              <Download size={13} /> CSV
            </Button>
            <Button
              variant="secondary" size="sm" loading={exporting === 'excel'}
              disabled={exporting !== null || total === 0}
              onClick={() => handleExport('excel')}
            >
              <FileSpreadsheet size={13} /> Excel
            </Button>
          </div>
          {canAdd && (
            <Button onClick={() => navigate('/exams/new')} size="sm">
              <Plus size={14} /> <span className="hidden sm:inline">Create</span> Exam
            </Button>
          )}
        </div>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-2 md:gap-3">
        <StatCard label="Total Exams" value={total} color="blue" icon={<BookOpen size={15} />} />
        <StatCard label="Published" value={publishedCount} color="green" icon={<Tag size={15} />} />
        <StatCard label="Draft / Pending" value={draftCount} color="amber" icon={<CalendarRange size={15} />} />
      </div>

      {/* Search + toolbar */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
            <input className="input pl-10 w-full" placeholder="Search exams by title or description…"
              value={search} onChange={e => handleSearch(e.target.value)} />
          </div>
          <button
            onClick={() => setShowFilters(v => !v)}
            className={cn(
              'relative flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl border text-sm font-display font-medium transition-all flex-shrink-0',
              showFilters || activeFilterCount > 0
                ? 'bg-azure-500/15 border-azure-500/40 text-azure-400'
                : 'bg-surface-900 border-surface text-secondary hover:text-primary'
            )}
          >
            <SlidersHorizontal size={14} />
            <span className="hidden sm:inline">Filters</span>
            {activeFilterCount > 0 && (
              <span className="w-4 h-4 flex items-center justify-center rounded-full bg-azure-500 text-white text-[10px] font-bold">
                {activeFilterCount}
              </span>
            )}
            <ChevronDown size={13} className={cn('transition-transform', showFilters && 'rotate-180')} />
          </button>
        </div>

        {/* Filter panel */}
        <AnimatePresence initial={false}>
          {showFilters && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden"
            >
              <div className="card p-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <Select label="Subject" value={subjectFilter} onChange={e => setFilter('subject', e.target.value)}
                  options={[{ value: '', label: 'All Subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]} />
                <Select label="Classroom" value={classroomFilter} onChange={e => setFilter('classroom', e.target.value)}
                  options={[{ value: '', label: 'All Classrooms' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]} />
                <Select label="Exam Type" value={typeFilter} onChange={e => setFilter('exam_type', e.target.value)}
                  options={[{ value: '', label: 'All Types' }, ...Object.entries(EXAM_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }))]} />
                <Select label="Term" value={termFilter} onChange={e => setFilter('term', e.target.value)}
                  options={[{ value: '', label: 'All Terms' }, ...Object.entries(TERM_LABELS).map(([v, l]) => ({ value: v, label: l }))]} />
                <Select label="Academic Year" value={yearFilter} onChange={e => setFilter('academic_year', e.target.value)}
                  options={[{ value: '', label: 'All Years' }, ...yearOptions.map(y => ({ value: y, label: y }))]} />
                <Select label="Status" value={statusFilter} onChange={e => setFilter('status', e.target.value)}
                  options={[{ value: '', label: 'All Statuses' }, { value: 'published', label: 'Published' }, { value: 'draft', label: isAdmin ? 'Draft' : 'Awaiting Approval' }]} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Active filter pills + sort/group controls */}
        <div className="flex flex-wrap items-center gap-2">
          {filterPills.map(p => (
            <button key={p.key} onClick={() => setFilter(p.key, '')}
              className="badge badge-blue text-[11px] hover:bg-azure-500/25 transition-colors">
              {p.label} <X size={10} />
            </button>
          ))}
          {activeFilterCount > 0 && (
            <button onClick={clearFilters} className="text-xs text-secondary hover:text-rose-400 transition-colors underline underline-offset-2">
              Clear all
            </button>
          )}

          <div className="ml-auto flex items-center gap-2 flex-wrap">
            {/* Group-by segmented control */}
            <div className="flex items-center rounded-xl border border-surface bg-surface-900 p-0.5">
              {GROUP_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setGroupBy(opt.value)}
                  title={opt.label}
                  className={cn(
                    'flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-display font-medium transition-all',
                    groupBy === opt.value ? 'bg-azure-500 text-white' : 'text-secondary hover:text-primary'
                  )}
                >
                  <opt.icon size={12} />
                  <span className="hidden lg:inline">{opt.label}</span>
                </button>
              ))}
            </div>

            <Select
              value={ordering}
              onChange={e => setFilter('ordering', e.target.value)}
              options={SORT_OPTIONS}
              className="!py-2 text-xs min-w-[9.5rem]"
            />
          </div>
        </div>

        {/* Mobile export row */}
        <div className="flex sm:hidden items-center gap-2">
          <Button variant="secondary" size="sm" loading={exporting === 'csv'} disabled={exporting !== null || total === 0}
            onClick={() => handleExport('csv')} className="flex-1 justify-center">
            <Download size={13} /> CSV
          </Button>
          <Button variant="secondary" size="sm" loading={exporting === 'excel'} disabled={exporting !== null || total === 0}
            onClick={() => handleExport('excel')} className="flex-1 justify-center">
            <FileSpreadsheet size={13} /> Excel
          </Button>
        </div>
      </div>

      {usingOfflineData && (
        <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
          <CloudOff size={13} className="flex-shrink-0" />
          Showing data saved on this device — reconnect for the latest exams.
        </div>
      )}

      {groupBy !== 'none' && !isLoading && total > exams.length && (
        <div className="text-xs text-secondary bg-surface-900 border border-surface rounded-xl px-3 py-2">
          Showing {exams.length} of {total} matching exams grouped below — narrow the filters above to see the rest grouped too.
        </div>
      )}

      {isLoading ? <LoadingPage /> : exams.length === 0 ? (
        <EmptyState icon={<BookOpen size={36} />} title="No exams found"
          message={activeFilterCount > 0 || search ? 'No exams match your filters. Try clearing some.' : 'Create your first exam.'} />
      ) : groupedSections ? (
        <div className="flex flex-col gap-3">
          {groupedSections.map((section, gi) => (
            <Reveal key={section.key} index={gi} className="card overflow-hidden">
              <button
                onClick={() => toggleCollapsed(section.key)}
                className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-700/30 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: section.color || 'var(--text-muted)' }}
                  />
                  <span className="font-display font-semibold text-primary truncate">{section.label}</span>
                  <span className="badge text-[10px] flex-shrink-0">{section.items.length}</span>
                </div>
                <ChevronDown size={15} className={cn('text-secondary transition-transform flex-shrink-0', !collapsed.has(section.key) && 'rotate-180')} />
              </button>
              <AnimatePresence initial={false}>
                {!collapsed.has(section.key) && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                    className="overflow-hidden border-t border-surface"
                  >
                    <ExamRows exams={section.items} navigate={navigate} isAdmin={isAdmin} />
                  </motion.div>
                )}
              </AnimatePresence>
            </Reveal>
          ))}
        </div>
      ) : (
        <>
          <ExamRows exams={exams} navigate={navigate} isAdmin={isAdmin} bare />
          {!usingOfflineData && groupBy === 'none' && (
            <div className="card px-4 border-t-0">
              <Pagination page={page} pageSize={pageSize} total={data?.count ?? 0} onChange={setPage} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Subject badge ─────────────────────────────────────────────────────────────
function SubjectBadge({ exam }: { exam: Exam }) {
  if (!exam.subject_name) return <span className="badge text-[10px]">No subject</span>;
  const color = exam.subject_color || '#6366f1';
  return (
    <span
      className="badge text-[10px] border"
      style={{ backgroundColor: `${color}22`, color, borderColor: `${color}44` }}
    >
      {exam.subject_code || exam.subject_name}
    </span>
  );
}

// ── Classroom chips ────────────────────────────────────────────────────────────
function ClassroomChips({ names }: { names?: string[] }) {
  if (!names || names.length === 0) return <span className="text-secondary text-xs">No classroom</span>;
  const shown = names.slice(0, 2);
  const extra = names.length - shown.length;
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map(n => (
        <span key={n} className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-display font-medium bg-surface-700 text-secondary border border-surface">
          {n}
        </span>
      ))}
      {extra > 0 && (
        <span title={names.join(', ')} className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-display font-medium bg-surface-700 text-secondary border border-surface">
          +{extra}
        </span>
      )}
    </div>
  );
}

// ── Shared exam list (mobile cards + desktop table) ─────────────────────────────
function ExamRows({ exams, navigate, isAdmin, bare }: {
  exams: Exam[]; navigate: (path: string) => void; isAdmin: boolean; bare?: boolean;
}) {
  return (
    <>
      {/* Mobile cards */}
      <div className={cn('flex flex-col gap-2 md:hidden', !bare && 'p-2')}>
        {exams.map((exam, i) => (
          <Reveal key={exam.id} index={i}>
            <div className="card-hover p-4" onClick={() => navigate(`/exams/${exam.id}`)}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="font-display font-semibold text-primary text-sm leading-tight">{exam.title}</p>
                <span className={`badge ${EXAM_TYPE_COLORS[exam.exam_type]} text-[10px] flex-shrink-0`}>
                  {EXAM_TYPE_LABELS[exam.exam_type]}
                </span>
              </div>
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <SubjectBadge exam={exam} />
                <ClassroomChips names={exam.classroom_names} />
              </div>
              <div className="flex items-center gap-3 text-xs text-secondary mb-2">
                <span>{TERM_LABELS[exam.term]}</span>
                <span>·</span>
                <span className="font-mono">{formatDate(exam.exam_date)}</span>
                <span>·</span>
                <span>{exam.max_score} marks</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex gap-3 text-xs">
                  {exam.average_score != null && (
                    <span className={gradeColor(exam.average_score)}>Avg: {exam.average_score}%</span>
                  )}
                  {exam.pass_rate != null && (
                    <span className={gradeColor(exam.pass_rate)}>Pass: {exam.pass_rate}%</span>
                  )}
                </div>
                <span className={`badge text-[10px] ${exam.is_published ? 'badge-green' : 'badge-amber'}`}>
                  {exam.is_published ? 'Published' : (isAdmin ? 'Draft' : 'Awaiting Approval')}
                </span>
              </div>
            </div>
          </Reveal>
        ))}
      </div>

      {/* Desktop table */}
      <div className={cn('hidden md:block overflow-hidden', !bare && 'card')}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface">
                {['Title', 'Subject', 'Classrooms', 'Type', 'Term', 'Date', 'Max', 'Avg', 'Pass Rate', 'Status', ''].map(h => (
                  <th key={h} className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {exams.map((exam, i) => (
                <motion.tr
                  key={exam.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.25, delay: Math.min(i * 0.02, 0.3) }}
                  className="border-b border-surface hover:bg-surface-800/50 transition-colors cursor-pointer"
                  onClick={() => navigate(`/exams/${exam.id}`)}
                >
                  <td className="py-3 px-4 font-display font-medium text-primary max-w-[220px] truncate">{exam.title}</td>
                  <td className="py-3 px-4"><SubjectBadge exam={exam} /></td>
                  <td className="py-3 px-4 max-w-[200px]"><ClassroomChips names={exam.classroom_names} /></td>
                  <td className="py-3 px-4"><span className={`badge ${EXAM_TYPE_COLORS[exam.exam_type]}`}>{EXAM_TYPE_LABELS[exam.exam_type]}</span></td>
                  <td className="py-3 px-4 text-secondary text-xs">{TERM_LABELS[exam.term]}</td>
                  <td className="py-3 px-4 text-secondary text-xs font-mono">{formatDate(exam.exam_date)}</td>
                  <td className="py-3 px-4 font-mono text-xs">{exam.max_score}</td>
                  <td className="py-3 px-4">
                    {exam.average_score != null
                      ? <span className={`font-mono text-xs font-bold ${gradeColor(exam.average_score)}`}>{exam.average_score}%</span>
                      : <span className="text-secondary text-xs">—</span>}
                  </td>
                  <td className="py-3 px-4">
                    {exam.pass_rate != null
                      ? <span className={`font-mono text-xs font-bold ${gradeColor(exam.pass_rate)}`}>{exam.pass_rate}%</span>
                      : <span className="text-secondary text-xs">—</span>}
                  </td>
                  <td className="py-3 px-4"><span className={`badge ${exam.is_published ? 'badge-green' : 'badge-amber'}`}>{exam.is_published ? 'Published' : (isAdmin ? 'Draft' : 'Awaiting Approval')}</span></td>
                  <td className="py-3 px-4">
                    <button className="text-xs text-azure-400 hover:text-azure-300 font-medium transition-colors"
                      onClick={e => { e.stopPropagation(); navigate(`/exams/${exam.id}/marks`); }}>
                      Marks →
                    </button>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
