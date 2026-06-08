import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileText, Download, FileSpreadsheet } from 'lucide-react';
import { studentsApi, examsApi } from '../../api';
import { Button, Select, Input, LoadingPage } from '../../components/ui';
import { downloadBlob, formatDate, EXAM_TYPE_LABELS, TERM_LABELS, gradeColor } from '../../utils';
import api from '../../api';
import toast from 'react-hot-toast';
import type { StudentProfile, Exam, PaginatedResponse } from '../../types';

type Tab = 'student' | 'exam' | 'class';
type SortBy = 'name' | 'score_desc' | 'score_asc' | 'grade' | 'student_id' | 'average_desc' | 'average_asc';
type ExportFormat = 'pdf' | 'excel' | 'csv';

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
  topic_analysis: { topics: { topic_id: number; topic_name: string; color: string; average: number; trend: string }[] };
}

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('exam');
  const [selectedStudent, setSelectedStudent] = useState('');
  const [selectedExam, setSelectedExam] = useState('');
  const [selectedClassroom, setSelectedClassroom] = useState('');
  const [sortBy, setSortBy] = useState<SortBy>('name');
  const [schoolName, setSchoolName] = useState('School of Excellence');
  const [reportData, setReportData] = useState<StudentReportData | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<ExportFormat | null>(null);

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
    { id: 'exam',    label: 'Exam Scores' },
    { id: 'class',   label: 'Class Report' },
    { id: 'student', label: 'Student Report' },
  ];

  const ExportButtons = ({ onExport }: { onExport: (fmt: ExportFormat) => void }) => (
    <div className="flex flex-wrap gap-2">
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
      <div className="card p-5 flex flex-wrap items-end gap-4">
        <div className="flex-1 min-w-48">
          <Input
            label="School Name (appears on all exports)"
            value={schoolName}
            onChange={e => setSchoolName(e.target.value)}
            placeholder="School of Excellence"
          />
        </div>
      </div>

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

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-surface">
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

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-surface">
            <p className="text-xs text-secondary">
              Includes exam overview table, student rankings, colour-coded averages.
            </p>
            <ExportButtons onExport={exportClass} />
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
                <Select
                  label="Select Student"
                  options={[
                    { value: '', label: 'Choose a student…' },
                    ...students.map(s => ({ value: s.id, label: `${s.full_name} (${s.student_id})` })),
                  ]}
                  value={selectedStudent}
                  onChange={e => { setSelectedStudent(e.target.value); setReportData(null); }}
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
  const { summary, topic_analysis } = data;
  return (
    <div className="flex flex-col gap-4">
      <div className="card p-6">
        <div className="flex items-start justify-between mb-5">
          <div>
            <h3 className="font-display font-bold text-xl text-primary">{summary.student_name}</h3>
            <p className="text-muted">{summary.student_code} · {summary.classroom}</p>
          </div>
          <div className="text-right">
            <p className="font-display font-bold text-3xl text-gradient">{summary.average_percentage}%</p>
            <p className="text-muted text-xs">Overall Average</p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 mb-5">
          {[
            { label: 'Exams Taken', value: summary.total_exams },
            { label: 'Pass Rate',   value: `${summary.pass_rate}%` },
            { label: 'Trend',       value: summary.trend },
          ].map(({ label, value }) => (
            <div key={label} className="bg-surface-900 rounded-xl p-3 text-center">
              <p className="text-xs text-secondary font-display uppercase tracking-widest">{label}</p>
              <p className="font-display font-bold text-primary mt-1 capitalize">{value}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-2">
          {summary.recent_scores?.map(score => (
            <div key={score.exam_id} className="flex items-center justify-between p-3 bg-surface-900 rounded-xl">
              <div>
                <p className="text-sm font-display font-medium text-primary">{score.exam_title}</p>
                <p className="text-xs text-secondary">{formatDate(score.exam_date)}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`font-mono text-sm font-bold ${gradeColor(score.percentage)}`}>
                  {score.score}/{score.max_score} ({score.percentage}%)
                </span>
                <span className={`badge ${score.passed ? 'badge-green' : 'badge-rose'}`}>{score.letter_grade}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {topic_analysis?.topics?.length > 0 && (
        <div className="card p-6">
          <p className="label mb-4">Topic Mastery</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {topic_analysis.topics.map(t => (
              <div key={t.topic_id} className="flex items-center gap-3 p-3 bg-surface-900 rounded-xl">
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: t.color }} />
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="font-display font-medium text-primary">{t.topic_name}</span>
                    <span className={`font-mono font-bold ${gradeColor(t.average)}`}>{t.average}%</span>
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
    </div>
  );
}
