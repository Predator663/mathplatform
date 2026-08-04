import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Shield, TrendingDown, Filter, FileDown } from 'lucide-react';
import toast from 'react-hot-toast';
import { analyticsApi, studentsApi, reportsApi } from '../../api';
import { LoadingPage, EmptyState, Select, Pagination, Button, TiltCard, Reveal } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useSubjectStore } from '../../store/subject';
import { useAuthStore } from '../../store/auth';
import { downloadBlob } from '../../utils';
import type { AtRiskStudent, Classroom, PaginatedResponse, Stream } from '../../types';

type SortBy = 'score_asc' | 'score_desc' | 'name' | 'classroom';

const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: 'score_asc', label: 'Most At-Risk First' },
  { value: 'score_desc', label: 'Least At-Risk First' },
  { value: 'name', label: 'Student Name (A-Z)' },
  { value: 'classroom', label: 'Classroom' },
];

function sortStudents(students: AtRiskStudent[], sortBy: SortBy): AtRiskStudent[] {
  const list = [...students];
  switch (sortBy) {
    case 'score_asc': return list.sort((a, b) => a.recent_average - b.recent_average);
    case 'score_desc': return list.sort((a, b) => b.recent_average - a.recent_average);
    case 'name': return list.sort((a, b) => a.student_name.localeCompare(b.student_name));
    case 'classroom': return list.sort((a, b) => (a.classroom ?? '').localeCompare(b.classroom ?? ''));
    default: return list;
  }
}

