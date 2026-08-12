import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, Check, Search, ArrowUp, ArrowDown } from 'lucide-react';
import toast from 'react-hot-toast';
import { quizzesApi, studentsApi } from '../../api';
import { LoadingPage, Button } from '../../components/ui';
import { PermissionGate } from '../../components/ui/PermissionGate';
import { gradeColor, TERM_LABELS, formatDate } from '../../utils';
import type { DailyQuiz, DailyQuizScore, StudentProfile } from '../../types';

interface ScoreRow {
  student: StudentProfile;
  score: string;
  is_absent: boolean;
  remarks: string;
  saved: boolean;
  error: string;
}

type SortField = 'name' | 'score' | 'status';
type SortDir = 'asc' | 'desc';

export default function QuizMarkEntryPage() {
  const { id } = useParams<{ id: string }>();
  const quizId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [rows, setRows] = useState<ScoreRow[]>([]);
  const [searchText, setSearchText] = useState('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [saving, setSaving] = useState(false);

  const { data: quiz, isLoading: l1 } = useQuery<DailyQuiz>({
    queryKey: ['quiz', quizId],
    queryFn: () => quizzesApi.quiz(quizId).then(r => r.data),
  });

  const { data: students, isLoading: l2 } = useQuery<StudentProfile[]>({
    queryKey: ['classroom-students', quiz?.classroom],
    queryFn: () => studentsApi.classroomStudents(quiz!.classroom).then(r => r.data),
    enabled: !!quiz,
  });

  const { data: existingScores } = useQuery<DailyQuizScore[]>({
    queryKey: ['quiz-scores', quizId],
    queryFn: () => quizzesApi.scores({ quiz: quizId, page_size: 500 }).then(r => r.data.results ?? r.data),
    enabled: !!quiz,
  });

  useEffect(() => {
    if (!students) return;
    const scoreMap = new Map<number, DailyQuizScore>();
    (existingScores ?? []).forEach(s => scoreMap.set(s.student, s));
    setRows(students.filter(s => s.is_active).map(s => {
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
  }, []);

  const handleSaveAll = async () => {
    if (!quiz) return;
    const dirty = rows.filter(r => !r.saved && (r.score !== '' || r.is_absent));
    if (dirty.length === 0) {
      toast('Nothing to save', { icon: 'ℹ️' });
      return;
    }
    setSaving(true);
    try {
      const payload = dirty.map(r => ({
        student_id: r.student.student_id,
        score: r.is_absent ? 0 : Number(r.score),
        is_absent: r.is_absent,
        remarks: r.remarks,
      }));
      const res = await quizzesApi.bulkScores(quiz.id, payload);
      const errorMap = new Map<string, string>((res.data.errors ?? []).map((e: { student_id: string; error: string }) => [e.student_id, e.error]));
      setRows(prev => prev.map(r => {
        if (!dirty.some(d => d.student.id === r.student.id)) return r;
        const err = errorMap.get(r.student.student_id);
        return err ? { ...r, error: err } : { ...r, saved: true, error: '' };
      }));
      if (errorMap.size > 0) {
        toast.error(`${errorMap.size} score(s) had errors — check highlighted rows`);
      } else {
        toast.success(`Saved ${dirty.length} score${dirty.length !== 1 ? 's' : ''}`);
      }
      queryClient.invalidateQueries({ queryKey: ['quiz-scores', quizId] });
      queryClient.invalidateQueries({ queryKey: ['quizzes'] });
    } catch {
      toast.error('Failed to save scores');
    } finally {
      setSaving(false);
    }
  };

  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortField(field); setSortDir('asc'); }
  };
  const sortIndicator = (field: SortField) => {
    if (sortField !== field) return null;
    return sortDir === 'asc' ? <ArrowUp size={11} className="inline ml-1" /> : <ArrowDown size={11} className="inline ml-1" />;
  };

  const searched = rows.filter(r =>
    !searchText || r.student.full_name.toLowerCase().includes(searchText.toLowerCase()) ||
    r.student.student_id.toLowerCase().includes(searchText.toLowerCase())
  );
  const sorted = [...searched].sort((a, b) => {
    let cmp = 0;
    switch (sortField) {
      case 'name': cmp = a.student.full_name.localeCompare(b.student.full_name); break;
      case 'score': cmp = (Number(a.score) || -1) - (Number(b.score) || -1); break;
      case 'status': cmp = Number(a.saved) - Number(b.saved); break;
    }
    return sortDir === 'asc' ? cmp : -cmp;
  });

  const savedCount = rows.filter(r => r.saved).length;
  const maxScore = quiz?.max_score ?? 0;

  if (l1 || l2) return <LoadingPage />;
  if (!quiz) return null;

  return (
    <PermissionGate resource="quizzes" action="edit" backTo="/quizzes" backLabel="Back to Quizzes">
      <div className="flex flex-col gap-4 md:gap-6">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <button onClick={() => navigate('/quizzes')} className="text-secondary hover:text-primary text-sm transition-colors mb-2">← Back to Quizzes</button>
            <h1 className="page-title">{quiz.display_title}</h1>
            <p className="text-muted mt-0.5">
              {quiz.classroom_name} · {quiz.subject_name} · {formatDate(quiz.date)} · {TERM_LABELS[quiz.term]} · Max {maxScore}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-secondary">{savedCount}/{rows.length} saved</span>
            <Button onClick={handleSaveAll} loading={saving} size="sm">
              <Save size={14} /> Save All
            </Button>
          </div>
        </div>

        <div className="relative">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
          <input className="input pl-10 w-full" placeholder="Search students…" value={searchText} onChange={e => setSearchText(e.target.value)} />
        </div>

        {rows.length === 0 ? (
          <div className="card p-6 text-center text-muted text-sm">No active students in this classroom.</div>
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface">
                    <th className="text-left py-3 px-4 whitespace-nowrap">
                      <button className="flex items-center gap-1 text-xs font-display font-semibold text-secondary uppercase tracking-widest hover:text-primary transition-colors" onClick={() => toggleSort('name')}>
                        Student {sortIndicator('name')}
                      </button>
                    </th>
                    <th className="text-left py-3 px-4 whitespace-nowrap w-28">
                      <button className="flex items-center gap-1 text-xs font-display font-semibold text-secondary uppercase tracking-widest hover:text-primary transition-colors" onClick={() => toggleSort('score')}>
                        Score / {maxScore} {sortIndicator('score')}
                      </button>
                    </th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap w-20">Absent</th>
                    <th className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">Remarks</th>
                    <th className="text-left py-3 px-3 whitespace-nowrap w-8">
                      <button className="text-xs font-display font-semibold text-secondary uppercase tracking-widest hover:text-primary transition-colors" onClick={() => toggleSort('status')}>
                        ✓{sortIndicator('status')}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(row => {
                    const pct = row.score !== '' && maxScore ? Math.round((Number(row.score) / maxScore) * 100) : null;
                    return (
                      <tr key={row.student.id} className={`border-b border-surface last:border-0 ${row.error ? 'bg-rose-500/5' : ''}`}>
                        <td className="py-2 px-4">
                          <p className="font-display font-medium text-primary text-sm">{row.student.full_name}</p>
                          <p className="text-xs text-secondary font-mono">{row.student.student_id}</p>
                        </td>
                        <td className="py-2 px-4">
                          <div className="flex items-center gap-2">
                            <input
                              type="number" min={0} max={maxScore} step="0.5"
                              className={`input w-20 text-sm text-center ${row.error ? 'border-rose-500' : ''}`}
                              value={row.score} disabled={row.is_absent}
                              onChange={e => updateRow(row.student.id, 'score', e.target.value)}
                            />
                            {pct !== null && !row.is_absent && (
                              <span className={`text-xs font-mono font-bold ${gradeColor(pct)}`}>{pct}%</span>
                            )}
                          </div>
                          {row.error && <p className="text-xs text-rose-400 mt-1">{row.error}</p>}
                        </td>
                        <td className="py-2 px-4">
                          <input type="checkbox" checked={row.is_absent}
                            onChange={e => updateRow(row.student.id, 'is_absent', e.target.checked)}
                            className="w-4 h-4 accent-azure-500" />
                        </td>
                        <td className="py-2 px-4">
                          <input type="text" className="input text-xs w-full" placeholder="Optional"
                            value={row.remarks} onChange={e => updateRow(row.student.id, 'remarks', e.target.value)} />
                        </td>
                        <td className="py-2 px-3">
                          {row.saved && <Check size={14} className="text-emerald-400" />}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </PermissionGate>
  );
}
