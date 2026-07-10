import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, BarChart, Bar, Cell,
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
} from 'recharts';
import { GitCompare } from 'lucide-react';
import { analyticsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState } from '../../components/ui';
import { useSubjectStore } from '../../store/subject';
import { gradeColor } from '../../utils';
import type { Classroom, PaginatedResponse, ComparativeAnalysis } from '../../types';

const CLASSROOM_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4'];

export default function CompareAnalyticsPage() {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectedTerm, setSelectedTerm] = useState('');
  const { activeSubjectId } = useSubjectStore();

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData
    : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data: compareData, isLoading } = useQuery<ComparativeAnalysis>({
    queryKey: ['compare', selectedIds, selectedTerm, activeSubjectId],
    queryFn: () =>
      analyticsApi.compare({
        classroom_ids: selectedIds.join(','),
        term: selectedTerm || undefined,
        ...(activeSubjectId ? { subject_id: activeSubjectId } : {}),
      }).then(r => r.data),
    enabled: selectedIds.length >= 2,
  });

  const toggleClassroom = (id: number) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  // Build chart data: exam title → avg per classroom
  const allExamTitles = new Set<string>();
  (compareData?.comparisons ?? []).forEach(c =>
    c.exam_summaries.forEach(e => allExamTitles.add(e.exam_title))
  );

  const chartData = Array.from(allExamTitles).map(title => {
    const point: Record<string, string | number> = {
      name: title.length > 14 ? title.slice(0, 14) + '…' : title,
    };
    (compareData?.comparisons ?? []).forEach(c => {
      const match = c.exam_summaries.find(e => e.exam_title === title);
      point[c.classroom_name] = match?.average ?? 0;
    });
    return point;
  });

  const overallBarData = (compareData?.comparisons ?? []).map(c => ({
    name: c.classroom_name,
    average: c.overall_average ?? 0,
  }));

  // Per-classroom aggregates derived from exam_summaries (pass rate + consistency
  // were already computed by the backend per exam but never rolled up for comparison).
  const classroomStats = (compareData?.comparisons ?? []).map(c => {
    const summaries = c.exam_summaries;
    const avgPassRate = summaries.length
      ? Math.round((summaries.reduce((sum, e) => sum + e.pass_rate, 0) / summaries.length) * 10) / 10
      : 0;
    const avgStdDev = summaries.length
      ? summaries.reduce((sum, e) => sum + e.std_dev, 0) / summaries.length
      : 0;
    return {
      classroom_id: c.classroom_id,
      classroom_name: c.classroom_name,
      average: c.overall_average ?? 0,
      passRate: avgPassRate,
      consistency: Math.max(0, Math.round(100 - avgStdDev)),
    };
  });

  const passRateBarData = classroomStats.map(s => ({ name: s.classroom_name, passRate: s.passRate }));

  const profileMetrics = [
    { key: 'average', label: 'Average' },
    { key: 'passRate', label: 'Pass Rate' },
    { key: 'consistency', label: 'Consistency' },
  ] as const;
  const radarProfileData = profileMetrics.map(({ key, label }) => {
    const point: Record<string, string | number> = { metric: label };
    classroomStats.forEach(s => { point[s.classroom_name] = s[key]; });
    return point;
  });

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div>
        <h1 className="page-title">Comparative Analysis</h1>
        <p className="text-muted mt-1">Select two or more classrooms to compare performance side-by-side.</p>
      </div>

      {/* Classroom selector */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title">Select Classrooms</h2>
          {selectedIds.length > 0 && (
            <button
              onClick={() => setSelectedIds([])}
              className="text-xs text-secondary hover:text-primary transition-colors"
            >
              Clear all
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2 mb-4">
          {classrooms.map((c) => {
            const isSelected = selectedIds.includes(c.id);
            const color = CLASSROOM_COLORS[selectedIds.indexOf(c.id)] ?? '#3d3d55';
            return (
              <button
                key={c.id}
                onClick={() => toggleClassroom(c.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-display font-medium border transition-all ${
                  isSelected
                    ? 'border-transparent text-primary'
                    : 'bg-surface-900 border-surface text-secondary hover:border-azure-500/50 hover:text-primary'
                }`}
                style={isSelected ? { backgroundColor: color + '25', borderColor: color + '80', color } : {}}
              >
                {isSelected && (
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                )}
                {c.name} — {c.grade_level_name}
                <span className="text-xs opacity-60">({c.academic_year})</span>
              </button>
            );
          })}
        </div>

        {/* Term filter */}
        <div className="flex items-center gap-3 pt-3 border-t border-surface">
          <span className="label mb-0">Filter by term:</span>
          <div className="flex gap-1">
            {[{ value: '', label: 'All' }, { value: 'term_1', label: 'Term 1' }, { value: 'term_2', label: 'Term 2' }, { value: 'term_3', label: 'Term 3' }].map(opt => (
              <button
                key={opt.value}
                onClick={() => setSelectedTerm(opt.value)}
                className={`px-3 py-1 rounded-lg text-xs font-display font-medium transition-all ${
                  selectedTerm === opt.value
                    ? 'bg-azure-500/20 text-azure-400'
                    : 'text-secondary hover:text-primary hover:bg-surface-700'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {selectedIds.length < 2 ? (
        <EmptyState
          icon={<GitCompare size={40} />}
          title="Select at least 2 classrooms"
          message="Pick two or more classrooms above to start comparing."
        />
      ) : isLoading ? (
        <LoadingPage />
      ) : (
        <>
          {/* Overall averages + pass rate by classroom */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="card p-6">
              <h2 className="section-title mb-5">Overall Average by Classroom</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={overallBarData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                  <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 11, fontFamily: 'DM Sans' }} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 11, fontFamily: 'DM Sans' }} />
                  <Tooltip
                    contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }}
                    labelStyle={{ color: '#fff' }}
                    formatter={(value: any) => [`${value}%`, 'Average'] as [string, string]}
                  />
                  <Bar dataKey="average" radius={[4, 4, 0, 0]} barSize={48}>
                    {overallBarData.map((entry, i) => (
                      <Cell key={entry.name} fill={CLASSROOM_COLORS[i] ?? '#6366f1'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card p-6">
              <h2 className="section-title mb-5">Pass Rate by Classroom</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={passRateBarData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                  <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 11, fontFamily: 'DM Sans' }} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 11, fontFamily: 'DM Sans' }} />
                  <Tooltip
                    contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }}
                    labelStyle={{ color: '#fff' }}
                    formatter={(value: any) => [`${value}%`, 'Pass rate'] as [string, string]}
                  />
                  <Bar dataKey="passRate" radius={[4, 4, 0, 0]} barSize={48}>
                    {passRateBarData.map((entry, i) => (
                      <Cell key={entry.name} fill={CLASSROOM_COLORS[i] ?? '#6366f1'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="text-xs text-muted mt-3">Average pass rate across each classroom's exams in this filter.</p>
            </div>
          </div>

          {/* Multi-metric profile radar */}
          <div className="card p-6">
            <h2 className="section-title mb-5">Classroom Profile Comparison</h2>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarProfileData}>
                <PolarGrid stroke="#2e2e42" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: '#3d3d55', fontSize: 11, fontFamily: 'DM Sans' }} />
                <Tooltip
                  contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: '#fff' }}
                />
                <Legend formatter={(v: any) => <span style={{ color: '#9ca3af', fontSize: 11 }}>{v}</span>} />
                {classroomStats.map((s, i) => (
                  <Radar
                    key={s.classroom_id}
                    name={s.classroom_name}
                    dataKey={s.classroom_name}
                    stroke={CLASSROOM_COLORS[i] ?? '#6366f1'}
                    fill={CLASSROOM_COLORS[i] ?? '#6366f1'}
                    fillOpacity={0.15}
                    strokeWidth={2}
                  />
                ))}
              </RadarChart>
            </ResponsiveContainer>
            <p className="text-xs text-muted mt-3">Consistency is 100 minus the average score spread (standard deviation) across exams — higher means more uniform results.</p>
          </div>

          {/* Exam-by-exam line chart */}
          {chartData.length > 0 && (
            <div className="card p-6">
              <h2 className="section-title mb-5">Average Score per Exam</h2>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                  <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                  <Tooltip
                    contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }}
                    labelStyle={{ color: '#fff', fontFamily: 'Syne' }}
                  />
                  <Legend formatter={(v: any) => <span style={{ color: '#9ca3af', fontSize: 11 }}>{v}</span>} />
                  {(compareData?.comparisons ?? []).map((c, i) => (
                    <Line
                      key={c.classroom_id}
                      type="monotone"
                      dataKey={c.classroom_name}
                      stroke={CLASSROOM_COLORS[i] ?? '#6366f1'}
                      strokeWidth={2.5}
                      dot={{ r: 4, strokeWidth: 0, fill: CLASSROOM_COLORS[i] ?? '#6366f1' }}
                      activeDot={{ r: 6 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {(compareData?.comparisons ?? []).map((c, i) => (
              <div key={c.classroom_id} className="card p-5" style={{ borderColor: (CLASSROOM_COLORS[i] ?? '#3d3d55') + '40' }}>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: CLASSROOM_COLORS[i] }} />
                  <h3 className="font-display font-semibold text-primary">{c.classroom_name}</h3>
                </div>
                <div className="flex items-end justify-between">
                  <div>
                    <p className="label">Overall Average</p>
                    <p className={`font-display font-bold text-2xl mt-1 ${gradeColor(c.overall_average ?? 0)}`}>
                      {c.overall_average != null ? `${c.overall_average}%` : '—'}
                    </p>
                  </div>
                  <p className="text-muted text-xs">{c.exam_summaries.length} exams</p>
                </div>
                <div className="mt-3 pt-3 border-t border-surface">
                  <div className="flex flex-col gap-1.5">
                    {c.exam_summaries.slice(0, 4).map(e => (
                      <div key={e.exam_id} className="flex justify-between text-xs">
                        <span className="text-secondary truncate max-w-[140px]">{e.exam_title}</span>
                        <span className={`font-mono font-bold ${gradeColor(e.average)}`}>{e.average}%</span>
                      </div>
                    ))}
                    {c.exam_summaries.length > 4 && (
                      <p className="text-secondary text-xs">+{c.exam_summaries.length - 4} more</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
