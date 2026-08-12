import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, BarChart, Bar, Cell,
} from 'recharts';
import { BarChart3, AlertTriangle, Trophy, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import { quizzesApi, studentsApi, subjectsApi, examsApi } from '../../api';
import { LoadingPage, EmptyState, Select, Table, Tr, Td } from '../../components/ui';
import { formatDate, gradeColor, TERM_LABELS } from '../../utils';
import type { ClassroomQuizAnalytics, Classroom, PaginatedResponse, Subject, MathTopic } from '../../types';

const TOPIC_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#f43f5e', '#06b6d4', '#84cc16', '#ec4899'];

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'improving') return <ArrowUpRight size={13} className="text-emerald-400" />;
  if (trend === 'declining') return <ArrowDownRight size={13} className="text-rose-400" />;
  return <Minus size={13} className="text-secondary" />;
}

export default function ClassroomQuizAnalyticsPage() {
  const navigate = useNavigate();
  const { classroomId: classroomIdParam } = useParams<{ classroomId: string }>();
  const [selectedClass, setSelectedClass] = useState<number | null>(classroomIdParam ? Number(classroomIdParam) : null);
  const [subjectFilter, setSubjectFilter] = useState('');
  const [topicFilter, setTopicFilter] = useState('');
  const [termFilter, setTermFilter] = useState('');

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
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
    enabled: !!subjectFilter,
  });
  const topics: MathTopic[] = Array.isArray(topicsData) ? topicsData : topicsData?.results ?? [];

  const { data: analytics, isLoading, isError } = useQuery<ClassroomQuizAnalytics>({
    queryKey: ['quiz-classroom-analytics', selectedClass, subjectFilter, topicFilter, termFilter],
    queryFn: () => quizzesApi.classroomAnalytics(selectedClass!, {
      subject_id: subjectFilter || undefined,
      topic_id: topicFilter || undefined,
      term: termFilter || undefined,
    }).then(r => r.data),
    enabled: !!selectedClass,
  });

  const trendData = (analytics?.trend ?? []).map(t => ({
    name: formatDate(t.date), average: t.average, pass_rate: t.pass_rate,
  }));
  const topicData = analytics?.topic_breakdown ?? [];

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div>
        <h1 className="page-title flex items-center gap-2"><BarChart3 className="text-azure-400" size={22} /> Daily Quiz Analytics</h1>
        <p className="text-muted mt-0.5">Class-scoped performance, topic mastery, and trends</p>
      </div>

      <div className="card p-3 flex flex-wrap items-end gap-3">
        <div className="w-56">
          <Select label="Classroom"
            options={[{ value: '', label: 'Select a classroom…' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]}
            value={selectedClass ?? ''}
            onChange={e => setSelectedClass(e.target.value ? Number(e.target.value) : null)} />
        </div>
        <div className="w-44">
          <Select label="Subject"
            options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
            value={subjectFilter} onChange={e => { setSubjectFilter(e.target.value); setTopicFilter(''); }} />
        </div>
        <div className="w-44">
          <Select label="Topic"
            options={[{ value: '', label: 'All topics' }, ...topics.map(t => ({ value: t.id, label: t.name }))]}
            value={topicFilter} onChange={e => setTopicFilter(e.target.value)} disabled={!subjectFilter} />
        </div>
        <div className="w-40">
          <Select label="Term"
            options={[{ value: '', label: 'All terms' }, ...Object.entries(TERM_LABELS).map(([value, label]) => ({ value, label }))]}
            value={termFilter} onChange={e => setTermFilter(e.target.value)} />
        </div>
      </div>

      {!selectedClass ? (
        <EmptyState icon={<BarChart3 size={36} />} title="Pick a classroom" message="Select a classroom above to see its daily quiz analytics." />
      ) : isLoading ? (
        <LoadingPage />
      ) : isError || !analytics ? (
        <EmptyState icon={<BarChart3 size={36} />} title="Couldn't load analytics" message="Try refreshing, or check you're assigned to this classroom." />
      ) : analytics.overview.quiz_count === 0 ? (
        <EmptyState icon={<BarChart3 size={36} />} title="No quizzes yet" message="Once quizzes are recorded for this classroom, analytics will appear here." />
      ) : (
        <>
          {/* Overview cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Quizzes Given', value: analytics.overview.quiz_count },
              { label: 'Average Score', value: analytics.overview.average_score != null ? `${analytics.overview.average_score}%` : '—' },
              { label: 'Pass Rate', value: analytics.overview.pass_rate != null ? `${analytics.overview.pass_rate}%` : '—' },
              { label: 'Participation', value: analytics.overview.participation_rate != null ? `${analytics.overview.participation_rate}%` : '—' },
            ].map(({ label, value }) => (
              <div key={label} className="card p-5">
                <p className="label">{label}</p>
                <p className="font-display font-bold text-2xl text-primary mt-1">{value}</p>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="card p-6">
              <h2 className="section-title mb-5">Score Trend Over Time</h2>
              {trendData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={trendData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                    <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                    <Tooltip contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }} labelStyle={{ color: '#fff' }} />
                    <Line type="monotone" dataKey="average" stroke="#3b82f6" strokeWidth={2.5} dot={{ fill: '#3b82f6', r: 4, strokeWidth: 0 }} name="Avg %" />
                    <Line type="monotone" dataKey="pass_rate" stroke="#10b981" strokeWidth={2} strokeDasharray="5 3" dot={false} name="Pass Rate %" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted text-center py-12">No quiz data for this filter.</p>
              )}
            </div>

            <div className="card p-6">
              <h2 className="section-title mb-5">Average by Topic</h2>
              {topicData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={topicData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                    <XAxis dataKey="topic_name" tick={{ fill: '#3d3d55', fontSize: 9, fontFamily: 'DM Sans' }} angle={-15} textAnchor="end" height={50} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                    <Tooltip contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }} labelStyle={{ color: '#fff' }} />
                    <Bar dataKey="average" radius={[4, 4, 0, 0]}>
                      {topicData.map((entry, i) => (
                        <Cell key={entry.topic_name} fill={TOPIC_COLORS[i % TOPIC_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted text-center py-12">No topic-tagged quizzes yet.</p>
              )}
            </div>
          </div>

          {/* Topic table */}
          <div className="card p-6">
            <h2 className="section-title mb-5">Topic Mastery Breakdown</h2>
            {topicData.length === 0 ? (
              <p className="text-muted text-center py-8">No topic-tagged quizzes recorded yet.</p>
            ) : (
              <Table headers={['Topic', 'Attempts', 'Average', 'Highest', 'Lowest', 'Trend']}>
                {topicData.map(t => (
                  <Tr key={t.topic_name}>
                    <Td><span className="font-display font-medium text-primary">{t.topic_name}</span></Td>
                    <Td className="font-mono text-xs">{t.attempts}</Td>
                    <Td><span className={`font-mono text-sm font-bold ${gradeColor(t.average)}`}>{t.average}%</span></Td>
                    <Td><span className="font-mono text-xs text-emerald-400">{t.highest}%</span></Td>
                    <Td><span className="font-mono text-xs text-rose-400">{t.lowest}%</span></Td>
                    <Td><span className="flex items-center gap-1 text-xs capitalize"><TrendIcon trend={t.trend} /> {t.trend}</span></Td>
                  </Tr>
                ))}
              </Table>
            )}
          </div>

          {/* At-risk / top students */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card p-6">
              <h2 className="section-title mb-4 flex items-center gap-2"><AlertTriangle size={16} className="text-rose-400" /> At-Risk Students</h2>
              {analytics.at_risk_students.length === 0 ? (
                <p className="text-muted text-sm text-center py-6">No at-risk students on this filter — nice work!</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {analytics.at_risk_students.map(s => (
                    <div key={s.student_id} className="flex items-center justify-between gap-2 p-3 rounded-xl bg-surface-900 cursor-pointer hover:bg-surface-800 transition-colors"
                      onClick={() => navigate(`/students/${s.student_id}`)}>
                      <p className="text-sm font-display font-medium text-primary">{s.student_name}</p>
                      <span className={`font-mono text-sm font-bold ${gradeColor(s.average)}`}>{s.average}% ({s.attempts} quizzes)</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="card p-6">
              <h2 className="section-title mb-4 flex items-center gap-2"><Trophy size={16} className="text-amber-400" /> Top Performers</h2>
              {analytics.top_students.length === 0 ? (
                <p className="text-muted text-sm text-center py-6">No data yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {analytics.top_students.map(s => (
                    <div key={s.student_id} className="flex items-center justify-between gap-2 p-3 rounded-xl bg-surface-900 cursor-pointer hover:bg-surface-800 transition-colors"
                      onClick={() => navigate(`/students/${s.student_id}`)}>
                      <p className="text-sm font-display font-medium text-primary">{s.student_name}</p>
                      <span className={`font-mono text-sm font-bold ${gradeColor(s.average)}`}>{s.average}% ({s.attempts} quizzes)</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
