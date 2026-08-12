import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ClipboardList, Plus, Search, Download, BarChart3, X, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import toast from 'react-hot-toast';
import { quizzesApi, studentsApi, subjectsApi, examsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination, Select } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useCanManage } from '../../hooks/useCanManage';
import { formatDate, downloadBlob, TERM_LABELS, gradeColor } from '../../utils';
import type { DailyQuiz, PaginatedResponse, Classroom, Subject, MathTopic } from '../../types';

const SORT_COLUMNS: Record<string, string> = {
  title: 'title', date: 'date', max: 'max_score',
};

const TERM_OPTIONS = Object.entries(TERM_LABELS).map(([value, label]) => ({ value, label }));

export default function QuizzesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState('-date');
  const [exporting, setExporting] = useState(false);

  const classroomFilter = searchParams.get('classroom') ?? '';
  const subjectFilter = searchParams.get('subject') ?? '';
  const topicFilter = searchParams.get('topic') ?? '';
  const yearFilter = searchParams.get('academic_year') ?? '';
  const termFilter = searchParams.get('term') ?? '';

  const { getPage } = useSiteSettingsStore();
  const pageSize = getPage('quizzes').page_size;
  const canAdd = useCanManage('quizzes', 'add');

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms', 'for-quiz-filter'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData) ? classroomsData : classroomsData?.results ?? [];

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
  });
  const subjects: Subject[] = Array.isArray(subjectsData) ? subjectsData : subjectsData?.results ?? [];

  const { data: topicsData } = useQuery<{ results?: MathTopic[] } | MathTopic[]>({
    queryKey: ['topics', subjectFilter],
    queryFn: () => examsApi.topics(subjectFilter ? { subject: subjectFilter } : {}).then(r => r.data),
  });
  const topics: MathTopic[] = Array.isArray(topicsData) ? topicsData : topicsData?.results ?? [];

  const { data: yearsData } = useQuery<string[]>({
    queryKey: ['quiz-academic-years'],
    queryFn: () => quizzesApi.academicYears().then(r => r.data),
  });
  const academicYears = yearsData ?? [];

  const filterParams = {
    search: search || undefined,
    classroom: classroomFilter || undefined,
    subject: subjectFilter || undefined,
    topic: topicFilter || undefined,
    academic_year: yearFilter || undefined,
    term: termFilter || undefined,
    ordering: ordering || undefined,
  };

  const { data, isLoading } = useQuery<PaginatedResponse<DailyQuiz>>({
    queryKey: ['quizzes', filterParams, page, pageSize],
    queryFn: () => quizzesApi.quizzes({ ...filterParams, page, page_size: pageSize }).then(r => r.data),
  });

  const quizzes = data?.results ?? [];
  const total = data?.count ?? 0;
  const hasActiveFilters = !!(classroomFilter || subjectFilter || topicFilter || yearFilter || termFilter);

  const setFilter = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set(key, val); else next.delete(key);
    if (key === 'subject') next.delete('topic'); // topic list depends on subject
    setSearchParams(next);
    setPage(1);
  };
  const clearFilters = () => { setSearchParams({}); setPage(1); };
  const handleSearch = (val: string) => { setSearch(val); setPage(1); };

  const handleSort = (columnKey: string) => {
    const field = SORT_COLUMNS[columnKey];
    setOrdering(prev => (prev === field ? `-${field}` : prev === `-${field}` ? '' : field));
    setPage(1);
  };
  const sortIcon = (columnKey: string) => {
    const field = SORT_COLUMNS[columnKey];
    if (ordering === field) return <ArrowUp size={12} />;
    if (ordering === `-${field}`) return <ArrowDown size={12} />;
    return <ArrowUpDown size={12} className="opacity-30" />;
  };
  const sortableHeader = (columnKey: string, label: string) => (
    <button className="flex items-center gap-1 text-xs font-display font-semibold text-secondary uppercase tracking-widest hover:text-primary transition-colors"
      onClick={() => handleSort(columnKey)}>
      {label} {sortIcon(columnKey)}
    </button>
  );

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await quizzesApi.exportCsv(filterParams);
      downloadBlob(res.data as Blob, 'daily_quizzes_export.csv');
      toast.success('CSV downloaded');
    } catch {
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Daily Quizzes</h1>
          <p className="text-muted mt-0.5">{total} total</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={handleExport} loading={exporting} disabled={total === 0}>
            <Download size={14} /> <span className="hidden sm:inline">Export</span>
          </Button>
          {canAdd && (
            <Button onClick={() => navigate('/quizzes/new')} size="sm">
              <Plus size={14} /> <span className="hidden sm:inline">New</span> Quiz
            </Button>
          )}
        </div>
      </div>

      <div className="relative">
        <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
        <input className="input pl-10 w-full" placeholder="Search quizzes…" value={search} onChange={e => handleSearch(e.target.value)} />
      </div>

      <div className="card p-3 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[160px]">
          <Select label="Classroom"
            options={[{ value: '', label: 'All classrooms' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]}
            value={classroomFilter} onChange={e => setFilter('classroom', e.target.value)} />
        </div>
        <div className="w-44">
          <Select label="Subject"
            options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
            value={subjectFilter} onChange={e => setFilter('subject', e.target.value)} />
        </div>
        <div className="w-44">
          <Select label="Topic"
            options={[{ value: '', label: 'All topics' }, ...topics.map(t => ({ value: t.id, label: t.name }))]}
            value={topicFilter} onChange={e => setFilter('topic', e.target.value)} />
        </div>
        <div className="w-36">
          <Select label="Academic Year"
            options={[{ value: '', label: 'All years' }, ...academicYears.map(y => ({ value: y, label: y }))]}
            value={yearFilter} onChange={e => setFilter('academic_year', e.target.value)} />
        </div>
        <div className="w-40">
          <Select label="Term"
            options={[{ value: '', label: 'All terms' }, ...TERM_OPTIONS]}
            value={termFilter} onChange={e => setFilter('term', e.target.value)} />
        </div>
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}><X size={13} /> Clear filters</Button>
        )}
        {classroomFilter && (
          <Button variant="secondary" size="sm" onClick={() => navigate(`/quizzes/analytics/${classroomFilter}`)}>
            <BarChart3 size={14} /> Class Analytics
          </Button>
        )}
      </div>

      {isLoading ? <LoadingPage /> : quizzes.length === 0 ? (
        <EmptyState icon={<ClipboardList size={36} />} title="No quizzes found"
          message={hasActiveFilters || search ? 'Try adjusting your filters or search.' : 'Create the first daily quiz to get started.'} />
      ) : (
        <>
          {/* Mobile cards */}
          <div className="flex flex-col gap-2 md:hidden">
            {quizzes.map(quiz => (
              <div key={quiz.id} className="card-hover p-4" onClick={() => navigate(`/quizzes/${quiz.id}/marks`)}>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className="font-display font-semibold text-primary text-sm leading-tight">{quiz.display_title}</p>
                  <span className="badge text-[10px] flex-shrink-0">{quiz.classroom_name}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-secondary mb-2">
                  <span className="font-mono">{formatDate(quiz.date)}</span>
                  <span>·</span>
                  <span>{quiz.subject_name}</span>
                  <span>·</span>
                  <span>{quiz.max_score} marks</span>
                </div>
                <div className="flex gap-3 text-xs">
                  {quiz.average_score != null && <span className={gradeColor(quiz.average_score)}>Avg: {quiz.average_score}%</span>}
                  {quiz.pass_rate != null && <span className={gradeColor(quiz.pass_rate)}>Pass: {quiz.pass_rate}%</span>}
                  {quiz.score_count === 0 && <span className="text-amber-400">No marks entered</span>}
                </div>
              </div>
            ))}
            <Pagination page={page} pageSize={pageSize} total={total} onChange={setPage} />
          </div>

          {/* Desktop table */}
          <div className="hidden md:block card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface">
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('date', 'Date')}</th>
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('title', 'Title')}</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">Classroom</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">Subject</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">Topic</th>
                    <th className="text-left py-3 px-4 whitespace-nowrap">{sortableHeader('max', 'Max')}</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">Avg</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">Pass Rate</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap"></th>
                  </tr>
                </thead>
                <tbody>
                  {quizzes.map(quiz => (
                    <tr key={quiz.id} className="border-b border-surface hover:bg-surface-800/50 transition-colors cursor-pointer"
                      onClick={() => navigate(`/quizzes/${quiz.id}/marks`)}>
                      <td className="py-3 px-4 text-secondary text-xs font-mono">{formatDate(quiz.date)}</td>
                      <td className="py-3 px-4 font-display font-medium text-primary max-w-[200px] truncate">{quiz.display_title}</td>
                      <td className="py-3 px-4 text-secondary text-xs">{quiz.classroom_name}</td>
                      <td className="py-3 px-4 text-secondary text-xs">{quiz.subject_name}</td>
                      <td className="py-3 px-4 text-secondary text-xs">{quiz.topic_name ?? '—'}</td>
                      <td className="py-3 px-4 font-mono text-xs">{quiz.max_score}</td>
                      <td className="py-3 px-4">
                        {quiz.average_score != null
                          ? <span className={`font-mono text-xs font-bold ${gradeColor(quiz.average_score)}`}>{quiz.average_score}%</span>
                          : <span className="text-secondary text-xs">—</span>}
                      </td>
                      <td className="py-3 px-4">
                        {quiz.pass_rate != null
                          ? <span className={`font-mono text-xs font-bold ${gradeColor(quiz.pass_rate)}`}>{quiz.pass_rate}%</span>
                          : <span className="text-secondary text-xs">—</span>}
                      </td>
                      <td className="py-3 px-4">
                        <button className="text-xs text-azure-400 hover:text-azure-300 font-medium transition-colors"
                          onClick={e => { e.stopPropagation(); navigate(`/quizzes/${quiz.id}/marks`); }}>
                          Marks →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-surface px-4">
              <Pagination page={page} pageSize={pageSize} total={total} onChange={setPage} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
