import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, RadarChart,
  PolarGrid, PolarAngleAxis, Radar, Legend,
} from 'recharts';
import { analyticsApi } from '../../api';
import { LoadingPage } from '../../components/ui';
import { formatDate, gradeBg, gradeColor, trendColor, trendIcon } from '../../utils';
import type { StudentSummary, StudentTrend, StudentTopicAnalysis } from '../../types';

const ChartTooltip = ({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) => {
  if (active && payload?.length) {
    return (
      <div className="card px-3 py-2 text-xs shadow-xl">
        <p className="font-display font-semibold text-primary mb-1">{label}</p>
        {payload.map(p => (
          <p key={p.name} style={{ color: p.name === 'percentage' ? '#3b82f6' : '#a78bfa' }}>
            {p.name === 'percentage' ? 'Score' : 'Moving Avg'}: {p.value}%
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function StudentAnalyticsPage() {
  const { id } = useParams<{ id: string }>();
  const studentId = Number(id);

  const { data: summary, isLoading: s1 } = useQuery<StudentSummary>({
    queryKey: ['student-summary', studentId],
    queryFn: () => analyticsApi.studentSummary(studentId).then(r => r.data),
  });

  const { data: trend, isLoading: s2 } = useQuery<StudentTrend>({
    queryKey: ['student-trend', studentId],
    queryFn: () => analyticsApi.studentTrend(studentId).then(r => r.data),
  });

  const { data: topicData, isLoading: s3 } = useQuery<StudentTopicAnalysis>({
    queryKey: ['student-topics', studentId],
    queryFn: () => analyticsApi.studentTopics(studentId).then(r => r.data),
  });

  if (s1 || s2 || s3) return <LoadingPage />;
  if (!summary) return <div className="text-muted">Student not found.</div>;

  // Build chart data merging trend + moving average
  const chartData = (trend?.timeline ?? []).map((t, i) => ({
    name: t.exam_title.length > 12 ? t.exam_title.slice(0, 12) + '…' : t.exam_title,
    percentage: t.percentage,
    movingAvg: trend?.moving_average[i] ?? t.percentage,
    date: formatDate(t.exam_date),
    grade: t.letter_grade,
  }));

  // Radar data
  const radarData = (topicData?.topics ?? []).map(t => ({
    topic: t.topic_name.length > 10 ? t.topic_name.slice(0, 10) + '…' : t.topic_name,
    average: t.average,
    fullMark: 100,
  }));

  const trendVal = summary.trend;

  return (
    <div className="flex flex-col gap-6 page-enter">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="page-title">{summary.student_name}</h1>
          <p className="text-muted mt-0.5">
            {summary.student_code} · {summary.classroom ?? 'No classroom'}
          </p>
        </div>
        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-display font-semibold ${trendColor(trendVal)} bg-surface-800 border border-surface`}>
          <span>{trendIcon(trendVal)}</span>
          <span className="capitalize">{trendVal}</span>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          { label: 'Average Score', value: summary.average_percentage != null ? `${summary.average_percentage}%` : '—', color: gradeBg(summary.average_percentage ?? 0) },
          { label: 'Exams Taken', value: summary.total_exams, color: 'bg-azure-500/15 text-azure-400' },
          { label: 'Pass Rate', value: `${summary.pass_rate}%`, color: summary.pass_rate >= 50 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400' },
          { label: 'Highest Score', value: `${summary.highest_percentage}%`, color: 'bg-emerald-500/15 text-emerald-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card p-5">
            <p className="label">{label}</p>
            <p className={`font-display font-bold text-2xl px-2 py-0.5 rounded-lg inline-block mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Timeline chart */}
        <div className="xl:col-span-2 card p-6">
          <h2 className="section-title mb-5">Performance Timeline</h2>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 11, fontFamily: 'DM Sans' }} />
                <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 11, fontFamily: 'DM Sans' }} />
                <Tooltip content={<ChartTooltip />} />
                <ReferenceLine y={50} stroke="#f43f5e" strokeDasharray="4 4" strokeOpacity={0.5} label={{ value: 'Pass', fill: '#f43f5e', fontSize: 10 }} />
                <Legend
                  formatter={(value) => <span style={{ color: '#6b7280', fontSize: 11 }}>{value === 'percentage' ? 'Score' : 'Moving Avg'}</span>}
                />
                <Line type="monotone" dataKey="percentage" stroke="#3b82f6" strokeWidth={2.5} dot={{ fill: '#3b82f6', r: 4, strokeWidth: 0 }} activeDot={{ r: 6 }} name="percentage" />
                <Line type="monotone" dataKey="movingAvg" stroke="#a78bfa" strokeWidth={1.5} strokeDasharray="5 3" dot={false} name="movingAvg" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-muted">No exam data yet</div>
          )}
        </div>

        {/* Radar chart */}
        <div className="card p-6">
          <h2 className="section-title mb-5">Topic Mastery</h2>
          {radarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#2e2e42" />
                <PolarAngleAxis dataKey="topic" tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                <Radar name="Avg" dataKey="average" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.25} strokeWidth={2} />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-muted">No topic data yet</div>
          )}
        </div>
      </div>

      {/* Topic breakdown table */}
      {(topicData?.topics?.length ?? 0) > 0 && (
        <div className="card p-6">
          <h2 className="section-title mb-5">Topic Breakdown</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {topicData!.topics.map(topic => (
              <div key={topic.topic_id} className="flex items-center gap-3 p-3 rounded-xl bg-surface-900">
                <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: topic.color }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-display font-medium text-primary">{topic.topic_name}</span>
                    <span className={`text-xs font-mono font-bold ${gradeColor(topic.average)}`}>{topic.average}%</span>
                  </div>
                  <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${topic.average}%`, backgroundColor: topic.color }}
                    />
                  </div>
                </div>
                <div className={`text-xs font-display font-semibold ${trendColor(topic.trend)}`}>
                  {trendIcon(topic.trend)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent scores */}
      <div className="card p-6">
        <h2 className="section-title mb-5">Recent Scores</h2>
        <div className="flex flex-col gap-2">
          {summary.recent_scores.map(score => (
            <div key={score.exam_id} className="flex items-center justify-between p-3 rounded-xl bg-surface-900 hover:bg-surface-800 transition-colors">
              <div>
                <p className="text-sm font-display font-medium text-primary">{score.exam_title}</p>
                <p className="text-xs text-secondary mt-0.5">{formatDate(score.exam_date)}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-sm font-mono font-bold ${gradeColor(score.percentage)}`}>
                  {score.score}/{score.max_score}
                </span>
                <span className={`badge ${gradeBg(score.percentage)}`}>
                  {score.letter_grade}
                </span>
                <span className={`badge ${score.passed ? 'badge-green' : 'badge-rose'}`}>
                  {score.passed ? 'Pass' : 'Fail'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
