import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';
import { examsApi, reportsApi } from '../../api';
import { LoadingPage, Table, Tr, Td, Button, Modal, Input } from '../../components/ui';
import { formatDate, EXAM_TYPE_LABELS, TERM_LABELS, gradeBg, gradeColor, downloadBlob } from '../../utils';
import { useAuthStore } from '../../store/auth';
import { useCanManage } from '../../hooks/useCanManage';
import type { Exam, ExamScore } from '../../types';
import toast from 'react-hot-toast';
import { Download, Edit, Send, Clock } from 'lucide-react';

interface ExamStats {
  exam_id: number;
  exam_title: string;
  total_students: number;
  absent_count: number;
  average: number | null;
  highest: number | null;
  lowest: number | null;
  pass_rate: number | null;
  distribution: Record<string, number>;
}

const DIST_COLORS: Record<string, string> = {
  '0-49': '#f43f5e', '50-59': '#f59e0b', '60-69': '#fbbf24',
  '70-79': '#60a5fa', '80-89': '#34d399', '90-100': '#10b981',
};

export default function ExamDetailPage() {
  const { id } = useParams<{ id: string }>();
  const examId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editScore, setEditScore] = useState<ExamScore | null>(null);
  const [editValue, setEditValue] = useState('');
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin';
  // Covers both "Enter Marks" (bulk_scores) and "Edit" (exam details) —
  // the backend gates both under the same exams/edit toggle since score
  // entry is just another way of writing exam data.
  const canEditExam = useCanManage('exams', 'edit');

  const { data: exam, isLoading: l1 } = useQuery<Exam>({
    queryKey: ['exam', examId],
    queryFn: () => examsApi.exam(examId).then(r => r.data),
  });

  const { data: scores, isLoading: l2 } = useQuery<ExamScore[]>({
    queryKey: ['exam-scores', examId],
    queryFn: () => examsApi.examScores(examId).then(r => r.data),
  });

  const { data: stats } = useQuery<ExamStats>({
    queryKey: ['exam-stats', examId],
    queryFn: () => examsApi.examStats(examId).then(r => r.data),
    enabled: !!exam?.is_published,
  });

  const publishMutation = useMutation({
    mutationFn: () => examsApi.publishExam(examId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exam', examId] });
      queryClient.invalidateQueries({ queryKey: ['exams'] });
      toast.success('Exam published!');
    },
  });

  const unpublishMutation = useMutation({
    mutationFn: () => examsApi.unpublishExam(examId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exam', examId] });
      queryClient.invalidateQueries({ queryKey: ['exams'] });
      toast.success('Exam moved back to draft');
    },
  });

  const updateScoreMutation = useMutation({
    mutationFn: ({ scoreId, score }: { scoreId: number; score: number }) =>
      examsApi.updateScore(scoreId, { score }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exam-scores', examId] });
      queryClient.invalidateQueries({ queryKey: ['exam-stats', examId] });
      setEditScore(null);
      toast.success('Score updated');
    },
    onError: () => toast.error('Failed to update score'),
  });

  const handleExportCSV = async () => {
    try {
      const res = await reportsApi.exportExamCsv(examId);
      downloadBlob(res.data as Blob, `exam_${examId}_scores.csv`);
      toast.success('CSV downloaded');
    } catch {
      toast.error('Export failed');
    }
  };

  const handleSaveScore = () => {
    if (!editScore) return;
    const val = parseFloat(editValue);
    if (isNaN(val) || val < 0) {
      toast.error('Enter a valid score');
      return;
    }
    if (exam && val > Number(exam.max_score)) {
      toast.error(`Score cannot exceed ${exam.max_score}`);
      return;
    }
    updateScoreMutation.mutate({ scoreId: editScore.id, score: val });
  };

  if (l1 || l2) return <LoadingPage />;
  if (!exam) return <div className="text-muted">Exam not found.</div>;

  const distData = stats?.distribution
    ? Object.entries(stats.distribution).map(([range, count]) => ({ range, count }))
    : [];

  return (
    <div className="flex flex-col gap-6 page-enter">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1 min-w-0">
            <button onClick={() => navigate('/exams')} className="text-secondary hover:text-primary text-sm transition-colors flex-shrink-0">Exams</button>
            <span className="text-secondary flex-shrink-0">/</span>
            <span className="text-sm text-primary truncate min-w-0">{exam.title}</span>
          </div>
          <h1 className="page-title break-words">{exam.title}</h1>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className="badge badge-violet">{EXAM_TYPE_LABELS[exam.exam_type]}</span>
            <span className="badge badge-blue">{TERM_LABELS[exam.term]}</span>
            <span className={`badge ${exam.is_published ? 'badge-green' : 'badge-amber'}`}>
              {exam.is_published ? 'Published' : 'Draft'}
            </span>
            <span className="text-muted text-xs">{formatDate(exam.exam_date)}</span>
          </div>
          {!exam.is_published && !isAdmin && (
            <div className="flex items-center gap-1.5 mt-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2.5 py-1.5 w-fit">
              <Clock size={11} />
              Awaiting admin approval before students can see this exam
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-2 sm:flex-shrink-0">
          <Button variant="primary" size="sm" onClick={() => navigate(`/exams/${examId}/marks`)} disabled={!canEditExam}
            title={!canEditExam ? 'Editing exams has been disabled for teachers by an administrator' : undefined}>
            <Edit size={13} /> Enter Marks
          </Button>
          {isAdmin && !exam.is_published && (
            <Button
              variant="primary"
              size="sm"
              loading={publishMutation.isPending}
              onClick={() => publishMutation.mutate()}
            >
              <Send size={13} /> Publish
            </Button>
          )}
          {isAdmin && exam.is_published && (
            <Button
              variant="secondary"
              size="sm"
              loading={unpublishMutation.isPending}
              onClick={() => unpublishMutation.mutate()}
            >
              Unpublish
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={handleExportCSV}>
            <Download size={13} /> Export CSV
          </Button>
          {canEditExam && (
            <Button variant="secondary" size="sm" onClick={() => navigate(`/exams/${examId}/edit`)}>
              <Edit size={13} /> Edit
            </Button>
          )}
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
          {[
            { label: 'Students', value: stats.total_students },
            { label: 'Average', value: stats.average != null ? `${stats.average}%` : '—' },
            { label: 'Highest', value: stats.highest != null ? `${stats.highest}%` : '—' },
            { label: 'Lowest', value: stats.lowest != null ? `${stats.lowest}%` : '—' },
            { label: 'Pass Rate', value: stats.pass_rate != null ? `${stats.pass_rate}%` : '—' },
          ].map(({ label, value }) => (
            <div key={label} className="card p-4">
              <p className="label">{label}</p>
              <p className="font-display font-bold text-xl text-primary mt-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Score distribution chart */}
        {distData.length > 0 && distData.some(d => (d.count as number) > 0) && (
          <div className="card p-6">
            <h2 className="section-title mb-5">Score Distribution</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={distData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                <XAxis dataKey="range" tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                <YAxis tick={{ fill: '#3d3d55', fontSize: 10, fontFamily: 'DM Sans' }} />
                <Tooltip
                  contentStyle={{ background: '#1a1a26', border: '1px solid #2e2e42', borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: '#fff', fontFamily: 'Syne' }}
                  itemStyle={{ color: '#60a5fa' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {distData.map((entry) => (
                    <Cell key={entry.range} fill={DIST_COLORS[entry.range] ?? '#6366f1'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Topic weights */}
        {exam.topic_weights.length > 0 && (
          <div className="card p-6">
            <h2 className="section-title mb-4">Topic Weights</h2>
            <div className="flex flex-col gap-2.5">
              {exam.topic_weights.map(tw => (
                <div key={tw.id} className="flex items-center gap-3">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: tw.topic_color }} />
                  <div className="flex-1">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-display font-medium text-primary">{tw.topic_name}</span>
                      <span className="font-mono text-secondary">{tw.max_marks} marks</span>
                    </div>
                    <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(tw.max_marks / Number(exam.max_score)) * 100}%`,
                          backgroundColor: tw.topic_color,
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Exam metadata */}
        <div className="card p-6">
          <h2 className="section-title mb-4">Exam Details</h2>
          <dl className="flex flex-col gap-3">
            {[
              { dt: 'Academic Year', dd: exam.academic_year },
              { dt: 'Max Score', dd: exam.max_score },
              { dt: 'Passing Score', dd: `${exam.passing_score} (${exam.passing_percentage}%)` },
              { dt: 'Created by', dd: exam.created_by_name },
              { dt: 'Created', dd: formatDate(exam.created_at) },
            ].map(({ dt, dd }) => (
              <div key={dt} className="flex justify-between text-sm gap-3">
                <dt className="text-secondary">{dt}</dt>
                <dd className="text-primary font-medium text-right">{dd}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* Scores table */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="section-title">Student Scores</h2>
          <span className="text-muted text-xs">{scores?.length ?? 0} records</span>
        </div>
        {!scores?.length ? (
          <p className="text-muted text-center py-10">No scores recorded yet.</p>
        ) : (
          <Table headers={['Student', 'ID', 'Score', 'Percentage', 'Grade', 'Status', 'Entered', '']}>
            {scores.map(score => (
              <Tr key={score.id}>
                <Td>
                  <button
                    className="font-display font-medium text-primary hover:text-azure-400 transition-colors text-left"
                    onClick={() => navigate(`/analytics/student/${score.student}`)}
                  >
                    {score.student_name}
                  </button>
                </Td>
                <Td>
                  <span className="font-mono text-xs text-secondary">{score.student_id_code}</span>
                </Td>
                <Td>
                  {score.is_absent ? (
                    <span className="badge badge-rose">Absent</span>
                  ) : (
                    <span className="font-mono text-sm font-bold text-primary">
                      {score.score}/{exam.max_score}
                    </span>
                  )}
                </Td>
                <Td>
                  {!score.is_absent && (
                    <span className={`font-mono text-sm font-bold ${gradeColor(score.percentage)}`}>
                      {score.percentage}%
                    </span>
                  )}
                </Td>
                <Td>
                  {!score.is_absent && (
                    <span className={`badge ${gradeBg(score.percentage)}`}>{score.letter_grade}</span>
                  )}
                </Td>
                <Td>
                  {!score.is_absent && (
                    <span className={`badge ${score.passed ? 'badge-green' : 'badge-rose'}`}>
                      {score.passed ? 'Pass' : 'Fail'}
                    </span>
                  )}
                </Td>
                <Td className="text-secondary text-xs">{formatDate(score.entered_at)}</Td>
                <Td>
                  {canEditExam && (
                    <button
                      className="text-xs text-azure-400 hover:text-azure-300 font-display font-medium transition-colors"
                      onClick={() => { setEditScore(score); setEditValue(String(score.score)); }}
                    >
                      Edit
                    </button>
                  )}
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </div>

      {/* Edit score modal */}
      <Modal
        open={!!editScore}
        onClose={() => setEditScore(null)}
        title="Edit Score"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditScore(null)}>Cancel</Button>
            <Button loading={updateScoreMutation.isPending} onClick={handleSaveScore}>Save</Button>
          </>
        }
      >
        {editScore && (
          <ScoreEditModal
            score={editScore}
            maxScore={Number(exam.max_score)}
            editValue={editValue}
            onChangeValue={setEditValue}
          />
        )}
      </Modal>
    </div>
  );
}

function ScoreEditModal({ score, maxScore, editValue, onChangeValue }: {
  score: ExamScore; maxScore: number;
  editValue: string; onChangeValue: (v: string) => void;
}) {
  const { data: history } = useQuery<{ id: number; old_score: number; new_score: number; changed_by_name: string; changed_at: string; reason: string }[]>({
    queryKey: ['score-history', score.id],
    queryFn: () => examsApi.scoreHistory(score.id).then(r => r.data),
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-surface-900 rounded-xl p-3">
        <p className="text-sm font-display font-medium text-primary">{score.student_name}</p>
        <p className="text-xs text-secondary mt-0.5">Current score: {score.score}/{maxScore}</p>
      </div>
      <Input
        label={`New Score (max ${maxScore})`}
        type="number" min={0} max={maxScore} step={0.5}
        value={editValue}
        onChange={e => onChangeValue(e.target.value)}
      />
      {history && history.length > 0 && (
        <div>
          <p className="label mb-2">Edit History</p>
          <div className="flex flex-col gap-1.5 max-h-36 overflow-y-auto">
            {history.map(h => (
              <div key={h.id} className="flex items-center justify-between text-xs bg-surface-900 rounded-lg px-3 py-2">
                <span className="text-secondary">{h.changed_by_name}</span>
                <span className="text-secondary font-mono">{h.old_score} → {h.new_score}</span>
                <span className="text-secondary">{new Date(h.changed_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {history && history.length === 0 && (
        <p className="text-xs text-muted text-center py-1">No edits recorded yet</p>
      )}
    </div>
  );
}
