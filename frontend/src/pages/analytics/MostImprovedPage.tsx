import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, Trophy, Filter, Medal } from 'lucide-react';
import { analyticsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Select, Pagination, TiltCard, Reveal } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useSubjectStore } from '../../store/subject';
import { useAuthStore } from '../../store/auth';
import type { MostImprovedStudent, Classroom, PaginatedResponse, Stream } from '../../types';

const MEDAL_COLORS = ['#f59e0b', '#94a3b8', '#c2703d']; // gold, silver, bronze

type SortBy = 'gain_desc' | 'gain_asc' | 'name' | 'classroom';
const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: 'gain_desc', label: 'Biggest Gain First' },
  { value: 'gain_asc', label: 'Smallest Gain First' },
  { value: 'name', label: 'Student Name (A-Z)' },
  { value: 'classroom', label: 'Classroom' },
];
function sortStudents(students: MostImprovedStudent[], sortBy: SortBy): MostImprovedStudent[] {
  const list = [...students];
  switch (sortBy) {
    case 'gain_desc': return list.sort((a, b) => b.delta - a.delta);
    case 'gain_asc': return list.sort((a, b) => a.delta - b.delta);
    case 'name': return list.sort((a, b) => a.student_name.localeCompare(b.student_name));
    case 'classroom': return list.sort((a, b) => (a.classroom ?? '').localeCompare(b.classroom ?? ''));
    default: return list;
  }
}

