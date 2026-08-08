import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { BookOpen, Plus, Search, CloudOff, Download, Trash2, ArrowUp, ArrowDown, ArrowUpDown, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { examsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination, Select } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useSubjectStore } from '../../store/subject';
import { useAuthStore } from '../../store/auth';
import { useCanManage } from '../../hooks/useCanManage';
import { useCachedExams } from '../../hooks/useOfflineData';
import { formatDate, downloadBlob, EXAM_TYPE_LABELS, EXAM_TYPE_COLORS, TERM_LABELS, gradeColor } from '../../utils';
import type { Exam, PaginatedResponse, Classroom, ExamType, TermType } from '../../types';

// Column key -> backend `ordering` field. Kept in sync with
// ExamViewSet.ordering_fields on the backend.
const SORT_COLUMNS: Record<string, string> = {
  title: 'title',
  type: 'exam_type',
  term: 'term',
  year: 'academic_year',
  date: 'exam_date',
  max: 'max_score',
  status: 'is_published',
};

const EXAM_TYPE_OPTIONS = Object.entries(EXAM_TYPE_LABELS).map(([value, label]) => ({ value, label }));
const TERM_OPTIONS = Object.entries(TERM_LABELS).map(([value, label]) => ({ value, label }));

export default function ExamsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState('');
  const [exporting, setExporting] = useState(false);

  const classroomFilter = searchParams.get('classroom') ?? '';
  const yearFilter = searchParams.get('academic_year') ?? '';
  const termFilter = searchParams.get('term') ?? '';
  const typeFilter = searchParams.get('exam_type') ?? '';
  const statusFilter = searchParams.get('is_published') ?? ''; // '', 'true', 'false'

  const { getPage } = useSiteSettingsStore();
  const { activeSubjectId } = useSubjectStore();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin';
  // Admins see ALL exams from all teachers — the subject filter is a
  // teacher/student convenience, never a visibility restriction for admin.
  const effectiveSubjectId = isAdmin ? null : activeSubjectId;
  const pageSize = getPage('exams').page_size;
  const canAdd = useCanManage('exams', 'add');
  const canDelete = useCanManage('exams', 'delete');

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms', 'for-exam-filter'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data: yearsData } = useQuery<string[]>({
    queryKey: ['exam-academic-years'],
    queryFn: () => examsApi.academicYears().then(r => r.data),
  });
  const academicYears = yearsData ?? [];

  const filterParams = {
    search: search || undefined,
    classrooms: classroomFilter || undefined,
    academic_year: yearFilter || undefined,
    term: termFilter || undefined,
    exam_type: typeFilter || undefined,
    is_published: statusFilter || undefined,
    ordering: ordering || undefined,
    ...(effectiveSubjectId ? { subject: effectiveSubjectId } : {}),
  };

  const { data, isLoading, isError } = useQuery<PaginatedResponse<Exam>>({
    queryKey: ['exams', filterParams, page, pageSize],
    queryFn: () => examsApi.exams({ ...filterParams, page, page_size: pageSize }).then(r => r.data),
    retry: 1,
  });

  // Network list failed (most commonly: offline) — fall back to whatever was
  // last cached locally so the page isn't just blank. Search/pagination are
  // done client-side here since the cache holds the full list, not a page.
  const cachedExams = useCachedExams();
  const usingOfflineData = isError;

  const offlineFiltered = usingOfflineData
    ? cachedExams.filter(e =>
        !effectiveSubjectId || e.subject === effectiveSubjectId
      ).filter(e =>
        !search || e.title.toLowerCase().includes(search.toLowerCase())
      )
    : [];

  const exams = usingOfflineData ? offlineFiltered : (data?.results ?? []);
  const total = usingOfflineData ? offlineFiltered.length : (data?.count ?? 0);

  const hasActiveFilters = !!(classroomFilter || yearFilter || termFilter || typeFilter || statusFilter);

  const deleteMutation = useMutation({
    mutationFn: (id: number) => examsApi.deleteExam(id),
    onSuccess: () => {
      toast.success('Exam moved to trash.');
      qc.invalidateQueries({ queryKey: ['exams'] });
      qc.invalidateQueries({ queryKey: ['exams-trash'] });
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? 'Failed to delete exam.');
    },
  });

  const handleDelete = (exam: Exam) => {
    if (confirm(`Delete "${exam.title}"? It will move to Trash and can be restored later.`)) {
      deleteMutation.mutate(exam.id);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await examsApi.exportCsv(filterParams);
      downloadBlob(res.data as Blob, 'exams_export.csv');
      toast.success('CSV downloaded');
    } catch {
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  const handleSearch = (val: string) => { setSearch(val); setPage(1); };

  const setFilter = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set(key, val); else next.delete(key);
    setSearchParams(next);
    setPage(1);
  };

  const clearFilters = () => { setSearchParams({}); setPage(1); };

  const handleSort = (columnKey: string) => {
    const field = SORT_COLUMNS[columnKey];
    setOrdering(prev => {
      if (prev === field) return `-${field}`;
      if (prev === `-${field}`) return '';
      return field;
    });
    setPage(1);
  };

  const sortIcon = (columnKey: string) => {
    const field = SORT_COLUMNS[columnKey];
    if (ordering === field) return <ArrowUp size={12} />;
    if (ordering === `-${field}`) return <ArrowDown size={12} />;
    return <ArrowUpDown size={12} className="opacity-30" />;
  };

  const sortableHeader = (columnKey: string, label: string) => (
    <button
      className="flex items-center gap-1 text-xs font-display font-semibold text-secondary uppercase tracking-widest hover:text-primary transition-colors"
      onClick={() => handleSort(columnKey)}
    >
      {label} {sortIcon(columnKey)}
    </button>
  );

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Exams</h1>
          <p className="text-muted mt-0.5">{total} total</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={handleExport} loading={exporting} disabled={total === 0}>
            <Download size={14} /> <span className="hidden sm:inline">Export</span>
          </Button>
          {canAdd && (
            <Button onClick={() => navigate('/exams/new')} size="sm">
              <Plus size={14} /> <span className="hidden sm:inline">Create</span> Exam
            </Button>
          )}
        </div>
      </div>

      <div className="relative">
        <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
        <input className="input pl-10 w-full" placeholder="Search exams…" value={search} onChange={e => handleSearch(e.target.value)} />
      </div>

      <div className="card p-3 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[160px]">
          <Select
            label="Classroom"
            options={[{ value: '', label: 'All classrooms' }, ...classrooms.map(c => ({ value: c.id, label: `${c.name}${c.grade_level_name ? ` — ${c.grade_level_name}` : ''}` }))]}
            value={classroomFilter}
            onChange={e => setFilter('classroom', e.target.value)}
          />
        </div>
        <div className="w-36">
          <Select
            label="Academic Year"
            options={[{ value: '', label: 'All years' }, ...academicYears.map(y => ({ value: y, label: y }))]}
            value={yearFilter}
            onChange={e => setFilter('academic_year', e.target.value)}
          />
        </div>
        <div className="w-40">
          <Select
            label="Term"
            options={[{ value: '', label: 'All terms' }, ...TERM_OPTIONS]}
            value={termFilter}
            onChange={e => setFilter('term', e.target.value as TermType | '')}
          />
        </div>
        <div className="w-48">
          <Select
            label="Exam Type"
            options={[{ value: '', label: 'All types' }, ...EXAM_TYPE_OPTIONS]}
            value={typeFilter}
            onChange={e => setFilter('exam_type', e.target.value as ExamType | '')}
          />
        </div>
        <div className="w-36">
          <Select
            label="Status"
            options={[{ value: '', label: 'All statuses' }, { value: 'true', label: 'Published' }, { value: 'false', label: isAdmin ? 'Draft' : 'Awaiting Approval' }]}
            value={statusFilter}
            onChange={e => setFilter('is_published', e.target.value)}
          />
        </div>
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            <X size={13} /> Clear filters
          </Button>
        )}
      </div>

      {usingOfflineData && (
        <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
          <CloudOff size={13} className="flex-shrink-0" />
          Showing data saved on this device — reconnect for the latest exams.
        </div>
      )}

      {isLoading ? <LoadingPage /> : exams.length === 0 ? (
        <EmptyState
          icon={<BookOpen size={36} />}
          title="No exams found"
          message={hasActiveFilters || search ? 'Try adjusting your filters or search.' : 'Create your first exam.'}
        />
      ) : (
        <>
          {/* Mobile cards */}
          <div className="flex flex-col gap-2 md:hidden">
            {exams.map(exam => (
              <div key={exam.id} className="card-hover p-4" onClick={() => navigate(`/exams/${exam.id}`)}>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className="font-display font-semibold text-primary text-sm leading-tight">{exam.title}</p>
                  <span className={`badge ${EXAM_TYPE_COLORS[exam.exam_type]} text-[10px] flex-shrink-0`}>
                    {EXAM_TYPE_LABELS[exam.exam_type]}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-secondary mb-2">
                  <span>{TERM_LABELS[exam.term]}</span>
                  <span>·</span>
                  <span>{exam.academic_year}</span>
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
                  <div className="flex items-center gap-2">
                    <span className={`badge text-[10px] ${exam.is_published ? 'badge-green' : 'badge-amber'}`}>
                      {exam.is_published ? 'Published' : (isAdmin ? 'Draft' : 'Awaiting Approval')}
                    </span>
                    {canDelete && (
                      <button
                        className="text-rose-400 hover:text-rose-300 transition-colors p-1"
                        onClick={e => { e.stopPropagation(); handleDelete(exam); }}
                        title="Delete exam"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {!usingOfflineData && <Pagination page={page} pageSize={pageSize} total={data?.count ?? 0} onChange={setPage} />}
          </div>

          {/* Desktop table */}
          <div className="hidden md:block card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface">
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('title', 'Title')}</th>
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('type', 'Type')}</th>
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('term', 'Term')}</th>
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('year', 'Year')}</th>
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('date', 'Date')}</th>
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('max', 'Max')}</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">Avg</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">Pass Rate</th>
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('status', 'Status')}</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap"></th>
                  </tr>
                </thead>
                <tbody>
                  {exams.map(exam => (
                    <tr key={exam.id} className="border-b border-surface hover:bg-surface-800/50 transition-colors cursor-pointer" onClick={() => navigate(`/exams/${exam.id}`)}>
                      <td className="py-3 px-4 font-display font-medium text-primary max-w-[200px] truncate">{exam.title}</td>
                      <td className="py-3 px-4"><span className={`badge ${EXAM_TYPE_COLORS[exam.exam_type]}`}>{EXAM_TYPE_LABELS[exam.exam_type]}</span></td>
                      <td className="py-3 px-4 text-secondary text-xs">{TERM_LABELS[exam.term]}</td>
                      <td className="py-3 px-4 text-secondary text-xs font-mono">{exam.academic_year}</td>
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
                        <div className="flex items-center gap-3">
                          <button className="text-xs text-azure-400 hover:text-azure-300 font-medium transition-colors"
                            onClick={e => { e.stopPropagation(); navigate(`/exams/${exam.id}/marks`); }}>
                            Marks →
                          </button>
                          {canDelete && (
                            <button
                              className="text-rose-400 hover:text-rose-300 transition-colors"
                              onClick={e => { e.stopPropagation(); handleDelete(exam); }}
                              title="Delete exam"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-surface px-4">
              {!usingOfflineData && <Pagination page={page} pageSize={pageSize} total={data?.count ?? 0} onChange={setPage} />}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
