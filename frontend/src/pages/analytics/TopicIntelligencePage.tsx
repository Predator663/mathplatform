import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LineChart, Line, Cell,
} from 'recharts';
import {
  Brain, ArrowUpRight, ArrowDownRight, Minus, X, TrendingUp, TrendingDown,
  Flame, Grid3x3, ListOrdered,
} from 'lucide-react';
import { analyticsApi, studentsApi, subjectsApi } from '../../api';
import { LoadingPage, EmptyState, Select, StatCard, TiltCard, Reveal } from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import { gradeColor, TERM_LABELS } from '../../utils';
import type {
  TopicIntelligenceOverview, TopicDistribution, Classroom, PaginatedResponse, Subject,
} from '../../types';

function TrendIcon({ trend, size = 14 }: { trend: string; size?: number }) {
  if (trend === 'improving') return <ArrowUpRight size={size} className="text-emerald-400" />;
  if (trend === 'declining') return <ArrowDownRight size={size} className="text-rose-400" />;
  return <Minus size={size} className="text-secondary" />;
}

function heatColor(pct: number | null): string {
  if (pct === null) return 'transparent';
  // Rose (weak) -> Amber -> Emerald (strong), matching the app's existing grade-color language.
  if (pct < 40) return 'rgba(244,63,94,0.75)';
  if (pct < 55) return 'rgba(244,63,94,0.4)';
  if (pct < 70) return 'rgba(245,158,11,0.45)';
  if (pct < 85) return 'rgba(16,185,129,0.35)';
  return 'rgba(16,185,129,0.7)';
}

