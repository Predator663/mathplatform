import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FileText, Download, FileSpreadsheet, TrendingUp, TrendingDown, Minus, Loader2 } from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, PieChart, Pie, Cell,
  BarChart, Bar,
} from 'recharts';
import { studentsApi, examsApi } from '../../api';
import { Button, Select, LoadingPage, SearchableSelect } from '../../components/ui';
import { downloadBlob, formatDate, EXAM_TYPE_LABELS, TERM_LABELS, gradeColor } from '../../utils';
import { useSiteSettingsStore } from '../../store/siteSettings';
import api from '../../api';
import toast from 'react-hot-toast';
import type { StudentProfile, Exam, PaginatedResponse, TrendDataPoint } from '../../types';

type Tab = 'student' | 'exam' | 'class' | 'analytics';
type SortBy = 'name' | 'score_desc' | 'score_asc' | 'grade' | 'student_id' | 'average_desc' | 'average_asc';
type ExportFormat = 'pdf' | 'excel' | 'csv';

const GRADE_COLORS: Record<string, string> = {
  'A+': '#10b981', A: '#34d399', B: '#3b82f6', C: '#f59e0b', D: '#fb923c', F: '#f43f5e',
};

const SORT_OPTIONS_EXAM = [
  { value: 'name',       label: 'Sort by Name (A→Z)' },
  { value: 'score_desc', label: 'Sort by Score (High→Low)' },
  { value: 'score_asc',  label: 'Sort by Score (Low→High)' },
  { value: 'grade',      label: 'Sort by Grade' },
  { value: 'student_id', label: 'Sort by Student ID' },
];

const SORT_OPTIONS_CLASS = [
  { value: 'name',         label: 'Sort by Name (A→Z)' },
  { value: 'average_desc', label: 'Sort by Average (High→Low)' },
  { value: 'average_asc',  label: 'Sort by Average (Low→High)' },
  { value: 'student_id',   label: 'Sort by Student ID' },
];

