import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Plus, Search } from 'lucide-react';
import { examsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { formatDate, EXAM_TYPE_LABELS, EXAM_TYPE_COLORS, TERM_LABELS, gradeColor } from '../../utils';
import type { Exam, PaginatedResponse } from '../../types';

export default function ExamsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const { getPage } = useSiteSettingsStore();
  const pageSize = getPage('exams').page_size;

  const { data, isLoading } = useQuery<PaginatedResponse<Exam>>({
    queryKey: ['exams', search, page, pageSize],
    queryFn: () => examsApi.exams({ search: search || undefined, page, page_size: pageSize }).then(r => r.data),
  });
  const exams = data?.results ?? [];

  const handleSearch = (val: string) => { setSearch(val); setPage(1); };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Exams</h1>
          <p className="text-muted mt-0.5">{data?.count ?? 0} total</p>
        </div>
        <Button onClick={() => navigate('/exams/new')} size="sm">
          <Plus size={14} /> <span className="hidden sm:inline">Create</span> Exam
        </Button>
      </div>

      <div className="relative">
        <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
        <input className="input pl-10 w-full" placeholder="Search exams…" value={search} onChange={e => handleSearch(e.target.value)} />
      </div>

      {isLoading ? <LoadingPage /> : exams.length === 0 ? (
        <EmptyState icon={<BookOpen size={36} />} title="No exams found" message="Create your first exam." />
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
                    {exam.is_published ? 'Published' : 'Draft'}
                  </span>
                </div>
              </div>
            ))}
            <Pagination page={page} pageSize={pageSize} total={data?.count ?? 0} onChange={setPage} />
          </div>

          {/* Desktop table */}
          <div className="hidden md:block card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface">
                    {['Title','Type','Term','Date','Max','Avg','Pass Rate','Status',''].map(h => (
                      <th key={h} className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {exams.map(exam => (
                    <tr key={exam.id} className="border-b border-surface hover:bg-surface-800/50 transition-colors cursor-pointer" onClick={() => navigate(`/exams/${exam.id}`)}>
                      <td className="py-3 px-4 font-display font-medium text-primary max-w-[200px] truncate">{exam.title}</td>
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
                      <td className="py-3 px-4"><span className={`badge ${exam.is_published ? 'badge-green' : 'badge-amber'}`}>{exam.is_published ? 'Published' : 'Draft'}</span></td>
                      <td className="py-3 px-4">
                        <button className="text-xs text-azure-400 hover:text-azure-300 font-medium transition-colors"
                          onClick={e => { e.stopPropagation(); navigate(`/exams/${exam.id}/marks`); }}>
                          Marks →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-surface px-4">
              <Pagination page={page} pageSize={pageSize} total={data?.count ?? 0} onChange={setPage} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