export default function MostImprovedPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [classroomId, setClassroomId] = useState('');
  const [streamId, setStreamId] = useState('');
  const [minExams, setMinExams] = useState<number>(2);
  const [sortBy, setSortBy] = useState<SortBy>('gain_desc');
  const [page, setPage] = useState(1);
  const { getPage } = useSiteSettingsStore();
  const { activeSubjectId } = useSubjectStore();
  const pageSize = getPage('most_improved').page_size;
  const isAdmin = user?.role === 'super_admin';

  useEffect(() => {
    setClassroomId('');
    setStreamId('');
    setPage(1);
  }, [activeSubjectId]);

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
    queryKey: ['streams-for-most-improved', classroomId],
    queryFn: () => studentsApi.streams({ classroom: classroomId, page_size: 200 }).then(r => r.data),
    enabled: !!classroomId,
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const { data, isLoading } = useQuery<{ most_improved: MostImprovedStudent[]; count: number }>({
    queryKey: ['most-improved', classroomId, minExams, activeSubjectId, streamId],
    queryFn: () => analyticsApi.mostImproved({
      ...(classroomId ? { classroom_id: classroomId } : {}),
      min_exams: minExams,
      stream_id: streamId || undefined,
      ...(activeSubjectId ? { subject_id: activeSubjectId } : {}),
    }).then(r => r.data),
  });
  const students = sortStudents(data?.most_improved ?? [], sortBy);
  const paged = students.slice((page - 1) * pageSize, page * pageSize);
  const gaining = students.filter(s => s.delta > 0).length;
  const slipping = students.filter(s => s.delta < 0).length;
  const topGain = [...students].sort((a, b) => b.delta - a.delta)[0];

  return (
    <div className="flex flex-col gap-4 md:gap-5">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <TrendingUp size={20} className="text-emerald-400" />
            Most Improved
          </h1>
          <p className="text-muted mt-1 text-sm">
            Ranked by growth — first exam vs. most recent — so students climbing from a low base get recognised too,
            not just students who were already on top{activeSubjectId ? ' in the selected subject' : ''}.
          </p>
        </div>
        {data && (
          <div className="self-start sm:self-end flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-display font-bold bg-emerald-500/10 border-emerald-500/30 text-emerald-400">
            <Trophy size={14} />
            {data.count} student{data.count !== 1 ? 's' : ''} ranked
          </div>
        )}
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
        {!!classroomId && streams.length > 0 && (
          <div className="w-full sm:w-44">
            <Select
              label="Stream"
              options={[{ value: '', label: 'All Streams' }, ...streams.map(s => ({ value: s.id, label: s.name }))]}
              value={streamId}
              onChange={e => { setStreamId(e.target.value); setPage(1); }}
            />
          </div>
        )}
        <div className="w-full sm:w-52">
          <Select
            label="Minimum Exams Counted"
            options={[
              { value: 2, label: '2 exams (most inclusive)' },
              { value: 3, label: '3 exams' },
              { value: 5, label: '5 exams (most reliable)' },
            ]}
            value={minExams}
            onChange={e => { setMinExams(Number(e.target.value)); setPage(1); }}
          />
        </div>
        <div className="w-full sm:w-52">
          <Select label="Sort By" options={SORT_OPTIONS} value={sortBy} onChange={e => setSortBy(e.target.value as SortBy)} />
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <LoadingPage />
      ) : students.length === 0 ? (
        <EmptyState
          icon={<TrendingUp size={36} className="text-muted" />}
          title="Not enough data yet"
          message="Students need at least the selected number of exams before a growth trend can be ranked."
        />
      ) : (
        <>
          {/* Summary strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Ranked', sub: `min ${minExams} exams`, value: data?.count ?? 0, color: '#3b82f6' },
              { label: 'Gaining', sub: 'positive growth', value: gaining, color: '#10b981' },
              { label: 'Slipping', sub: 'negative growth', value: slipping, color: '#f43f5e' },
              { label: 'Top Gain', sub: topGain?.student_name ?? null, value: topGain ? `+${topGain.delta} pts` : '—', color: '#f59e0b' },
            ].map(({ label, sub, value, color }) => (
              <div key={label} className="card p-3 border" style={{ borderColor: `${color}30` }}>
                <p className="text-[10px] text-secondary uppercase tracking-wider font-display">{label}</p>
                <p className="font-display font-bold text-xl mt-1" style={{ color }}>{value}</p>
                {sub && <p className="text-[10px] text-muted mt-0.5 truncate">{sub}</p>}
              </div>
            ))}
          </div>

          <p className="text-[11px] text-muted -mt-1">
            Growth = most recent exam % minus first exam % in scope, so it favours consistent climbers over students
            who were always near the top. A student can rank highly here while still being below the pass threshold —
            check the At-Risk page too before assuming "improving" means "safe".
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {paged.map((s, idx) => {
              const rank = students.indexOf(s);
              const medal = sortBy === 'gain_desc' && rank < 3 ? MEDAL_COLORS[rank] : null;
              return (
                <Reveal key={s.student_id} index={idx}>
                  <TiltCard
                    className="card p-4 cursor-pointer transition-all hover:shadow-lg hover:shadow-emerald-500/5 hover:-translate-y-0.5 active:scale-[0.99]"
                    style={{ borderColor: medal ? `${medal}40` : 'rgba(16,185,129,0.15)' }}
                    onClick={() => navigate(`/analytics/student/${s.student_id}`)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                          style={{ background: medal ? `linear-gradient(135deg, ${medal}, ${medal}aa)` : 'linear-gradient(135deg, #10b981, #3b82f6)' }}
                        >
                          {medal ? <Medal size={14} /> : `#${rank + 1}`}
                        </div>
                        <div className="min-w-0">
                          <p className="font-display font-semibold text-primary text-sm leading-tight truncate">{s.student_name}</p>
                          <p className="text-[11px] text-secondary truncate">{s.student_code} · {s.classroom ?? 'No class'}</p>
                        </div>
                      </div>
                      <div className="flex flex-col items-end flex-shrink-0 ml-2">
                        <span className={`font-display font-black text-xl ${s.delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {s.delta >= 0 ? '+' : ''}{s.delta}
                        </span>
                        <span className="text-[9px] text-secondary">pts gained</span>
                      </div>
                    </div>

                    {/* First -> latest mini progress bar */}
                    <div className="flex items-center gap-2 text-[11px] text-secondary mb-1">
                      <span className="font-mono">{s.first_percentage}%</span>
                      <div className="flex-1 h-1.5 rounded-full bg-surface-800 overflow-hidden relative">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-azure-500 to-emerald-500"
                          style={{ width: `${Math.min(100, s.latest_percentage)}%` }}
                        />
                      </div>
                      <span className="font-mono font-semibold text-primary">{s.latest_percentage}%</span>
                    </div>
                    <p className="text-[10px] text-muted">{s.exams_counted} exams counted</p>

                    <p className="text-[11px] text-emerald-400 font-display font-semibold mt-2">View full analytics →</p>
                  </TiltCard>
                </Reveal>
              );
            })}
          </div>

          <Pagination page={page} pageSize={pageSize} total={students.length} onChange={setPage} />
        </>
      )}
    </div>
  );
}

