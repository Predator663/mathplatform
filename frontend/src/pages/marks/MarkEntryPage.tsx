import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, Check, WifiOff, Download, Search, CloudOff, ArrowUp, ArrowDown } from 'lucide-react';
import toast from 'react-hot-toast';
import { examsApi } from '../../api';
import { LoadingPage, Button, Select } from '../../components/ui';
import { PermissionGate } from '../../components/ui/PermissionGate';
import { gradeBg, gradeColor, tanzaniaGrade, EXAM_TYPE_LABELS, TERM_LABELS, downloadBlob } from '../../utils';
import { useSync } from '../../hooks/usePWASync';
import { useOfflineStudentsByClassroom, useOfflineClassrooms } from '../../hooks/useOfflineData';
import { getCachedExams } from '../../db';
import type { Exam, ExamScore, StudentProfile } from '../../types';

interface ScoreRow {
  student: StudentProfile;
  score: string;
  is_absent: boolean;
  remarks: string;
  saved: boolean;
  error: string;
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';
type SortField = 'name' | 'student_id' | 'score' | 'status';
type SortDir = 'asc' | 'desc';

export default function MarkEntryPage() {
  const { id } = useParams<{ id: string }>();
  const examId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isOnline, queueScore } = useSync();

  const [rows, setRows]               = useState<ScoreRow[]>([]);
  const [searchText, setSearchText]   = useState('');
  const [filterClass, setFilterClass] = useState('');
  const [sortField, setSortField]     = useState<SortField>('name');
  const [sortDir, setSortDir]         = useState<SortDir>('asc');
  const [saveStatus, setSaveStatus]   = useState<SaveStatus>('idle');
  const [autoSave, setAutoSave]       = useState(true);
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dirtyRef = useRef(false);
  const desktopTableRef = useRef<HTMLDivElement>(null);

  const { data: exam, isLoading: l1, isError: examError } = useQuery<Exam>({
    queryKey: ['exam', examId],
    queryFn: () => examsApi.exam(examId).then(r => r.data),
    retry: 1,
  });

  // If the live exam fetch fails (offline, or just a flaky connection), fall
  // back to whatever was last synced into IndexedDB so the teacher can still
  // see which classrooms/students this exam covers and keep entering marks.
  const [offlineExam, setOfflineExam] = useState<Exam | null>(null);
  useEffect(() => {
    if (!examError) return;
    getCachedExams().then(cachedExams => {
      const match = cachedExams.find(r => r.id === examId);
      if (match) {
        setOfflineExam({
          id: match.id, title: match.title, exam_type: match.exam_type as Exam['exam_type'],
          term: match.term as Exam['term'], academic_year: match.academic_year,
          exam_date: match.exam_date, max_score: match.max_score, passing_score: match.passing_score,
          passing_percentage: 0, classrooms: match.classrooms, topic_weights: [],
          created_by: 0, created_by_name: '', description: '', is_published: match.is_published,
          created_at: '', updated_at: '', score_count: match.score_count,
          average_score: match.average_score, pass_rate: match.pass_rate,
          subject: 0, subject_name: '', subject_code: '', subject_color: '',
        });
      }
    }).catch(() => {});
  }, [examError, examId]);

  const effectiveExam = exam ?? (examError ? offlineExam ?? undefined : undefined);
  const usingOfflineExam = examError && !!offlineExam;

  const { data: existingScores } = useQuery<ExamScore[]>({
    queryKey: ['exam-scores', examId],
    queryFn: () => examsApi.examScores(examId).then(r => r.data),
    retry: 1,
  });

  const { classrooms } = useOfflineClassrooms();