export default function TopicIntelligencePage() {
  const { user } = useAuthStore();
  const [subjectFilter, setSubjectFilter] = useState('');
  const [classroomFilter, setClassroomFilter] = useState('');
  const [termFilter, setTermFilter] = useState('');
  const [includeQuizzes, setIncludeQuizzes] = useState(true);
  const [drilldownTopicId, setDrilldownTopicId] = useState<number | null>(null);

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
  });
  const subjects: Subject[] = Array.isArray(subjectsData) ? subjectsData : subjectsData?.results ?? [];

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData) ? classroomsData : classroomsData?.results ?? [];

  const params = {
    subject_id: subjectFilter || undefined,
    classroom_id: classroomFilter || undefined,
    term: termFilter || undefined,
    include_quizzes: includeQuizzes ? 'true' : 'false',
  };

  const { data: overview, isLoading, isError } = useQuery<TopicIntelligenceOverview>({
    queryKey: ['topic-intelligence-overview', params],
    queryFn: () => analyticsApi.topicIntelligenceOverview(params).then(r => r.data),
  });

  const { data: distribution, isLoading: loadingDist } = useQuery<TopicDistribution>({
    queryKey: ['topic-distribution', drilldownTopicId, params],
    queryFn: () => analyticsApi.topicDistribution(drilldownTopicId!, params).then(r => r.data),
    enabled: drilldownTopicId != null,
  });
  const drilldownTopic = overview?.topics.find(t => t.topic_id === drilldownTopicId);

  const rankingChartData = useMemo(
    () => (overview?.topics ?? []).slice(0, 12).map(t => ({ name: t.topic_name, average: t.average, color: t.color })),
    [overview],
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="page-title flex items-center gap-2"><Brain className="text-violet-400" size={22} /> Topic Intelligence</h1>
        <p className="text-muted mt-0.5">
          School-wide topic mastery — combining {includeQuizzes ? 'exams and daily quizzes' : 'exam data'}, ranked hardest to easiest.
        </p>
      </div>

      <div className="card p-3 flex flex-wrap items-end gap-3">
        <div className="w-52">
          <Select label="Subject" options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
            value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)} />
        </div>
        <div className="w-52">
          <Select label="Classroom" options={[{ value: '', label: user?.role === 'super_admin' ? 'All classrooms' : 'All my classrooms' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]}
            value={classroomFilter} onChange={e => setClassroomFilter(e.target.value)} />
        </div>
        <div className="w-44">
          <Select label="Term" options={[{ value: '', label: 'All terms' }, ...Object.entries(TERM_LABELS).map(([value, label]) => ({ value, label }))]}
            value={termFilter} onChange={e => setTermFilter(e.target.value)} />
        </div>
        <button
          onClick={() => setIncludeQuizzes(v => !v)}
          className={`flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-xs font-display font-medium transition-colors border ${
            includeQuizzes ? 'text-azure-400 border-azure-500/30 bg-azure-500/10' : 'text-secondary border-surface'
          }`}
        >
          <Flame size={13} /> Include Daily Quizzes
        </button>
      </div>

      {isLoading ? <LoadingPage /> : isError || !overview ? (
        <EmptyState icon={<Brain size={36} />} title="Couldn't load topic intelligence" message="Try adjusting the filters or refreshing." />
      ) : overview.topics.length === 0 ? (
        <EmptyState icon={<Brain size={36} />} title="No topic data yet" message="Once exams or daily quizzes are tagged with topics and scored, insights will appear here." />
      ) : (
        <>
          {/* Overview stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Topics Tracked" value={String(overview.topics.length)} color="violet" icon={<Grid3x3 size={18} />} />
            <StatCard label="Hardest Topic" value={overview.topics[0]?.topic_name ?? '—'} color="rose"
              sub={overview.topics[0] ? `${overview.topics[0].average}% average` : ''} icon={<TrendingDown size={18} />} />
            <StatCard label="Most Improved" value={overview.most_improved[0]?.topic_name ?? '—'} color="green" icon={<TrendingUp size={18} />} />
            <StatCard label="Most Declined" value={overview.most_declined[0]?.topic_name ?? '—'} color="amber" icon={<ArrowDownRight size={18} />} />
          </div>

          {/* Difficulty ranking */}
          <div className="card p-6">
            <h2 className="section-title mb-1 flex items-center gap-2"><ListOrdered size={15} className="text-rose-400" /> Difficulty Ranking</h2>
            <p className="text-xs text-secondary mb-5">Average score per topic, hardest first. Click a bar to drill in.</p>
            <ResponsiveContainer width="100%" height={Math.max(220, rankingChartData.length * 32)}>
              <BarChart data={rankingChartData} layout="vertical" margin={{ top: 5, right: 30, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                <YAxis type="category" dataKey="name" width={140} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                <Tooltip contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }} labelStyle={{ color: '#fff' }} />
                <Bar dataKey="average" radius={[0, 4, 4, 0]} cursor="pointer"
                  onClick={(data) => { const t = overview.topics.find(x => x.topic_name === data.name); if (t) setDrilldownTopicId(t.topic_id); }}>
                  {rankingChartData.map(entry => <Cell key={entry.name} fill={entry.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Classroom x Topic Heatmap */}
          {overview.classroom_matrix.classrooms.length > 0 && (
            <div className="card p-6 overflow-x-auto">
              <h2 className="section-title mb-1 flex items-center gap-2"><Grid3x3 size={15} className="text-azure-400" /> Classroom × Topic Heatmap</h2>
              <p className="text-xs text-secondary mb-5">Average % per classroom per topic. Darker = further from the pass mark or ahead of it.</p>
              <table className="text-xs border-collapse min-w-full">
                <thead>
                  <tr>
                    <th className="text-left py-2 pr-4 text-secondary font-display uppercase tracking-wider sticky left-0 bg-surface-800">Classroom</th>
                    {overview.classroom_matrix.topics.map(t => (
                      <th key={t.id} className="px-2 py-2 text-secondary font-display font-medium text-center whitespace-nowrap min-w-[90px]">
                        {t.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {overview.classroom_matrix.classrooms.map((c, ri) => (
                    <tr key={c.id}>
                      <td className="py-1.5 pr-4 font-display font-medium text-primary sticky left-0 bg-surface-800 whitespace-nowrap">{c.name}</td>
                      {overview.classroom_matrix.matrix[ri].map((val, ci) => (
                        <td key={ci} className="p-1">
                          <motion.div
                            initial={{ opacity: 0, scale: 0.8 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: (ri * overview.classroom_matrix.topics.length + ci) * 0.01 }}
                            className="rounded-lg py-2 text-center font-mono font-bold text-primary cursor-pointer hover:ring-1 hover:ring-white/30 transition-shadow"
                            style={{ backgroundColor: heatColor(val) }}
                            onClick={() => val !== null && setDrilldownTopicId(overview.classroom_matrix.topics[ci].id)}
                          >
                            {val !== null ? `${val}%` : '—'}
                          </motion.div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Trend movers */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card p-6">
              <h2 className="section-title mb-4 flex items-center gap-2"><TrendingUp size={15} className="text-emerald-400" /> Most Improved Topics</h2>
              {overview.most_improved.length === 0 ? (
                <p className="text-muted text-sm text-center py-6">No topics trending upward yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {overview.most_improved.map(t => (
                    <button key={t.topic_id} onClick={() => setDrilldownTopicId(t.topic_id)}
                      className="flex items-center justify-between gap-2 p-3 rounded-xl bg-surface-900 hover:bg-surface-800 transition-colors text-left">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: t.color }} />
                        <span className="text-sm font-display font-medium text-primary">{t.topic_name}</span>
                      </div>
                      <span className={`font-mono text-sm font-bold ${gradeColor(t.average)}`}>{t.average}%</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="card p-6">
              <h2 className="section-title mb-4 flex items-center gap-2"><TrendingDown size={15} className="text-rose-400" /> Most Declined Topics</h2>
              {overview.most_declined.length === 0 ? (
                <p className="text-muted text-sm text-center py-6">No topics trending downward — nice work.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {overview.most_declined.map(t => (
                    <button key={t.topic_id} onClick={() => setDrilldownTopicId(t.topic_id)}
                      className="flex items-center justify-between gap-2 p-3 rounded-xl bg-surface-900 hover:bg-surface-800 transition-colors text-left">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: t.color }} />
                        <span className="text-sm font-display font-medium text-primary">{t.topic_name}</span>
                      </div>
                      <span className={`font-mono text-sm font-bold ${gradeColor(t.average)}`}>{t.average}%</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* All topics grid */}
          <div>
            <h2 className="section-title mb-3">All Topics</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {overview.topics.map((t, i) => (
                <Reveal key={t.topic_id} index={i}>
                  <TiltCard
                    onClick={() => setDrilldownTopicId(t.topic_id)}
                    aria-label={`${t.topic_name} — view distribution`}
                    className="p-4 cursor-pointer border border-surface hover:border-white/10"
                    maxTilt={5}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: t.color }} />
                        <p className="font-display font-semibold text-sm text-primary truncate">{t.topic_name}</p>
                      </div>
                      <span className="text-[10px] text-secondary font-mono flex-shrink-0">#{t.difficulty_rank}</span>
                    </div>
                    <p className="text-[11px] text-secondary mb-3">{t.subject_name} · {t.attempts} attempt{t.attempts !== 1 ? 's' : ''} · {t.student_count} student{t.student_count !== 1 ? 's' : ''}</p>
                    <div className="flex items-center justify-between">
                      <span className={`font-mono text-lg font-bold ${gradeColor(t.average)}`}>{t.average}%</span>
                      <span className="flex items-center gap-1 text-xs capitalize text-secondary"><TrendIcon trend={t.trend} /> {t.trend}</span>
                    </div>
                  </TiltCard>
                </Reveal>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Drill-down modal-ish panel */}
      <AnimatePresence>
        {drilldownTopicId != null && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4"
            onClick={() => setDrilldownTopicId(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="card p-6 max-w-2xl w-full max-h-[85vh] overflow-y-auto"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="font-display font-bold text-lg text-primary flex items-center gap-2">
                    {drilldownTopic && <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: drilldownTopic.color }} />}
                    {drilldownTopic?.topic_name ?? 'Topic'}
                  </h2>
                  <p className="text-xs text-secondary mt-0.5">{drilldownTopic?.subject_name}</p>
                </div>
                <button onClick={() => setDrilldownTopicId(null)} className="text-secondary hover:text-primary transition-colors">
                  <X size={18} />
                </button>
              </div>

              {loadingDist ? <LoadingPage /> : !distribution || !distribution.summary ? (
                <EmptyState icon={<Brain size={28} />} title="No data for this topic" message="No scored attempts recorded under the current filters." />
              ) : (
                <div className="flex flex-col gap-5">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <div className="bg-surface-900 rounded-xl p-3 text-center">
                      <p className="text-[10px] text-secondary uppercase tracking-wider">Average</p>
                      <p className={`font-mono font-bold text-lg ${gradeColor(distribution.summary.average)}`}>{distribution.summary.average}%</p>
                    </div>
                    <div className="bg-surface-900 rounded-xl p-3 text-center">
                      <p className="text-[10px] text-secondary uppercase tracking-wider">Attempts</p>
                      <p className="font-mono font-bold text-lg text-primary">{distribution.summary.attempts}</p>
                    </div>
                    <div className="bg-surface-900 rounded-xl p-3 text-center">
                      <p className="text-[10px] text-secondary uppercase tracking-wider">Students</p>
                      <p className="font-mono font-bold text-lg text-primary">{distribution.summary.student_count}</p>
                    </div>
                    <div className="bg-surface-900 rounded-xl p-3 text-center">
                      <p className="text-[10px] text-secondary uppercase tracking-wider">Trend</p>
                      <p className="flex items-center justify-center gap-1 font-display font-bold text-sm text-primary capitalize"><TrendIcon trend={distribution.summary.trend} /> {distribution.summary.trend}</p>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-display font-semibold text-secondary uppercase tracking-wider mb-2">Mastery Distribution</p>
                    <ResponsiveContainer width="100%" height={160}>
                      <BarChart data={distribution.histogram} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                        <XAxis dataKey="range" tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                        <YAxis allowDecimals={false} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                        <Tooltip contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }} labelStyle={{ color: '#fff' }} />
                        <Bar dataKey="count" radius={[4, 4, 0, 0]} fill={drilldownTopic?.color ?? '#3b82f6'} />
                      </BarChart>
                    </ResponsiveContainer>
                    <p className="text-[11px] text-secondary mt-1">Number of students by their own average on this topic.</p>
                  </div>

                  {distribution.timeline.length > 1 && (
                    <div>
                      <p className="text-xs font-display font-semibold text-secondary uppercase tracking-wider mb-2">Trend Over Time</p>
                      <ResponsiveContainer width="100%" height={160}>
                        <LineChart data={distribution.timeline.map(t => ({ name: t.date, percentage: t.percentage }))} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                          <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 9, fontFamily: 'DM Sans' }} />
                          <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                          <Tooltip contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }} labelStyle={{ color: '#fff' }} />
                          <Line type="monotone" dataKey="percentage" stroke={drilldownTopic?.color ?? '#3b82f6'} strokeWidth={2.5} dot={{ r: 3 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
