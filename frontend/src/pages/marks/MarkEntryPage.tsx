import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, Check, WifiOff, Download, Search } from 'lucide-react';
import toast from 'react-hot-toast';
import { examsApi, studentsApi } from '../../api';
import { LoadingPage, Button, Select } from '../../components/ui';
import { gradeBg, gradeColor, EXAM_TYPE_LABELS, TERM_LABELS, downloadBlob } from '../../utils';
import { useSync } from '../../hooks/usePWASync';
import type { Exam, ExamScore, StudentProfile, Classroom, PaginatedResponse } from '../../types';

interface ScoreRow {
  student: StudentProfile;
  score: string;
  is_absent: boolean;
  remarks: string;
  saved: boolean;
  error: string;
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export default function MarkEntryPage() {
  const { id } = useParams<{ id: string }>();
  const examId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isOnline, queueScore } = useSync();

  const [rows, setRows]               = useState<ScoreRow[]>([]);
  const [searchText, setSearchText]   = useState('');
  const [filterClass, setFilterClass] = useState('');
  const [saveStatus, setSaveStatus]   = useState<SaveStatus>('idle');
  const [autoSave, setAutoSave]       = useState(true);
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dirtyRef = useRef(false);

  const { data: exam, isLoading: l1 } = useQuery<Exam>({
    queryKey: ['exam', examId],
    queryFn: () => examsApi.exam(examId).then(r => r.data),
  });