export default function AtRiskPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [classroomId, setClassroomId] = useState('');
  const [streamId, setStreamId] = useState('');
  const [threshold, setThreshold] = useState<number>(30);
  const [sortBy, setSortBy] = useState<SortBy>('score_asc');
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const { getPage } = useSiteSettingsStore();
  const { activeSubjectId } = useSubjectStore();
  const pageSize = getPage('at_risk').page_size;
  const isAdmin = user?.role === 'super_admin';

  // Reset classroom filter when subject changes — a classroom that exists for
  // one subject may not apply to another, making the filter misleadingly empty.
  useEffect(() => {
    setClassroomId('');
    setStreamId('');
    setPage(1);
  }, [activeSubjectId]);

  // For teachers: the backend already scopes /classrooms/ to their assigned
  // classrooms. Passing subject_id here further narrows to classrooms where
  // they're assigned to teach that specific subject, so the dropdown only
  // shows relevant options.
  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms', activeSubjectId],
    queryFn: () => studentsApi.classrooms(
      activeSubjectId ? { subject_id: activeSubjectId } : undefined
    ).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  // Streams are per-classroom, so this filter only appears once one classroom is chosen.
  const { data: streamsData } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams-for-at-risk', classroomId],
    queryFn: () => studentsApi.streams({ classroom: classroomId, page_size: 200 }).then(r => r.data),
    enabled: !!classroomId,
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const { data, isLoading } = useQuery<{ at_risk: AtRiskStudent[]; count: number }>({
    queryKey: ['at-risk', classroomId, threshold, activeSubjectId, streamId],
    queryFn: () => analyticsApi.atRisk({
      ...(classroomId ? { classroom_id: classroomId } : {}),
      threshold,
      stream_id: streamId || undefined,
      ...(activeSubjectId ? { subject_id: activeSubjectId } : {}),
    }).then(r => r.data),
  });
  const students = sortStudents(data?.at_risk ?? [], sortBy);
  const paged = students.slice((page - 1) * pageSize, page * pageSize);

  async function handleExportPdf() {
    setExporting(true);
    try {
      const res = await reportsApi.exportAtRiskPdf({
        ...(classroomId ? { classroom_id: classroomId } : {}),
        threshold,
        stream_id: streamId || undefined,
        subject_id: activeSubjectId || undefined,
        sort_by: sortBy,
      });
      downloadBlob(res.data, 'at_risk_students.pdf');
      toast.success('At-risk report downloaded');
    } catch {
      toast.error('Export failed — please try again');
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 md:gap-5">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <AlertTriangle size={20} className="text-rose-400" />
            At-Risk Students
          </h1>
          <p className="text-muted mt-1 text-sm">
            Students flagged for declining performance or below the pass threshold
            {activeSubjectId ? ' in the selected subject' : ''}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data && (
            <div className={`self-start sm:self-end flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-display font-bold ${
              data.count > 0 ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            }`}>
              {data.count > 0 ? <TrendingDown size={14} /> : <Shield size={14} />}
              {data.count} student{data.count !== 1 ? 's' : ''} flagged
            </div>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={handleExportPdf}
            loading={exporting}
            disabled={students.length === 0}
          >
            <FileDown size={13} /> Export PDF
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap items-end gap-3">
        <div className="flex items-center gap-1.5 text-xs text-secondary font-display font-medium uppercase tracking-wider flex-shrink-0">
          <Filter size={12} /> Filters
        </div>
        <div className="flex-1 min-w-[160px]">
          <Select
            label="Classroom"
            options={[
              { value: '', label: isAdmin ? 'All Classrooms' : 'All My Classrooms' },
              ...classrooms.map(c => ({ value: c.id, label: `${c.name}${c.grade_level_name ? ` — ${c.grade_level_name}` : ''}` })),
            ]}
            value={classroomId}
            onChange={e => { setClassroomId(e.target.value); setStreamId(''); setPage(1); }}
          />
        </div>
        {streams.length > 0 && (
          <div className="w-full sm:w-44">
            <Select
              label="Stream"
              options={[{ value: '', label: 'All Streams' }, ...streams.map(s => ({ value: s.id, label: `Stream ${s.name}` }))]}
              value={streamId}
              onChange={e => { setStreamId(e.target.value); setPage(1); }}
            />
          </div>
        )}
        <div className="w-full sm:w-44">
          <Select
            label="Pass Threshold"
            options={[
              { value: 30, label: '30% (O-Level / NECTA)' },
              { value: 40, label: '40% (Primary D)' },
              { value: 50, label: '50% (Custom)' },
            ]}
            value={threshold}
            onChange={e => { setThreshold(Number(e.target.value)); setPage(1); }}
          />
        </div>
        <div className="w-full sm:w-48">
          <Select
            label="Sort By"
            options={SORT_OPTIONS.map(o => ({ value: o.value, label: o.label }))}
            value={sortBy}
            onChange={e => { setSortBy(e.target.value as SortBy); setPage(1); }}
          />
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <LoadingPage />
      ) : students.length === 0 ? (
        <EmptyState
          icon={<Shield size={36} className="text-emerald-400" />}
          title="No at-risk students"
          message={
            activeSubjectId
              ? 'All students in the selected subject are performing above the threshold 🎉'
              : 'All students are performing above the threshold 🎉'
          }
        />
      ) : (
        <>
          {/* Summary strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Flagged', value: data?.count ?? 0, color: '#f43f5e' },
              { label: 'Below Threshold', value: students.filter(s => s.flags.below_threshold).length, color: '#f97316' },
              { label: 'Declining', value: students.filter(s => s.flags.declining).length, color: '#f59e0b' },
              { label: 'Avg Score', value: students.length > 0
                  ? `${Math.round(students.reduce((s, x) => s + x.recent_average, 0) / students.length)}%`
                  : '—', color: '#3b82f6' },
            ].map(({ label, value, color }, i) => (
              <Reveal key={label} index={i} variant="scale">
                <div className="card p-3 border" style={{ borderColor: `${color}30` }}>
                  <p className="text-[10px] text-secondary uppercase tracking-wider font-display">{label}</p>
                  <p className="font-display font-bold text-xl mt-1" style={{ color }}>{value}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            <AnimatePresence mode="popLayout">
              {paged.map((s, idx) => (
                <motion.div
                  key={s.student_id}
                  layout
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.35, delay: Math.min(idx * 0.04, 0.3), ease: [0.16, 1, 0.3, 1] }}
                >
                  <TiltCard
                    className="p-4 cursor-pointer"
                    style={{ borderColor: 'rgba(244,63,94,0.2)' }}
                    onClick={() => navigate(`/analytics/student/${s.student_id}`)}
                  >
                    {/* Student identity */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-rose-500 to-orange-500 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0">
                          {s.student_name.split(' ').map(w => w[0]).join('').slice(0, 2)}
                        </div>
                        <div className="min-w-0">
                          <p className="font-display font-semibold text-primary text-sm leading-tight truncate">{s.student_name}</p>
                          <p className="text-[11px] text-secondary truncate">{s.student_code} · {s.classroom ?? 'No class'}</p>
                        </div>
                      </div>
                      <div className="flex flex-col items-end flex-shrink-0 ml-2">
                        <span className="font-display font-black text-xl text-rose-400">{s.recent_average}%</span>
                        <span className="text-[9px] text-secondary">recent avg</span>
                      </div>
                    </div>

                    {/* Flags */}
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {s.flags.below_threshold && (
                        <span className="badge badge-rose text-[10px] flex items-center gap-1">
                          <AlertTriangle size={9} /> Below {threshold}%
                        </span>
                      )}
                      {s.flags.declining && (
                        <span className="badge badge-amber text-[10px] flex items-center gap-1">
                          <TrendingDown size={9} /> Declining
                        </span>
                      )}
                    </div>

                    {/* Sparkline — oldest→newest left-to-right */}
                    <div className="flex items-end gap-1 h-10 mb-1">
                      {[...s.recent_scores].reverse().map((score, i, arr) => (
                        <motion.div
                          key={i}
                          className="flex-1 flex flex-col items-center gap-0.5"
                          initial={{ scaleY: 0 }}
                          animate={{ scaleY: 1 }}
                          transition={{ duration: 0.4, delay: 0.15 + i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                          style={{ transformOrigin: 'bottom' }}
                        >
                          <div
                            className="w-full rounded-sm transition-all"
                            style={{
                              height: `${Math.max(4, (score / 100) * 36)}px`,
                              backgroundColor: score >= threshold ? '#10b981' : '#f43f5e',
                              opacity: 0.4 + (i / Math.max(1, arr.length - 1)) * 0.6,
                            }}
                          />
                          <span className="text-[8px] font-mono text-secondary leading-none">{score}</span>
                        </motion.div>
                      ))}
                      {s.recent_scores.length === 0 && (
                        <span className="text-xs text-muted">No scores</span>
                      )}
                    </div>

                    <p className="text-[11px] text-rose-400 font-display font-semibold mt-2">View full analytics →</p>
                  </TiltCard>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          <Pagination page={page} pageSize={pageSize} total={students.length} onChange={setPage} />
        </>
      )}
    </div>
  );
}