  const { students, isOfflineFallback: studentsOffline, isLoading: l2 } =
    useOfflineStudentsByClassroom(effectiveExam?.classrooms);

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
    if (!effectiveExam) return;
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
          exam_id: effectiveExam.id,
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
      const res = await examsApi.bulkScores(effectiveExam.id, { scores: payload });
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
  }, [rows, effectiveExam, examId, isOnline, queueScore, queryClient]);

  const downloadTemplate = async () => {
    if (!effectiveExam || usingOfflineExam) return;
    try {
      const res = await examsApi.scoresTemplate(examId);
      downloadBlob(res.data as Blob, `scores_template_${examId}.csv`);
    } catch { toast.error('Download failed'); }
  };

  const searchedRows = rows.filter(r => {
    const matchSearch = !searchText ||
      r.student.full_name.toLowerCase().includes(searchText.toLowerCase()) ||
      r.student.student_id.toLowerCase().includes(searchText.toLowerCase());
    const matchClass = !filterClass || String(r.student.classroom) === filterClass;
    return matchSearch && matchClass;
  });

  // Status rank used for the "Status" sort: students with nothing entered yet
  // float to one end so a teacher can quickly find who's left to mark.
  const statusRank = (r: ScoreRow) => {
    if (r.score === '' && !r.is_absent) return 0; // not entered
    if (r.is_absent) return 1;                    // marked absent
    if (!r.saved) return 2;                        // entered, not yet saved
    return 3;                                       // saved
  };

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const sortIndicator = (field: SortField) => {
    if (sortField !== field) return null;
    return sortDir === 'asc' ? <ArrowUp size={11} className="inline ml-1" /> : <ArrowDown size={11} className="inline ml-1" />;
  };

  const filteredRows = [...searchedRows].sort((a, b) => {
    let cmp = 0;
    switch (sortField) {
      case 'name':
        cmp = a.student.full_name.localeCompare(b.student.full_name);
        break;
      case 'student_id':
        cmp = a.student.student_id.localeCompare(b.student.student_id, undefined, { numeric: true });
        break;
      case 'score': {
        const val = (r: ScoreRow) => (r.is_absent || r.score === '' || isNaN(parseFloat(r.score))) ? -1 : parseFloat(r.score);
        cmp = val(a) - val(b);
        break;
      }
      case 'status':
        cmp = statusRank(a) - statusRank(b);
        break;
    }
    return sortDir === 'asc' ? cmp : -cmp;
  });

  const totalEntered = rows.filter(r => r.is_absent || (r.score !== '' && !isNaN(parseFloat(r.score)))).length;

  if (l1 && !usingOfflineExam) return <LoadingPage />;
  if (!effectiveExam) return <div className="text-muted p-4">Exam not found.</div>;

  return (
    <PermissionGate resource="exams" action="edit" backTo={`/exams/${examId}`} backLabel="Back to Exam">
    <div className="flex flex-col gap-4 page-enter">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <button onClick={() => navigate(`/exams/${examId}`)} className="text-ink-500 hover:text-primary text-sm transition-colors mb-1">
            ← {effectiveExam.title}
          </button>
          <h1 className="page-title">Mark Entry</h1>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-muted text-sm">{totalEntered}/{rows.length} entered</span>
            {!isOnline && (
              <span className="flex items-center gap-1 text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded-full">
                <WifiOff size={11} /> Offline — queuing
              </span>
            )}
            {(usingOfflineExam || studentsOffline) && (
              <span className="flex items-center gap-1 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                <CloudOff size={11} /> Showing data saved on this device
              </span>
            )}
            {saveStatus === 'saving' && <span className="text-xs text-azure-400 animate-pulse">Saving…</span>}
            {saveStatus === 'saved'  && <span className="text-xs text-emerald-400 flex items-center gap-1"><Check size={11} /> Saved</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <label className="flex items-center gap-1.5 text-xs text-ink-500 cursor-pointer select-none">
            <input type="checkbox" checked={autoSave} onChange={e => setAutoSave(e.target.checked)} className="rounded accent-azure-500" />
            Auto-save
          </label>
          <Button variant="secondary" size="sm" onClick={downloadTemplate} disabled={!isOnline}><Download size={13} /> Template</Button>
          <Button size="sm" onClick={() => saveAll()} loading={saveStatus === 'saving'}><Save size={13} /> Save All</Button>
        </div>
      </div>

      {/* Progress */}
      <div className="h-1.5 bg-ink-800 rounded-full overflow-hidden">
        <div className="h-full bg-gradient-to-r from-azure-500 to-emerald-500 rounded-full transition-all duration-500"
          style={{ width: rows.length ? `${(totalEntered / rows.length) * 100}%` : '0%' }} />
      </div>

      {/* Exam meta + filters */}
      <div className="flex flex-wrap gap-2 sm:gap-3 items-center">
        <div className="relative flex-1 min-w-[140px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-500" />
          <input className="input pl-9 text-sm w-full" placeholder="Search student…"
            value={searchText} onChange={e => setSearchText(e.target.value)} />
        </div>
        {classrooms.length > 1 && (
          <Select className="w-full sm:w-40" options={[
            { value: '', label: 'All Classes' },
            ...classrooms.map(c => ({ value: c.id, label: c.name })),
          ]} value={filterClass} onChange={e => setFilterClass(e.target.value)} />
        )}
        <div className="flex items-center gap-1.5 w-full sm:w-auto">
          <Select className="w-full sm:w-36" aria-label="Sort by" options={[
            { value: 'name', label: 'Sort: Name' },
            { value: 'student_id', label: 'Sort: Student ID' },
            { value: 'score', label: 'Sort: Score' },
            { value: 'status', label: 'Sort: Status' },
          ]} value={sortField} onChange={e => setSortField(e.target.value as SortField)} />
          <button
            type="button"
            onClick={() => setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))}
            title={sortDir === 'asc' ? 'Ascending — click for descending' : 'Descending — click for ascending'}
            className="flex-shrink-0 p-2.5 rounded-xl border border-surface text-secondary hover:text-primary hover:bg-surface-700 transition-colors"
          >
            {sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
          </button>
        </div>
        <div className="text-xs text-ink-500 font-mono bg-ink-900 rounded-xl px-3 py-2 whitespace-nowrap">
          Max: <b className="text-primary">{effectiveExam.max_score}</b> · Pass: <b className="text-primary">{effectiveExam.passing_score}</b>
        </div>
      </div>

      {/* Mobile card list */}
      <div className="flex flex-col gap-2 md:hidden">
        {filteredRows.map(row => {
          const scoreNum = parseFloat(row.score);
          const valid = !isNaN(scoreNum) && scoreNum >= 0 && scoreNum <= Number(effectiveExam.max_score);
          const pct = valid ? Math.round((scoreNum / Number(effectiveExam.max_score)) * 100) : null;
          const grade = pct !== null ? tanzaniaGrade(pct) : null;

          return (
            <div key={row.student.id}
              className={`card p-3.5 flex flex-col gap-3 ${
                row.is_absent ? 'bg-rose-500/5' : row.saved ? 'bg-emerald-500/5' : ''
              }`}>
              {/* Identity */}
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0">
                  {row.student.first_name?.[0]}{row.student.last_name?.[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-primary text-sm leading-tight truncate">{row.student.full_name}</p>
                  <p className="text-[11px] text-ink-500 font-mono">{row.student.student_id}</p>
                </div>
                {row.error
                  ? <span className="text-rose-400 text-xs flex-shrink-0" title={row.error}>!</span>
                  : row.saved
                    ? <Check size={16} className="text-emerald-400 flex-shrink-0" />
                    : null}
              </div>

              {/* Score input with explicit "/max" context + grade readout */}
              <div className="flex items-center gap-2.5">
                <div className="flex-1 flex items-center gap-1.5 min-w-0">
                  <input
                    type="number" min={0} max={Number(effectiveExam.max_score)} step={0.5}
                    disabled={row.is_absent}
                    className={`input flex-1 min-w-0 text-base font-mono text-center disabled:opacity-40 ${
                      row.error ? 'border-rose-500/60 text-rose-400'
                      : row.saved && !row.is_absent ? 'border-emerald-500/40 text-emerald-400'
                      : 'text-primary'
                    }`}
                    value={row.is_absent ? '' : row.score}
                    placeholder={row.is_absent ? '—' : '0'}
                    onChange={e => updateRow(row.student.id, 'score', e.target.value)}
                  />
                  <span className="text-xs text-ink-500 font-mono flex-shrink-0">/ {effectiveExam.max_score}</span>
                </div>
                <div className="w-16 text-center flex-shrink-0">
                  {row.is_absent
                    ? <span className="text-xs text-rose-400 font-medium">Absent</span>
                    : pct !== null && grade
                      ? <span className={`font-mono text-sm font-bold ${gradeColor(pct)}`}>{pct}% <span className="text-xs opacity-70">{grade}</span></span>
                      : <span className="text-ink-600 text-xs">—</span>}
                </div>
              </div>

              {/* Absent toggle + remarks */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const next = !row.is_absent;
                    updateRow(row.student.id, 'is_absent', next);
                    if (next) updateRow(row.student.id, 'score', '');
                  }}
                  className={`flex-shrink-0 text-xs font-medium px-3 py-2.5 rounded-lg border transition-colors ${
                    row.is_absent
                      ? 'bg-rose-500/15 border-rose-500/40 text-rose-400'
                      : 'border-ink-600 text-ink-500 hover:text-primary hover:border-ink-500'
                  }`}
                >
                  Absent
                </button>
                <input type="text" className="input flex-1 min-w-0 text-xs py-2.5"
                  placeholder="Remarks…" value={row.remarks}
                  onChange={e => updateRow(row.student.id, 'remarks', e.target.value)} />
              </div>
            </div>
          );
        })}
        {filteredRows.length === 0 && (
          <div className="py-12 text-center text-muted text-sm">No students found for this exam.</div>
        )}
      </div>

      {/* Desktop score table */}
      <div className="card overflow-hidden hidden md:block" ref={desktopTableRef}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead>
              <tr className="border-b border-ink-700">
                <th className="text-left text-xs font-display font-semibold text-ink-500 uppercase tracking-widest py-3 px-3 whitespace-nowrap first:pl-4">#</th>
                <th className="text-left text-xs font-display font-semibold text-ink-500 uppercase tracking-widest py-3 px-3 whitespace-nowrap cursor-pointer select-none hover:text-primary transition-colors"
                  onClick={() => toggleSort('name')}>
                  Student{sortIndicator('name')}
                </th>
                <th className="text-left text-xs font-display font-semibold text-ink-500 uppercase tracking-widest py-3 px-3 whitespace-nowrap cursor-pointer select-none hover:text-primary transition-colors"
                  onClick={() => toggleSort('score')}>
                  Score{sortIndicator('score')}
                </th>
                <th className="text-left text-xs font-display font-semibold text-ink-500 uppercase tracking-widest py-3 px-3 whitespace-nowrap">% Grade</th>
                <th className="text-left text-xs font-display font-semibold text-ink-500 uppercase tracking-widest py-3 px-3 whitespace-nowrap">Absent</th>
                <th className="text-left text-xs font-display font-semibold text-ink-500 uppercase tracking-widest py-3 px-3 whitespace-nowrap">Remarks</th>
                <th className="text-left text-xs font-display font-semibold text-ink-500 uppercase tracking-widest py-3 px-3 whitespace-nowrap cursor-pointer select-none hover:text-primary transition-colors last:pr-4"
                  onClick={() => toggleSort('status')}>
                  ✓{sortIndicator('status')}
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row, idx) => {
                const scoreNum = parseFloat(row.score);
                const valid = !isNaN(scoreNum) && scoreNum >= 0 && scoreNum <= Number(effectiveExam.max_score);
                const pct = valid ? Math.round((scoreNum / Number(effectiveExam.max_score)) * 100) : null;
                const grade = pct !== null ? tanzaniaGrade(pct) : null;

                return (
                  <tr key={row.student.id}
                    className={`border-b border-ink-800 transition-colors ${
                      row.is_absent ? 'bg-rose-500/5' : row.saved ? 'bg-emerald-500/5' : 'hover:bg-surface-700'
                    }`}>
                    <td className="py-2.5 pl-4 pr-2 text-ink-500 text-xs font-mono w-8">{idx + 1}</td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0">
                          {row.student.first_name?.[0]}{row.student.last_name?.[0]}
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-primary text-xs leading-tight truncate">{row.student.full_name}</p>
                          <p className="text-[10px] text-ink-500 font-mono">{row.student.student_id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 w-24">
                      <input
                        type="number" min={0} max={Number(effectiveExam.max_score)} step={0.5}
                        disabled={row.is_absent}
                        className={`w-20 bg-ink-900 border rounded-lg px-2 py-1.5 text-sm font-mono text-center focus:outline-none focus:ring-2 transition-all ${
                          row.error ? 'border-rose-500/60 focus:ring-rose-500/30 text-rose-400'
                          : row.saved && !row.is_absent ? 'border-emerald-500/40 focus:ring-emerald-500/30 text-emerald-400'
                          : 'border-ink-600 focus:ring-azure-500/40 text-primary'
                        } disabled:opacity-40`}
                        value={row.is_absent ? '' : row.score}
                        placeholder={row.is_absent ? 'ABS' : '0'}
                        onChange={e => updateRow(row.student.id, 'score', e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter' || (e.key === 'Tab' && !e.shiftKey)) {
                            e.preventDefault();
                            const next = filteredRows.findIndex(r => r.student.id === row.student.id) + 1;
                            if (next < filteredRows.length) {
                              desktopTableRef.current
                                ?.querySelectorAll<HTMLInputElement>('input[type="number"]')[next]?.focus();
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
                          : <span className="text-ink-600 text-xs">—</span>}
                    </td>
                    <td className="py-2.5 px-3 w-20">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" checked={row.is_absent}
                          onChange={e => {
                            updateRow(row.student.id, 'is_absent', e.target.checked);
                            if (e.target.checked) updateRow(row.student.id, 'score', '');
                          }}
                          className="w-3.5 h-3.5 rounded accent-rose-500" />
                        <span className="text-xs text-ink-500">Abs</span>
                      </label>
                    </td>
                    <td className="py-2.5 px-3">
                      <input type="text" className="bg-ink-900 border border-ink-700 rounded-lg px-2 py-1 text-xs text-ink-400 w-24 focus:outline-none focus:border-ink-500 focus:text-primary"
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
      <div className="sticky bottom-20 lg:bottom-4 flex items-center justify-between gap-2 flex-wrap bg-surface-800 backdrop-blur border border-ink-600 rounded-2xl px-4 py-3 shadow-2xl">
        <div className="text-sm text-ink-500">
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
    </PermissionGate>
  );
}