  const { data: existingScores } = useQuery<ExamScore[]>({
    queryKey: ['exam-scores', examId],
    queryFn: () => examsApi.examScores(examId).then(r => r.data),
  });

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data: studentsData, isLoading: l2 } = useQuery<PaginatedResponse<StudentProfile> | StudentProfile[]>({
    queryKey: ['exam-students', examId, exam?.classrooms],
    queryFn: async () => {
      if (!exam?.classrooms?.length) return [];
      const all: StudentProfile[] = [];
      for (const cid of exam.classrooms) {
        const res = await studentsApi.classroomStudents(cid);
        all.push(...(res.data as StudentProfile[]));
      }
      return all;
    },
    enabled: !!exam,
  });
  const students: StudentProfile[] = Array.isArray(studentsData)
    ? studentsData : (studentsData as PaginatedResponse<StudentProfile>)?.results ?? [];

  useEffect(() => {
    if (!students.length) return;
    const scoreMap = new Map<number, ExamScore>();
    (existingScores ?? []).forEach(s => scoreMap.set(s.student, s));
    setRows(students.map(s => {
      const ex = scoreMap.get(s.id);
      return {
        student: s,
        score: ex && !ex.is_absent ? String(ex.score) : '',
        is_absent: ex?.is_absent ?? false,
        remarks: ex?.remarks ?? '',
        saved: !!ex,
        error: '',
      };
    }));
  }, [students, existingScores]);

  const updateRow = useCallback((studentId: number, field: keyof ScoreRow, value: string | boolean) => {
    setRows(prev => prev.map(r =>
      r.student.id === studentId ? { ...r, [field]: value, saved: false, error: '' } : r
    ));
    dirtyRef.current = true;
    if (autoSave) {
      if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
      autoSaveTimer.current = setTimeout(() => { saveAll(true); }, 1500);
    }
  }, [autoSave]);

  const saveAll = useCallback(async (silent = false) => {
    if (!exam) return;
    setSaveStatus('saving');

    const payload = rows
      .filter(r => r.is_absent || (r.score !== '' && !isNaN(parseFloat(r.score))))
      .map(r => ({
        student_id: r.student.student_id,
        score: r.is_absent ? 0 : parseFloat(r.score),
        is_absent: r.is_absent,
        remarks: r.remarks,
      }));

    if (payload.length === 0) { setSaveStatus('idle'); return; }

    if (!isOnline) {
      for (const item of payload) {
        await queueScore({
          exam_id: exam.id,
          student_id_code: item.student_id,
          score: item.score,
          is_absent: item.is_absent,
          remarks: item.remarks,
        });
      }
      setRows(prev => prev.map(r => ({ ...r, saved: true })));
      setSaveStatus('saved');
      if (!silent) toast('Queued offline — will sync when back online', { icon: '📡' });
      setTimeout(() => setSaveStatus('idle'), 3000);
      return;
    }

    try {
      const res = await examsApi.bulkScores(exam.id, { scores: payload });
      const data = res.data as { created: number; updated: number; errors: { student_id: string; error: string }[] };
      const errorMap = new Map((data.errors ?? []).map((e: { student_id: string; error: string }) => [e.student_id, e.error]));

      setRows(prev => prev.map(r => ({
        ...r,
        saved: !errorMap.has(r.student.student_id),
        error: errorMap.get(r.student.student_id) ?? '',
      })));

      queryClient.invalidateQueries({ queryKey: ['exam-scores', examId] });
      queryClient.invalidateQueries({ queryKey: ['exam-stats', examId] });
      setSaveStatus('saved');

      if (!silent) {
        const total = data.created + data.updated;
        toast.success(`Saved ${total} score${total !== 1 ? 's' : ''}${data.errors?.length ? ` (${data.errors.length} errors)` : ''}`);
      }
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch {
      setSaveStatus('error');
      if (!silent) toast.error('Failed to save scores');
    }
  }, [rows, exam, examId, isOnline, queueScore, queryClient]);

  const downloadTemplate = async () => {
    if (!exam) return;
    try {
      const res = await examsApi.scoresTemplate(examId);
      downloadBlob(res.data as Blob, `scores_template_${examId}.csv`);
    } catch { toast.error('Download failed'); }
  };

  const filteredRows = rows.filter(r => {
    const matchSearch = !searchText ||
      r.student.full_name.toLowerCase().includes(searchText.toLowerCase()) ||
      r.student.student_id.toLowerCase().includes(searchText.toLowerCase());
    const matchClass = !filterClass || String(r.student.classroom) === filterClass;
    return matchSearch && matchClass;
  });

  const totalEntered = rows.filter(r => r.is_absent || (r.score !== '' && !isNaN(parseFloat(r.score)))).length;

  if (l1 || l2) return <LoadingPage />;
  if (!exam) return <div className="text-muted p-4">Exam not found.</div>;

  return (
    <div className="flex flex-col gap-4 page-enter">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <button onClick={() => navigate(`/exams/${examId}`)} className="text-secondary hover:text-primary text-sm transition-colors mb-1">
            ← {exam.title}
          </button>
          <h1 className="page-title">Mark Entry</h1>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-muted text-sm">{totalEntered}/{rows.length} entered</span>
            {!isOnline && (
              <span className="flex items-center gap-1 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded-full">
                <WifiOff size={11} /> Offline — queuing
              </span>
            )}
            {saveStatus === 'saving' && <span className="text-xs text-azure-400 animate-pulse">Saving…</span>}
            {saveStatus === 'saved'  && <span className="text-xs text-emerald-400 flex items-center gap-1"><Check size={11} /> Saved</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <label className="flex items-center gap-1.5 text-xs text-secondary cursor-pointer select-none">
            <input type="checkbox" checked={autoSave} onChange={e => setAutoSave(e.target.checked)} className="rounded accent-azure-500" />
            Auto-save
          </label>
          <Button variant="secondary" size="sm" onClick={downloadTemplate}><Download size={13} /> Template</Button>
          <Button size="sm" onClick={() => saveAll()} loading={saveStatus === 'saving'}><Save size={13} /> Save All</Button>
        </div>
      </div>

      {/* Progress */}
      <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
        <div className="h-full bg-gradient-to-r from-azure-500 to-emerald-500 rounded-full transition-all duration-500"
          style={{ width: rows.length ? `${(totalEntered / rows.length) * 100}%` : '0%' }} />
      </div>

      {/* Exam meta + filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-44">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary" />
          <input className="input pl-9 text-sm w-full" placeholder="Search student…"
            value={searchText} onChange={e => setSearchText(e.target.value)} />
        </div>
        {classrooms.length > 1 && (
          <Select className="w-40" options={[
            { value: '', label: 'All Classes' },
            ...classrooms.map(c => ({ value: c.id, label: c.name })),
          ]} value={filterClass} onChange={e => setFilterClass(e.target.value)} />
        )}
        <div className="text-xs text-secondary font-mono bg-surface-900 rounded-xl px-3 py-2 whitespace-nowrap">
          Max: <b className="text-primary">{exam.max_score}</b> · Pass: <b className="text-primary">{exam.passing_score}</b>
        </div>
      </div>

      {/* Score table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead>
              <tr className="border-b border-surface">
                {['#', 'Student', 'Score', '%  Grade', 'Absent', 'Remarks', '✓'].map(h => (
                  <th key={h} className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-3 whitespace-nowrap first:pl-4 last:pr-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row, idx) => {
                const scoreNum = parseFloat(row.score);
                const valid = !isNaN(scoreNum) && scoreNum >= 0 && scoreNum <= Number(exam.max_score);
                const pct = valid ? Math.round((scoreNum / Number(exam.max_score)) * 100) : null;
                const grade = pct !== null
                  ? pct >= 75 ? 'A' : pct >= 65 ? 'B' : pct >= 50 ? 'C' : pct >= 30 ? 'D' : 'F'
                  : null;

                return (
                  <tr key={row.student.id}
                    className={`border-b border-surface transition-colors ${
                      row.is_absent ? 'bg-rose-500/5' : row.saved ? 'bg-emerald-500/5' : 'hover:bg-surface-700/40'
                    }`}>
                    <td className="py-2.5 pl-4 pr-2 text-secondary text-xs font-mono w-8">{idx + 1}</td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0">
                          {row.student.first_name?.[0]}{row.student.last_name?.[0]}
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-primary text-xs leading-tight truncate">{row.student.full_name}</p>
                          <p className="text-[10px] text-secondary font-mono">{row.student.student_id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 w-24">
                      <input
                        type="number" min={0} max={Number(exam.max_score)} step={0.5}
                        disabled={row.is_absent}
                        className={`w-20 input rounded-lg px-2 py-1.5 text-sm font-mono text-center focus:outline-none focus:ring-2 transition-all ${
                          row.error ? 'border-rose-500/60 focus:ring-rose-500/30 text-rose-400'
                          : row.saved && !row.is_absent ? 'border-emerald-500/40 focus:ring-emerald-500/30 text-emerald-400'
                          : 'border-surface focus:ring-azure-500/40 text-primary'
                        } disabled:opacity-40`}
                        value={row.is_absent ? '' : row.score}
                        placeholder={row.is_absent ? 'ABS' : '0'}
                        onChange={e => updateRow(row.student.id, 'score', e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter' || (e.key === 'Tab' && !e.shiftKey)) {
                            e.preventDefault();
                            const next = filteredRows.findIndex(r => r.student.id === row.student.id) + 1;
                            if (next < filteredRows.length) {
                              document.querySelectorAll<HTMLInputElement>('input[type="number"]')[next]?.focus();
                            }
                          }
                        }}
                      />
                    </td>
                    <td className="py-2.5 px-3 w-24">
                      {row.is_absent
                        ? <span className="text-xs text-rose-400">Absent</span>
                        : pct !== null && grade
                          ? <span className={`font-mono text-sm font-bold ${gradeColor(pct)}`}>{pct}% <span className="text-xs opacity-70">{grade}</span></span>
                          : <span className="text-secondary text-xs">—</span>}
                    </td>
                    <td className="py-2.5 px-3 w-20">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" checked={row.is_absent}
                          onChange={e => {
                            updateRow(row.student.id, 'is_absent', e.target.checked);
                            if (e.target.checked) updateRow(row.student.id, 'score', '');
                          }}
                          className="w-3.5 h-3.5 rounded accent-rose-500" />
                        <span className="text-xs text-secondary">Abs</span>
                      </label>
                    </td>
                    <td className="py-2.5 px-3">
                      <input type="text" className="bg-surface-900 border border-surface rounded-lg px-2 py-1 text-xs text-secondary w-24 focus:outline-none focus:border-surface focus:text-primary"
                        placeholder="Note…" value={row.remarks}
                        onChange={e => updateRow(row.student.id, 'remarks', e.target.value)} />
                    </td>
                    <td className="py-2.5 pr-4 pl-3 w-6">
                      {row.error
                        ? <span className="text-rose-400 text-xs" title={row.error}>!</span>
                        : row.saved
                          ? <Check size={13} className="text-emerald-400" />
                          : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {filteredRows.length === 0 && (
            <div className="py-12 text-center text-muted text-sm">No students found for this exam.</div>
          )}
        </div>
      </div>

      {/* Sticky bottom bar */}
      <div className="sticky bottom-20 lg:bottom-4 flex items-center justify-between bg-surface-800/95 backdrop-blur border border-surface rounded-2xl px-4 py-3 shadow-2xl">
        <div className="text-sm text-secondary">
          <span className="text-primary font-display font-semibold">{totalEntered}</span>
          {' '}of{' '}
          <span className="text-primary font-semibold">{rows.length}</span>
          {' '}entered
          {!isOnline && <span className="ml-2 text-rose-400 text-xs">· offline queue</span>}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => navigate(`/exams/${examId}`)}>Done</Button>
          <Button size="sm" onClick={() => saveAll()} loading={saveStatus === 'saving'}><Save size={13} /> Save All</Button>
        </div>
      </div>
    </div>
  );
}