interface StudentReportData {
  summary: {
    student_name: string; student_code: string; classroom: string;
    total_exams: number; average_percentage: number; pass_rate: number; trend: string;
    recent_scores: { exam_id: number; exam_title: string; exam_date: string; score: number; max_score: number; percentage: number; letter_grade: string; passed: boolean }[];
  };
  topic_analysis: { topics: { topic_id: number; topic_name: string; color: string; average: number; highest: number; lowest: number; attempts: number; trend: string }[] };
  trend: { timeline: TrendDataPoint[]; trend: string; trend_slope: number; moving_average: number[] };
}

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('exam');
  const [selectedStudent, setSelectedStudent] = useState('');
  const [selectedExam, setSelectedExam] = useState('');
  const [selectedClassroom, setSelectedClassroom] = useState('');
  const [sortBy, setSortBy] = useState<SortBy>('name');
  const { settings } = useSiteSettingsStore();
  const schoolName = settings.platform_name;
  const [reportData, setReportData] = useState<StudentReportData | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<ExportFormat | null>(null);
  const [analyticsClassroom, setAnalyticsClassroom] = useState('');
  const [analyticsYear, setAnalyticsYear]           = useState('');
  const [analyticsTerm, setAnalyticsTerm]           = useState('');
  const [analyticsExam, setAnalyticsExam]           = useState('');
  const [exportingAnalytics, setExportingAnalytics] = useState<'pdf' | 'excel' | null>(null);

  const { data: studentsData } = useQuery<PaginatedResponse<StudentProfile> | StudentProfile[]>({
    queryKey: ['students-all'],
    queryFn: () => studentsApi.students({ page_size: 200 }).then(r => r.data),
  });
  const students: StudentProfile[] = Array.isArray(studentsData)
    ? studentsData : (studentsData as PaginatedResponse<StudentProfile>)?.results ?? [];

  const { data: examsData } = useQuery<PaginatedResponse<Exam> | Exam[]>({
    queryKey: ['exams-all'],
    queryFn: () => examsApi.exams({ page_size: 200 }).then(r => r.data),
  });
  const exams: Exam[] = Array.isArray(examsData)
    ? examsData : (examsData as PaginatedResponse<Exam>)?.results ?? [];

  const { data: classroomsData } = useQuery<PaginatedResponse<{ id: number; name: string; grade_level_name: string; academic_year: string }> | { id: number; name: string; grade_level_name: string; academic_year: string }[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms = Array.isArray(classroomsData)
    ? classroomsData
    : (classroomsData as PaginatedResponse<{ id: number; name: string; grade_level_name: string; academic_year: string }>)?.results ?? [];

  const buildParams = () => new URLSearchParams({
    sort_by: sortBy,
    school_name: schoolName,
  }).toString();

  const exportExam = async (fmt: ExportFormat) => {
    if (!selectedExam) { toast.error('Select an exam first'); return; }
    setExportingFormat(fmt);
    const params = buildParams();
    try {
      const res = await api.get(`/reports/export/exam/${selectedExam}/${fmt}/?${params}`, { responseType: 'blob' });
      const exam = exams.find(e => String(e.id) === selectedExam);
      const name = exam?.title.replace(/\s+/g, '_').slice(0, 30) ?? `exam_${selectedExam}`;
      const ext = fmt === 'excel' ? 'xlsx' : fmt;
      downloadBlob(res.data as Blob, `${name}_scores.${ext}`);
      toast.success(`${fmt.toUpperCase()} downloaded`);
    } catch { toast.error('Export failed'); }
    finally { setExportingFormat(null); }
  };

  const exportClass = async (fmt: ExportFormat) => {
    if (!selectedClassroom) { toast.error('Select a classroom first'); return; }
    setExportingFormat(fmt);
    const params = buildParams();
    try {
      const res = await api.get(`/reports/export/classroom/${selectedClassroom}/${fmt}/?${params}`, { responseType: 'blob' });
      const cls = classrooms.find(c => String(c.id) === selectedClassroom);
      const name = cls?.name.replace(/\s+/g, '_').slice(0, 30) ?? `class_${selectedClassroom}`;
      const ext = fmt === 'excel' ? 'xlsx' : fmt;
      downloadBlob(res.data as Blob, `${name}_report.${ext}`);
      toast.success(`${fmt.toUpperCase()} downloaded`);
    } catch { toast.error('Export failed'); }
    finally { setExportingFormat(null); }
  };

  const exportStudent = async (fmt: ExportFormat) => {
    if (!selectedStudent) { toast.error('Select a student first'); return; }
    setExportingFormat(fmt);
    try {
      const res = await api.get(
        `/reports/export/student/${selectedStudent}/${fmt}/?${buildParams()}`,
        { responseType: 'blob' }
      );
      const s = students.find(s => String(s.id) === selectedStudent);
      const name = s?.full_name.replace(/\s+/g, '_').slice(0, 30) ?? `student_${selectedStudent}`;
      const ext = fmt === 'excel' ? 'xlsx' : fmt;
      downloadBlob(res.data as Blob, `${name}_report.${ext}`);
      toast.success(`${fmt.toUpperCase()} downloaded`);
    } catch { toast.error('Export failed'); }
    finally { setExportingFormat(null); }
  };

  const exportAnalytics = async (fmt: 'pdf' | 'excel') => {
    if (!analyticsClassroom) { toast.error('Select a classroom first'); return; }
    setExportingAnalytics(fmt);
    try {
      const params = new URLSearchParams();
      if (analyticsExam)  params.set('exam_id', analyticsExam);
      if (!analyticsExam && analyticsYear) params.set('academic_year', analyticsYear);
      if (!analyticsExam && analyticsTerm) params.set('term', analyticsTerm);
      const qs = params.toString() ? `?${params}` : '';
      const res = await api.get(
        `/reports/export/classroom/${analyticsClassroom}/analytics/${fmt}/${qs}`,
        { responseType: 'blob' }
      );
      const cls = classrooms.find(c => String(c.id) === analyticsClassroom);
      const name = (cls?.name ?? `classroom_${analyticsClassroom}`).replace(/\s+/g, '_').slice(0, 30);
      const ext = fmt === 'excel' ? 'xlsx' : 'pdf';
      downloadBlob(res.data as Blob, `analytics_${name}.${ext}`);
      toast.success(`${fmt.toUpperCase()} downloaded`);
    } catch (err: any) {
      // When responseType:'blob', error body is also a Blob — parse it
      let msg = err?.message ?? 'Export failed';
      try {
        const blob = err?.response?.data;
        if (blob instanceof Blob) {
          const text = await blob.text();
          const parsed = JSON.parse(text);
          msg = parsed?.detail ?? msg;
        } else if (err?.response?.data?.detail) {
          msg = err.response.data.detail;
        }
      } catch { /* ignore parse errors */ }
      toast.error(msg);
      console.error('Analytics export error:', err?.response?.status, msg, err);
    } finally { setExportingAnalytics(null); }
  };

  const loadStudentReport = async () => {
    if (!selectedStudent) { toast.error('Select a student'); return; }
    setLoadingReport(true);
    try {
      const res = await api.get(`/reports/student/${selectedStudent}/`);
      setReportData(res.data as StudentReportData);
    } catch { toast.error('Failed to load report'); }
    finally { setLoadingReport(false); }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'exam',      label: 'Exam Scores' },
    { id: 'class',     label: 'Class Report' },
    { id: 'analytics', label: 'All-Subjects Analytics' },
    { id: 'student',   label: 'Student Report' },
  ];

  const ExportButtons = ({ onExport }: { onExport: (fmt: ExportFormat) => void }) => (
    <div className="flex gap-2">
      <Button
        variant="secondary" size="sm"
        loading={exportingFormat === 'pdf'}
        onClick={() => onExport('pdf')}
      >
        <FileText size={13} /> PDF
      </Button>
      <Button
        variant="secondary" size="sm"
        loading={exportingFormat === 'excel'}
        onClick={() => onExport('excel')}
      >
        <FileSpreadsheet size={13} /> Excel
      </Button>
      <Button
        variant="secondary" size="sm"
        loading={exportingFormat === 'csv'}
        onClick={() => onExport('csv')}
      >
        <Download size={13} /> CSV
      </Button>
    </div>
  );

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div>
        <h1 className="page-title">Reports & Exports</h1>
        <p className="text-muted mt-1">Generate PDF, Excel, and CSV reports sorted as needed.</p>
      </div>

      {/* Global settings */}
      <div className="card p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="label">Report Header</p>
          <p className="font-display font-semibold text-primary mt-0.5">{schoolName}</p>
        </div>
        <Link to="/settings" className="text-xs text-azure-400 hover:text-azure-300 transition-colors">
          Change in Settings →
        </Link>
      </div>
      <p className="text-xs text-muted -mt-2">
        This name is pulled from the Settings page and appears on every PDF, Excel, and CSV report.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-900 p-1 rounded-xl w-fit">
        {tabs.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => { setActiveTab(id); setReportData(null); }}
            className={`px-4 py-2 rounded-lg text-sm font-display font-medium transition-all ${
              activeTab === id ? 'bg-surface-700 text-primary shadow' : 'text-secondary hover:text-primary'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Exam Scores ──────────────────────────────────────────────────────── */}
      {activeTab === 'exam' && (
        <div className="card p-6 flex flex-col gap-5">
          <h2 className="section-title">Exam Score Report</h2>
          <p className="text-muted text-sm">Export all student scores for an exam, sorted and formatted.</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Select Exam"
              options={[
                { value: '', label: 'Choose an exam…' },
                ...exams.map(e => ({
                  value: e.id,
                  label: `${e.title} (${EXAM_TYPE_LABELS[e.exam_type]} · ${formatDate(e.exam_date)})`,
                })),
              ]}
              value={selectedExam}
              onChange={e => setSelectedExam(e.target.value)}
            />
            <Select
              label="Sort Order"
              options={SORT_OPTIONS_EXAM}
              value={sortBy}
              onChange={e => setSortBy(e.target.value as SortBy)}
            />
          </div>

          {selectedExam && (
            <div className="bg-surface-900 rounded-xl p-3">
              {(() => {
                const e = exams.find(ex => String(ex.id) === selectedExam);
                if (!e) return null;
                return (
                  <div className="flex flex-wrap gap-3 text-xs">
                    <span className="text-secondary">Term: <b className="text-primary">{TERM_LABELS[e.term]}</b></span>
                    <span className="text-secondary">Max: <b className="text-primary">{e.max_score}</b></span>
                    <span className="text-secondary">Pass: <b className="text-primary">{e.passing_score}</b></span>
                    <span className="text-secondary">Year: <b className="text-primary">{e.academic_year}</b></span>
                    {e.average_score != null && <span className="text-secondary">Avg: <b className="text-primary">{e.average_score}%</b></span>}
                    {e.pass_rate != null && <span className="text-secondary">Pass rate: <b className="text-primary">{e.pass_rate}%</b></span>}
                  </div>
                );
              })()}
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-surface">
            <p className="text-xs text-secondary">
              PDF includes school header, footer with {schoolName}, page numbers & generated date.
            </p>
            <ExportButtons onExport={exportExam} />
          </div>
        </div>
      )}

      {/* ── Class Report ─────────────────────────────────────────────────────── */}
      {activeTab === 'class' && (
        <div className="card p-6 flex flex-col gap-5">
          <h2 className="section-title">Class Performance Report</h2>
          <p className="text-muted text-sm">Full class matrix — one row per student, one column per exam.</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Select Classroom"
              options={[
                { value: '', label: 'Choose a classroom…' },
                ...classrooms.map(c => ({
                  value: c.id,
                  label: `${c.name} — ${c.grade_level_name} (${c.academic_year})`,
                })),
              ]}
              value={selectedClassroom}
              onChange={e => setSelectedClassroom(e.target.value)}
            />
            <Select
              label="Sort Order"
              options={SORT_OPTIONS_CLASS}
              value={sortBy}
              onChange={e => setSortBy(e.target.value as SortBy)}
            />
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-surface">
            <p className="text-xs text-secondary">
              Includes exam overview table, student rankings, colour-coded averages.
            </p>
            <ExportButtons onExport={exportClass} />
          </div>
        </div>
      )}

      {/* ── All-Subjects Analytics Report ─────────────────────────────────── */}
      {activeTab === 'analytics' && (
        <div className="card p-6 flex flex-col gap-5 relative">
          {/* ── Full-screen loading overlay during export ── */}
          {exportingAnalytics && (
            <div className="absolute inset-0 z-20 rounded-xl bg-surface-900/80 backdrop-blur-sm flex flex-col items-center justify-center gap-3">
              <Loader2 size={36} className="animate-spin text-azure-400" />
              <p className="text-sm font-medium text-primary">
                Generating {exportingAnalytics.toUpperCase()} report…
              </p>
              <p className="text-xs text-secondary">This may take a few seconds</p>
            </div>
          )}
          <div>
            <h2 className="section-title">All-Subjects Analytics Report</h2>
            <p className="text-muted text-sm mt-1">
              NECTA-style report — full student marks table (Page 1) + subject summary,
              division table, class GPA, best &amp; worst 10 students (Page 2).
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Select Classroom *"
              options={[
                { value: '', label: 'Choose a classroom…' },
                ...classrooms.map(c => ({
                  value: c.id,
                  label: `${c.name} — ${c.grade_level_name} (${c.academic_year})`,
                })),
              ]}
              value={analyticsClassroom}
              onChange={e => { setAnalyticsClassroom(e.target.value); setAnalyticsExam(''); }}
            />
            <Select
              label="Specific Exam (optional — overrides year/term)"
              options={[
                { value: '', label: analyticsClassroom ? 'All exams in classroom' : 'Select classroom first' },
                ...(analyticsClassroom
                  ? exams
                      .filter(ex =>
                        ex.classrooms.some((c: any) => String(c.id ?? c) === analyticsClassroom)
                      )
                      .map(ex => ({
                        value: ex.id,
                        label: `${ex.title} — ${ex.subject_name ?? ''} (${ex.term?.replace('_',' ').toUpperCase()})`,
                      }))
                  : []),
              ]}
              value={analyticsExam}
              onChange={e => setAnalyticsExam(e.target.value)}
            />
          </div>

          {!analyticsExam && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Select
                label="Academic Year (optional)"
                options={[
                  { value: '', label: 'All years' },
                  ...Array.from(new Set(classrooms.map(c => c.academic_year)))
                    .sort().reverse()
                    .map(y => ({ value: y, label: y })),
                ]}
                value={analyticsYear}
                onChange={e => setAnalyticsYear(e.target.value)}
              />
              <Select
                label="Term (optional)"
                options={[
                  { value: '',       label: 'All terms' },
                  { value: 'term_1', label: 'Term I (Jan–Apr)' },
                  { value: 'term_2', label: 'Term II (May–Aug)' },
                  { value: 'term_3', label: 'Term III (Sep–Dec)' },
                  { value: 'annual', label: 'Annual' },
                ]}
                value={analyticsTerm}
                onChange={e => setAnalyticsTerm(e.target.value)}
              />
            </div>
          )}

          <div className="rounded-xl border border-surface-700 bg-surface-900 p-4 text-sm text-secondary space-y-1">
            <p className="font-semibold text-primary text-xs uppercase tracking-wide mb-2">Report includes</p>
            <p>• <strong>Page 1 — Student Marks Table</strong>: SN, Reg No, Name, score &amp; grade per subject, average, division, position</p>
            <p>• <strong>Page 2 — Subject Summary</strong>: grade counts (A/B/C/D/F), seats, average, GPA &amp; competency per subject</p>
            <p>• <strong>Page 2 — Division Summary</strong>: student breakdown by division (I / II / III / IV / 0)</p>
            <p>• <strong>Page 2 — Top 10 Best</strong> and <strong>Top 10 Worst</strong> students</p>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-surface">
            <p className="text-xs text-secondary">
              Landscape A4 PDF · Excel workbook with full formatting
            </p>
            <div className="flex gap-2">
              <Button
                variant="secondary" size="sm"
                loading={exportingAnalytics === 'pdf'}
                disabled={!analyticsClassroom || exportingAnalytics !== null}
                onClick={() => exportAnalytics('pdf')}
              >
                <FileText size={13} /> PDF
              </Button>
              <Button
                variant="secondary" size="sm"
                loading={exportingAnalytics === 'excel'}
                disabled={!analyticsClassroom || exportingAnalytics !== null}
                onClick={() => exportAnalytics('excel')}
              >
                <FileSpreadsheet size={13} /> Excel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Student Report ───────────────────────────────────────────────────── */}
      {activeTab === 'student' && (
        <div className="flex flex-col gap-4">
          <div className="card p-6 flex flex-col gap-4">
            <h2 className="section-title">Student Report Card</h2>
            <div className="flex gap-3 items-end flex-wrap">
              <div className="flex-1 min-w-56">
                <SearchableSelect
                  label="Select Student"
                  placeholder="Choose a student…"
                  searchPlaceholder="Search by name or ID…"
                  options={students.map(s => ({
                    value: s.id, label: s.full_name, sublabel: s.student_id,
                  }))}
                  value={selectedStudent}
                  onChange={value => { setSelectedStudent(value); setReportData(null); }}
                />
              </div>
              <Button onClick={loadStudentReport} loading={loadingReport}>
                <FileText size={14} /> Preview
              </Button>
              {selectedStudent && (
                <ExportButtons onExport={exportStudent} />
              )}
            </div>
          </div>

          {loadingReport && <LoadingPage />}

          {reportData && (
            <StudentReportPreview data={reportData} />
          )}
        </div>
      )}
    </div>
  );
}

function StudentReportPreview({ data }: { data: StudentReportData }) {
  const { summary, topic_analysis, trend } = data;

  const chartData = (trend?.timeline ?? []).map((t, i) => ({
    name: formatDate(t.exam_date).slice(0, 6),
    fullTitle: t.exam_title,
    percentage: t.percentage,
    movingAvg: trend?.moving_average?.[i] ?? null,
  }));

  const topicBarData = (topic_analysis?.topics ?? [])
    .map(t => ({ topic: t.topic_name.length > 12 ? t.topic_name.slice(0, 12) + '…' : t.topic_name, average: t.average, color: t.color }))
    .sort((a, b) => a.average - b.average);

  const gradeCounts: Record<string, number> = {};
  for (const t of trend?.timeline ?? []) {
    gradeCounts[t.letter_grade] = (gradeCounts[t.letter_grade] ?? 0) + 1;
  }
  const gradeData = Object.entries(gradeCounts).map(([grade, count]) => ({ grade, count }));

  const TrendIcon = summary.trend === 'improving' ? TrendingUp : summary.trend === 'declining' ? TrendingDown : Minus;
  const trendTone = summary.trend === 'improving' ? 'text-emerald-400' : summary.trend === 'declining' ? 'text-rose-400' : 'text-secondary';

  return (
    <div className="flex flex-col gap-4">
      <div className="card p-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-5">
          <div className="min-w-0">
            <h3 className="font-display font-bold text-xl text-primary break-words">{summary.student_name}</h3>
            <p className="text-muted">{summary.student_code} · {summary.classroom}</p>
          </div>
          <div className="text-left sm:text-right flex-shrink-0">
            <p className="font-display font-bold text-3xl text-gradient">{summary.average_percentage}%</p>
            <p className="text-muted text-xs">Overall Average</p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
          {[
            { label: 'Exams Taken', value: summary.total_exams },
            { label: 'Pass Rate',   value: `${summary.pass_rate}%` },
            { label: 'Trend',       value: summary.trend },
          ].map(({ label, value }) => (
            <div key={label} className="bg-surface-900 rounded-xl p-3 text-center">
              <p className="text-xs text-secondary font-display uppercase tracking-widest">{label}</p>
              {label === 'Trend' ? (
                <p className={`font-display font-bold mt-1 capitalize flex items-center justify-center gap-1 ${trendTone}`}>
                  <TrendIcon size={14} /> {value}
                </p>
              ) : (
                <p className="font-display font-bold text-primary mt-1 capitalize">{value}</p>
              )}
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-2">
          {summary.recent_scores?.map(score => (
            <div key={score.exam_id} className="flex flex-wrap items-center justify-between gap-2 p-3 bg-surface-900 rounded-xl">
              <div className="min-w-0">
                <p className="text-sm font-display font-medium text-primary break-words">{score.exam_title}</p>
                <p className="text-xs text-secondary">{formatDate(score.exam_date)}</p>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className={`font-mono text-sm font-bold ${gradeColor(score.percentage)}`}>
                  {score.score}/{score.max_score} ({score.percentage}%)
                </span>
                <span className={`badge ${score.passed ? 'badge-green' : 'badge-rose'}`}>{score.letter_grade}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Score trend chart */}
      <div className="card p-5">
        <h2 className="section-title mb-4">Score Trend Over Time</h2>
        {chartData.length > 1 ? (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ top: 5, right: 8, bottom: 0, left: -22 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Tooltip
                  formatter={(v: any, name: any) => [`${v}%`, (name === 'percentage' ? 'Score' : 'Moving Avg')] as [string, string]}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullTitle ?? ''}
                />
                <ReferenceLine y={50} stroke="#f43f5e" strokeDasharray="4 4" strokeOpacity={0.5}
                  label={{ value: 'Pass mark', fill: '#f43f5e', fontSize: 9 }} />
                <Line type="monotone" dataKey="percentage" stroke="#3b82f6" strokeWidth={2.5}
                  dot={{ fill: '#3b82f6', r: 3.5, strokeWidth: 0 }} activeDot={{ r: 5 }} name="percentage" />
                <Line type="monotone" dataKey="movingAvg" stroke="#a78bfa" strokeWidth={1.5}
                  strokeDasharray="5 3" dot={false} name="movingAvg" />
              </LineChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap items-center gap-4 mt-3 pl-1">
              <div className="flex items-center gap-1.5">
                <div className="w-5 h-0.5 bg-azure-500 rounded-full" />
                <span className="text-xs text-secondary">Score %</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-5 h-px border-t-2 border-dashed border-violet-400" />
                <span className="text-xs text-secondary">3-exam moving average</span>
              </div>
            </div>
          </>
        ) : (
          <div className="h-44 flex items-center justify-center text-muted text-sm">Not enough exams yet for a trend chart</div>
        )}
      </div>

      {/* Topic mastery + grade distribution */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="card p-5">
          <h2 className="section-title mb-4">Topic Averages</h2>
          {topicBarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={Math.max(160, topicBarData.length * 34)}>
              <BarChart data={topicBarData} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="topic" width={90} tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v: any) => [`${v}%`, 'Average'] as [string, string]} />
                <ReferenceLine x={50} stroke="#f43f5e" strokeDasharray="4 4" strokeOpacity={0.5} />
                <Bar dataKey="average" radius={[0, 4, 4, 0]} barSize={16}>
                  {topicBarData.map(t => <Cell key={t.topic} fill={t.color || '#6366f1'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex items-center justify-center text-muted text-sm">No topic data yet</div>
          )}
        </div>

        <div className="card p-5">
          <h2 className="section-title mb-4">Grade Distribution</h2>
          {gradeData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={gradeData} dataKey="count" nameKey="grade" innerRadius={46} outerRadius={72} paddingAngle={2}>
                    {gradeData.map(g => <Cell key={g.grade} fill={GRADE_COLORS[g.grade] ?? '#6366f1'} stroke="none" />)}
                  </Pie>
                  <Tooltip formatter={(v: any, _n: any, p: any) => [`${v} exam(s)`, `Grade ${p?.payload?.grade}`] as [string, string]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap justify-center gap-2 mt-2">
                {gradeData.map(g => (
                  <div key={g.grade} className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: GRADE_COLORS[g.grade] ?? '#6366f1' }} />
                    <span className="text-xs text-secondary">
                      {g.grade} <span className="font-mono text-primary font-medium">{g.count}</span>
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-44 flex items-center justify-center text-muted text-sm">No graded exams yet</div>
          )}
        </div>
      </div>

      {topic_analysis?.topics?.length > 0 && (
        <div className="card p-6">
          <p className="label mb-4">Topic Mastery — Detail</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {topic_analysis.topics.map(t => (
              <div key={t.topic_id} className="flex items-center gap-3 p-3 bg-surface-900 rounded-xl">
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: t.color }} />
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between text-xs mb-1.5 gap-2">
                    <span className="font-display font-medium text-primary truncate">{t.topic_name}</span>
                    <span className={`font-mono font-bold flex-shrink-0 ${gradeColor(t.average)}`}>{t.average}%</span>
                  </div>
                  <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${t.average}%`, backgroundColor: t.color }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-muted text-center">
        This preview mirrors the full A4 PDF report — export it above for printable charts, term breakdown & insights.
      </p>
    </div>
  );
}
