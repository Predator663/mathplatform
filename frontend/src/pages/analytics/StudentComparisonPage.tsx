import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, BarChart, Bar,
} from 'recharts';
import { GitCompare, Search, X, Download, ArrowUpRight, ArrowDownRight, Minus, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { analyticsApi, studentsApi, subjectsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Select } from '../../components/ui';
import { downloadBlob, gradeColor } from '../../utils';
import type { StudentComparisonResult, StudentProfile, PaginatedResponse, Subject } from '../../types';

const STUDENT_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#f43f5e', '#06b6d4'];

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'improving') return <ArrowUpRight size={14} className="text-emerald-400" />;
  if (trend === 'declining') return <ArrowDownRight size={14} className="text-rose-400" />;
  return <Minus size={14} className="text-secondary" />;
}

export default function StudentComparisonPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [selected, setSelected] = useState<StudentProfile[]>([]);
  const [query, setQuery] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [downloading, setDownloading] = useState(false);

  // Deep-link support: /analytics/compare-students?student_id=42 pre-seeds
  // the comparison with that student, so "Compare with another student"
  // on a student's own page can jump straight here with them already added.
  const seedStudentId = searchParams.get('student_id');
  const { data: seedStudent } = useQuery<StudentProfile>({
    queryKey: ['student', seedStudentId],
    queryFn: () => studentsApi.student(Number(seedStudentId)).then(r => r.data),
    enabled: !!seedStudentId,
  });
  useEffect(() => {
    if (seedStudent && !selected.some(s => s.id === seedStudent.id)) {
      setSelected(prev => [...prev, seedStudent]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedStudent]);

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
  });
  const subjects: Subject[] = Array.isArray(subjectsData) ? subjectsData : subjectsData?.results ?? [];

  const { data: searchResults } = useQuery<PaginatedResponse<StudentProfile> | StudentProfile[]>({
    queryKey: ['student-search', query],
    queryFn: () => studentsApi.students({ search: query, page_size: 8 }).then(r => r.data),
    enabled: query.length >= 2,
  });
  const results: StudentProfile[] = Array.isArray(searchResults) ? searchResults : searchResults?.results ?? [];
  const availableResults = results.filter(r => !selected.some(s => s.id === r.id));

  const addStudent = (s: StudentProfile) => {
    if (selected.length >= 6) { toast.error('You can compare up to 6 students at a time'); return; }
    setSelected(prev => [...prev, s]);
    setQuery('');
  };
  const removeStudent = (id: number) => setSelected(prev => prev.filter(s => s.id !== id));

  const studentIds = selected.map(s => s.id);
  const params = {
    student_ids: studentIds.join(','),
    subject_id: subjectFilter || undefined,
    include_quizzes: 'true',
  };

  const { data: comparison, isLoading, isError } = useQuery<StudentComparisonResult>({
    queryKey: ['student-comparison', studentIds, subjectFilter],
    queryFn: () => analyticsApi.compareStudents(params).then(r => r.data),
    enabled: studentIds.length >= 2,
  });

  const colorFor = (i: number) => STUDENT_COLORS[i % STUDENT_COLORS.length];

  // Trend chart: merge each student's timeline by exam sequence (#1, #2, ...), not calendar date.
  const trendData = useMemo(() => {
    const students = comparison?.students ?? [];
    const maxLen = Math.max(0, ...students.map(s => s.timeline.length));
    return Array.from({ length: maxLen }, (_, i) => {
      const row: Record<string, string | number> = { name: `#${i + 1}` };
      students.forEach(s => {
        if (s.timeline[i]) row[s.name] = s.timeline[i].percentage;
      });
      return row;
    });
  }, [comparison]);

  // Topic chart: union of topic names, one bar series per student.
  const topicData = useMemo(() => {
    const students = comparison?.students ?? [];
    const names: string[] = [];
    const seen = new Set<string>();
    students.forEach(s => s.topics.forEach(t => {
      if (!seen.has(t.topic_name)) { seen.add(t.topic_name); names.push(t.topic_name); }
    }));
    return names.map(name => {
      const row: Record<string, string | number> = { name };
      students.forEach(s => {
        const match = s.topics.find(t => t.topic_name === name);
        row[s.name] = match?.average ?? 0;
      });
      return row;
    });
  }, [comparison]);

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const res = await analyticsApi.compareStudentsPdf(params);
      downloadBlob(res.data as Blob, 'student_comparison.pdf');
      toast.success('PDF downloaded');
    } catch {
      toast.error('Could not generate the comparison PDF');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div>
        <h1 className="page-title flex items-center gap-2"><GitCompare className="text-azure-400" size={22} /> Compare Students</h1>
        <p className="text-muted mt-0.5">Side-by-side progress — a growth story to share with a student, not just a ranking.</p>
      </div>

      <div className="card p-4 flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          {selected.map((s, i) => (
            <span key={s.id} className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium"
              style={{ backgroundColor: `${colorFor(i)}22`, color: colorFor(i), border: `1px solid ${colorFor(i)}55` }}>
              {s.full_name}
              <button onClick={() => removeStudent(s.id)} className="hover:opacity-70"><X size={12} /></button>
            </span>
          ))}
        </div>

        {selected.length < 6 && (
          <div className="relative">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
            <input className="input pl-10 w-full" placeholder="Search a student to add to the comparison…"
              value={query} onChange={e => setQuery(e.target.value)} />
            {query.length >= 2 && availableResults.length > 0 && (
              <div className="absolute z-10 mt-1 w-full card p-1 max-h-56 overflow-y-auto">
                {availableResults.map(s => (
                  <button key={s.id} onClick={() => addStudent(s)}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-700 transition-colors text-sm">
                    <span className="text-primary font-medium">{s.full_name}</span>
                    <span className="text-secondary text-xs ml-2">{s.student_id} · {s.classroom_name ?? '—'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex items-end gap-3">
          <div className="w-56">
            <Select label="Subject (optional)"
              options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
              value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)} />
          </div>
          {comparison && comparison.students.length >= 2 && (
            <Button variant="secondary" size="sm" onClick={handleDownloadPdf} loading={downloading}>
              <Download size={14} /> Download PDF
            </Button>
          )}
        </div>
      </div>

      {studentIds.length < 2 ? (
        <EmptyState icon={<GitCompare size={36} />} title="Add at least 2 students"
          message="Search and add students above to see their progress side by side." />
      ) : isLoading ? (
        <LoadingPage />
      ) : isError || !comparison ? (
        <EmptyState icon={<GitCompare size={36} />} title="Couldn't load this comparison"
          message="Make sure you have access to all the selected students." />
      ) : (
        <>
          {/* Growth cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {comparison.students.map((s, i) => (
              <div key={s.student_id} className="card p-4 cursor-pointer hover:bg-surface-800/40 transition-colors"
                onClick={() => navigate(`/students/${s.student_id}`)}>
                <div className="flex items-center justify-between mb-2">
                  <p className="font-display font-semibold text-primary" style={{ color: colorFor(i) }}>{s.name}</p>
                  <TrendIcon trend={s.trend} />
                </div>
                <p className="text-xs text-secondary mb-2">{s.classroom ?? '—'}</p>
                {s.growth.delta != null ? (
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-xs text-secondary">{s.growth.first_pct}% → </span>
                    <span className={`font-mono font-bold ${gradeColor(s.growth.last_pct!)}`}>{s.growth.last_pct}%</span>
                    <span className={`text-xs font-bold ml-1 ${s.growth.delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      ({s.growth.delta >= 0 ? '+' : ''}{s.growth.delta} pts)
                    </span>
                  </div>
                ) : (
                  <p className="text-xs text-secondary">Not enough exams yet for a growth trend</p>
                )}
                {s.quiz_streak != null && s.quiz_streak > 0 && (
                  <p className="text-xs text-amber-400 mt-1.5">🔥 {s.quiz_streak}-day quiz streak</p>
                )}
              </div>
            ))}
          </div>

          {/* Trend chart */}
          <div className="card p-6">
            <h2 className="section-title mb-5 flex items-center gap-2"><Sparkles size={15} className="text-azure-400" /> Score Trend — Side by Side</h2>
            <p className="text-xs text-secondary -mt-3 mb-4">Each point is one exam, in the order that student took it.</p>
            {trendData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={trendData} margin={{ top: 5, right: 20, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                  <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                  <Tooltip contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }} labelStyle={{ color: '#fff' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {comparison.students.map((s, i) => (
                    <Line key={s.student_id} type="monotone" dataKey={s.name} stroke={colorFor(i)}
                      strokeWidth={2.5} dot={{ fill: colorFor(i), r: 4, strokeWidth: 0 }} connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-muted text-center py-12">Not enough exam data for a trend chart.</p>
            )}
          </div>

          {/* Topic chart */}
          <div className="card p-6">
            <h2 className="section-title mb-5">Topic Mastery — Side by Side</h2>
            {topicData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={topicData} margin={{ top: 5, right: 20, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                  <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 9, fontFamily: 'DM Sans' }} angle={-15} textAnchor="end" height={50} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                  <Tooltip contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }} labelStyle={{ color: '#fff' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {comparison.students.map((s, i) => (
                    <Bar key={s.student_id} dataKey={s.name} fill={colorFor(i)} radius={[4, 4, 0, 0]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-muted text-center py-12">No topic-tagged exam data recorded for these students yet.</p>
            )}
          </div>

          {/* Stats table */}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface">
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4"></th>
                    {comparison.students.map((s, i) => (
                      <th key={s.student_id} className="text-left py-3 px-4 font-display font-semibold" style={{ color: colorFor(i) }}>
                        {s.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: 'Exams Recorded', get: (s: typeof comparison.students[0]) => s.summary.total_exams },
                    { label: 'Overall Average', get: (s: typeof comparison.students[0]) => s.summary.average_percentage != null ? `${s.summary.average_percentage}%` : '—' },
                    { label: 'Pass Rate', get: (s: typeof comparison.students[0]) => `${s.summary.pass_rate}%` },
                    { label: 'Predicted NECTA Grade', get: (s: typeof comparison.students[0]) => s.summary.predicted_necta_grade ?? '—' },
                    { label: 'Badges Earned', get: (s: typeof comparison.students[0]) => s.badge_count ?? '—' },
                    { label: 'Quiz Streak', get: (s: typeof comparison.students[0]) => s.quiz_streak != null ? `${s.quiz_streak} days` : '—' },
                  ].map(row => (
                    <tr key={row.label} className="border-b border-surface last:border-0">
                      <td className="py-3 px-4 text-xs text-secondary font-medium">{row.label}</td>
                      {comparison.students.map(s => (
                        <td key={s.student_id} className="py-3 px-4 font-mono text-sm text-primary">{row.get(s)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
