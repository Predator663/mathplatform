import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, BarChart, Bar, Cell,
} from 'recharts';
import { analyticsApi, studentsApi } from '../../api';
import { LoadingPage, Table, Tr, Td, EmptyState, Select } from '../../components/ui';
import { formatDate, gradeColor, TERM_LABELS, EXAM_TYPE_LABELS } from '../../utils';
import type { ClassAnalytics, Classroom, PaginatedResponse } from '../../types';
import { BarChart3 } from 'lucide-react';

const DIST_COLORS: Record<string, string> = {
  '0-49': '#f43f5e', '50-59': '#f59e0b', '60-69': '#fbbf24',
  '70-79': '#60a5fa', '80-89': '#34d399', '90-100': '#10b981',
};

export default function ClassAnalyticsPage() {
  const navigate = useNavigate();
  const [selectedClass, setSelectedClass] = useState<number | null>(null);
  const [selectedTerm, setSelectedTerm] = useState<string>('');

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData
    : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data: analytics, isLoading } = useQuery<ClassAnalytics>({
    queryKey: ['class-analytics', selectedClass, selectedTerm],
    queryFn: () => analyticsApi.classAnalytics(selectedClass!, { term: selectedTerm || undefined }).then(r => r.data),
    enabled: !!selectedClass,
  });

  const examChartData = (analytics?.exam_summaries ?? []).map(e => ({
    name: e.exam_title.length > 14 ? e.exam_title.slice(0, 14) + '…' : e.exam_title,
    average: e.average,
    pass_rate: e.pass_rate,
    date: formatDate(e.exam_date),
  }));

  const distData = analytics?.distribution
    ? Object.entries(analytics.distribution).map(([range, count]) => ({ range, count }))
    : [];

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div>
        <h1 className="page-title">Class Analytics</h1>
        <p className="text-muted mt-1">Analyse performance across a classroom over time.</p>
      </div>

      {/* Filters */}
      <div className="card p-4 flex items-center gap-4">
        <div className="flex-1 max-w-xs">
          <Select
            label="Select Classroom"
            options={[
              { value: '', label: 'Choose a classroom…' },
              ...classrooms.map(c => ({ value: c.id, label: `${c.name} — ${c.grade_level_name} (${c.academic_year})` })),
            ]}
            value={selectedClass ?? ''}
            onChange={e => setSelectedClass(e.target.value ? Number(e.target.value) : null)}
          />
        </div>
        <div className="w-40">
          <Select
            label="Filter by Term"
            options={[
              { value: '', label: 'All Terms' },
              { value: 'term_1', label: 'Term 1' },
              { value: 'term_2', label: 'Term 2' },
              { value: 'term_3', label: 'Term 3' },
            ]}
            value={selectedTerm}
            onChange={e => setSelectedTerm(e.target.value)}
          />
        </div>
      </div>

      {!selectedClass ? (
        <EmptyState icon={<BarChart3 size={40} />} title="Select a classroom" message="Choose a classroom above to view analytics." />
      ) : isLoading ? (
        <LoadingPage />
      ) : !analytics ? (
        <div className="text-muted text-center py-16">No data available.</div>
      ) : (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {[
              { label: 'Overall Average', value: analytics.overall_average != null ? `${analytics.overall_average}%` : '—' },
              { label: 'Students Ranked', value: analytics.student_rankings.length },
              { label: 'At Risk', value: analytics.at_risk_students.length },
              { label: 'Exams Analysed', value: analytics.exam_summaries.length },
            ].map(({ label, value }) => (
              <div key={label} className="card p-5">
                <p className="label">{label}</p>
                <p className="font-display font-bold text-2xl text-primary mt-1">{value}</p>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* Average per exam */}
            <div className="card p-6">
              <h2 className="section-title mb-5">Class Average by Exam</h2>
              {examChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={examChartData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                    <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                    <Tooltip
                      contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }}
                      labelStyle={{ color: '#fff' }}
                    />
                    <Line type="monotone" dataKey="average" stroke="#3b82f6" strokeWidth={2.5} dot={{ fill: '#3b82f6', r: 4, strokeWidth: 0 }} name="Avg %" />
                    <Line type="monotone" dataKey="pass_rate" stroke="#10b981" strokeWidth={2} strokeDasharray="5 3" dot={false} name="Pass Rate %" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted text-center py-12">No exam data for this filter.</p>
              )}
            </div>

            {/* Score distribution */}
            <div className="card p-6">
              <h2 className="section-title mb-5">Score Distribution</h2>
              {distData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={distData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                    <XAxis dataKey="range" tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                    <YAxis tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                    <Tooltip
                      contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }}
                      labelStyle={{ color: '#fff' }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {distData.map(entry => (
                        <Cell key={entry.range} fill={DIST_COLORS[entry.range] ?? '#6366f1'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted text-center py-12">No distribution data.</p>
              )}
            </div>
          </div>

          {/* Exam summaries table */}
          {analytics.exam_summaries.length > 0 && (
            <div className="card p-6">
              <h2 className="section-title mb-5">Exam Summaries</h2>
              <Table headers={['Exam', 'Type', 'Term', 'Date', 'Students', 'Average', 'Highest', 'Lowest', 'Pass Rate']}>
                {analytics.exam_summaries.map(e => (
                  <Tr key={e.exam_id} onClick={() => navigate(`/exams/${e.exam_id}`)}>
                    <Td><span className="font-display font-medium text-primary">{e.exam_title}</span></Td>
                    <Td><span className="badge badge-violet">{EXAM_TYPE_LABELS[e.exam_type]}</span></Td>
                    <Td className="text-secondary text-xs">{TERM_LABELS[e.term]}</Td>
                    <Td className="text-secondary text-xs font-mono">{formatDate(e.exam_date)}</Td>
                    <Td className="font-mono text-xs">{e.student_count}</Td>
                    <Td><span className={`font-mono text-sm font-bold ${gradeColor(e.average)}`}>{e.average}%</span></Td>
                    <Td><span className="font-mono text-xs text-emerald-400">{e.highest}%</span></Td>
                    <Td><span className="font-mono text-xs text-rose-400">{e.lowest}%</span></Td>
                    <Td><span className={`font-mono text-sm font-bold ${gradeColor(e.pass_rate)}`}>{e.pass_rate}%</span></Td>
                  </Tr>
                ))}
              </Table>
            </div>
          )}

          {/* Student rankings */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* Top performers */}
            <div className="card p-6">
              <h2 className="section-title mb-4">Top Performers</h2>
              <div className="flex flex-col gap-2">
                {analytics.top_performers.map((s, i) => (
                  <div
                    key={s.student_id}
                    className="flex items-center gap-3 p-3 rounded-xl bg-surface-900 cursor-pointer hover:bg-surface-800 transition-colors"
                    onClick={() => navigate(`/analytics/student/${s.student_id}`)}
                  >
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-display font-bold flex-shrink-0 ${
                      i === 0 ? 'bg-amber-500/20 text-amber-400' :
                      i === 1 ? 'bg-surface-600 text-primary' :
                      'bg-surface-700 text-secondary'
                    }`}>
                      {s.rank}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-display font-medium text-primary truncate">{s.student_name}</p>
                      <p className="text-xs text-secondary">{s.exams_taken} exams</p>
                    </div>
                    <span className={`font-mono text-sm font-bold ${gradeColor(s.average)}`}>{s.average}%</span>
                  </div>
                ))}
              </div>
            </div>

            {/* At risk */}
            <div className="card p-6">
              <h2 className="section-title mb-4 text-rose-400">At-Risk Students</h2>
              {analytics.at_risk_students.length === 0 ? (
                <p className="text-muted text-center py-8">No at-risk students 🎉</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {analytics.at_risk_students.map(s => (
                    <div
                      key={s.student_id}
                      className="flex items-center gap-3 p-3 rounded-xl bg-rose-500/5 border border-rose-500/15 cursor-pointer hover:bg-rose-500/10 transition-colors"
                      onClick={() => navigate(`/analytics/student/${s.student_id}`)}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-display font-medium text-primary truncate">{s.student_name}</p>
                        <p className="text-xs text-secondary">{s.exams_taken} exams</p>
                      </div>
                      <span className="font-mono text-sm font-bold text-rose-400">{s.average}%</span>
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
