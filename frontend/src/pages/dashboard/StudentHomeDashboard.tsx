import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip,
} from 'recharts';
import type { TooltipProps } from 'recharts';
import {
  TrendingUp, TrendingDown, Minus, Flame,
  AlertTriangle, ArrowRight, ClipboardList, Trophy, Pencil, Check, X as XIcon,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { analyticsApi, gamificationApi, quizzesApi, studentsApi } from '../../api';
import { LoadingPage, TiltCard, Reveal } from '../../components/ui';
import { formatDate, gradeBg, gradeColor } from '../../utils';
import type {
  StudentSummary, StudentTrend, StudentTopicAnalysis,
  StudentClassroomComparison, StudentProgress, StudentQuizProgress, StudentProfile,
} from '../../types';

/* Fallback goal for students who haven't set their own yet — NECTA's
 * "good pass" bar. A real per-student value now lives on StudentProfile
 * (target_percentage) and is editable below when viewerRole === 'self'. */
const DEFAULT_TARGET_PERCENTAGE = 75;

function cssVar(name: string): string {
  if (typeof document === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function TrendBadge({ trend }: { trend: string }) {
  const Icon = trend === 'improving' ? TrendingUp : trend === 'declining' ? TrendingDown : Minus;
  const color = trend === 'improving' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
    : trend === 'declining' ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
    : 'text-secondary bg-surface-800 border-surface';
  const label = trend === 'improving' ? 'Improving' : trend === 'declining' ? 'Needs attention' : trend === 'no_data' ? 'No data yet' : 'Steady';
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-display font-semibold border ${color}`}>
      <Icon size={14} /><span>{label}</span>
    </div>
  );
}

const ChartTooltip = ({ active, payload, label }: TooltipProps<number, string>) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl border border-surface">
      <p className="font-display font-semibold text-primary mb-1">{label}</p>
      {payload.filter(p => p.value != null).map(p => (
        <p key={String(p.name)} className="text-azure-400">
          {p.name === 'movingAvg' ? 'Moving avg' : 'Score'}: {p.value}%
        </p>
      ))}
    </div>
  );
};

export default function StudentHomeDashboard({
  studentId, viewerRole = 'self', childLabel,
}: {
  studentId: number;
  /** 'self' = the student viewing their own data (default); 'guardian' =
   * a parent/teacher viewing on someone else's behalf — same data, but the
   * "go do this now" action links (take a quiz, practice a topic) are
   * hidden since those don't make sense for someone who isn't the learner. */
  viewerRole?: 'self' | 'guardian';
  /** Optional override for the greeting, e.g. a parent viewing a specific child. */
  childLabel?: string;
}) {
  const { data: summary, isLoading: l1 } = useQuery<StudentSummary>({
    queryKey: ['my-summary', studentId],
    queryFn: () => analyticsApi.studentSummary(studentId).then(r => r.data),
  });
  const { data: trend, isLoading: l2 } = useQuery<StudentTrend>({
    queryKey: ['my-trend', studentId],
    queryFn: () => analyticsApi.studentTrend(studentId).then(r => r.data),
  });
  const { data: topics, isLoading: l3 } = useQuery<StudentTopicAnalysis>({
    queryKey: ['my-topics', studentId],
    queryFn: () => analyticsApi.studentTopics(studentId).then(r => r.data),
  });
  const { data: comparison } = useQuery<StudentClassroomComparison>({
    queryKey: ['my-comparison', studentId],
    queryFn: () => analyticsApi.studentClassroomComparison(studentId).then(r => r.data),
  });
  const { data: progress } = useQuery<StudentProgress>({
    queryKey: ['my-gamification-progress'],
    queryFn: () => gamificationApi.myProgress().then(r => r.data),
  });
  const { data: quizProgress } = useQuery<StudentQuizProgress>({
    queryKey: ['my-quiz-progress'],
    queryFn: () => quizzesApi.myProgress().then(r => r.data),
  });
  const { data: profile } = useQuery<StudentProfile>({
    queryKey: ['my-student-profile', studentId],
    queryFn: () => studentsApi.student(studentId).then(r => r.data),
  });

  const queryClient = useQueryClient();
  const [editingTarget, setEditingTarget] = useState(false);
  const [targetInput, setTargetInput] = useState('');
  const [savingTarget, setSavingTarget] = useState(false);

  const saveTarget = async () => {
    const parsed = targetInput.trim() === '' ? null : Number(targetInput);
    if (parsed !== null && (Number.isNaN(parsed) || parsed < 0 || parsed > 100)) {
      toast.error('Target must be between 0 and 100');
      return;
    }
    setSavingTarget(true);
    try {
      await studentsApi.setMyTarget(parsed);
      await queryClient.invalidateQueries({ queryKey: ['my-student-profile', studentId] });
      toast.success(parsed === null ? 'Target cleared' : 'Target updated');
      setEditingTarget(false);
    } catch {
      toast.error('Could not update target');
    } finally {
      setSavingTarget(false);
    }
  };

  if (l1 || l2 || l3) return <LoadingPage />;
  if (!summary || summary.total_exams === 0) {
    return (
      <div className="card p-8 text-center flex flex-col items-center gap-2">
        <ClipboardList size={28} className="text-muted" />
        <p className="font-display font-semibold text-primary">No exam results yet</p>
        <p className="text-sm text-secondary max-w-sm">
          Your dashboard will fill in as soon as your first exam or quiz is scored — check back after your next assessment.
        </p>
      </div>
    );
  }

  const target = profile?.target_percentage ?? DEFAULT_TARGET_PERCENTAGE;
  const usingDefaultTarget = profile?.target_percentage == null;
  const average = summary.average_percentage ?? 0;
  const gap = Math.max(0, Math.round((target - average) * 10) / 10);

  const sortedTopics = [...(topics?.topics ?? [])].sort((a, b) => a.average - b.average);
  const weakest = sortedTopics[0];
  const strongest = sortedTopics[sortedTopics.length - 1];

  const chartData = (trend?.timeline ?? []).map((t, i) => ({
    name: t.exam_title.length > 10 ? t.exam_title.slice(0, 10) + '…' : t.exam_title,
    percentage: t.percentage,
    movingAvg: trend?.moving_average[i] ?? t.percentage,
  }));

  const chartGrid = cssVar('--chart-grid') || '#2e2e42';
  const chartAxis = cssVar('--chart-axis') || '#3d3d55';

  const lastScore = summary.recent_scores[0];

  return (
    <div className="flex flex-col gap-5 page-enter">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="page-title">
            {viewerRole === 'guardian' ? (childLabel ?? summary.student_name) : `Hi ${summary.student_name.split(' ')[0]} 👋`}
          </h1>
          <p className="text-muted mt-0.5 text-sm">{summary.classroom ?? 'No classroom'} · {summary.student_code}</p>
        </div>
        <TrendBadge trend={summary.trend} />
      </div>

      {/* ── Stat tiles: where am I, what's my gap, where do I stand ──── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <Reveal index={0}><TiltCard className="card p-4 h-full">
          <p className="label text-xs">Current Average</p>
          <p className={`font-display font-bold text-2xl px-2 py-0.5 rounded-lg inline-block mt-1.5 ${gradeBg(average)}`}>
            {average}%
          </p>
        </TiltCard></Reveal>
        <Reveal index={1}><TiltCard className="card p-4 h-full">
          <div className="flex items-center justify-between gap-1">
            <p className="label text-xs">Gap to Target ({target}%){usingDefaultTarget && viewerRole === 'self' ? ' · default' : ''}</p>
            {viewerRole === 'self' && !editingTarget && (
              <button
                onClick={() => { setTargetInput(profile?.target_percentage != null ? String(profile.target_percentage) : ''); setEditingTarget(true); }}
                className="text-muted hover:text-azure-400 transition-colors flex-shrink-0"
                title="Set your own target"
              >
                <Pencil size={12} />
              </button>
            )}
          </div>
          {editingTarget ? (
            <div className="flex items-center gap-1.5 mt-1.5">
              <input
                type="number" min={0} max={100} autoFocus
                value={targetInput}
                onChange={e => setTargetInput(e.target.value)}
                placeholder="e.g. 80"
                className="w-16 px-2 py-1 rounded-lg bg-surface-800 border border-surface text-sm font-display font-semibold text-primary"
              />
              <button onClick={saveTarget} disabled={savingTarget} className="p-1.5 rounded-lg bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 transition-colors disabled:opacity-50">
                <Check size={13} />
              </button>
              <button onClick={() => setEditingTarget(false)} className="p-1.5 rounded-lg bg-surface-800 text-muted hover:text-primary transition-colors">
                <XIcon size={13} />
              </button>
            </div>
          ) : (
            <p className={`font-display font-bold text-2xl px-2 py-0.5 rounded-lg inline-block mt-1.5 ${gap === 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'}`}>
              {gap === 0 ? 'Reached 🎉' : `${gap} pts`}
            </p>
          )}
        </TiltCard></Reveal>
        <Reveal index={2}><TiltCard className="card p-4 h-full">
          <p className="label text-xs">Class Position</p>
          <p className="font-display font-bold text-2xl px-2 py-0.5 rounded-lg inline-block mt-1.5 bg-azure-500/15 text-azure-400">
            {comparison?.rank != null ? `#${comparison.rank} / ${comparison.class_size}` : '—'}
          </p>
        </TiltCard></Reveal>
        <Reveal index={3}><TiltCard className="card p-4 h-full">
          <p className="label text-xs">Last Result</p>
          <p className={`font-display font-bold text-2xl px-2 py-0.5 rounded-lg inline-block mt-1.5 ${lastScore ? gradeBg(lastScore.percentage) : ''}`}>
            {lastScore ? `${lastScore.percentage}%` : '—'}
          </p>
        </TiltCard></Reveal>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* ── Trend chart ────────────────────────────────────────────── */}
        <div className="xl:col-span-2 card p-5">
          <h2 className="section-title mb-4">Your Trend</h2>
          {chartData.length > 1 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData} margin={{ top: 5, right: 8, bottom: 0, left: -22 }}>
                <defs>
                  <linearGradient id="myTrendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
                <XAxis dataKey="name" tick={{ fill: chartAxis, fontSize: 10, fontFamily: 'DM Sans' }} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} tick={{ fill: chartAxis, fontSize: 10, fontFamily: 'DM Sans' }} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="percentage" stroke="#3b82f6" strokeWidth={2.5} fill="url(#myTrendFill)" dot={{ fill: '#3b82f6', r: 3.5, strokeWidth: 0 }} name="percentage" />
                <Area type="monotone" dataKey="movingAvg" stroke="#a78bfa" strokeWidth={1.5} strokeDasharray="5 3" fill="none" dot={false} name="movingAvg" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex items-center justify-center text-muted text-sm">Need at least 2 exams to show a trend</div>
          )}
          {summary.total_exams >= 2 && (
            <p className="text-xs text-secondary mt-2">
              {summary.trend === 'improving' && `📈 You're improving — keep going.`}
              {summary.trend === 'declining' && `⚠️ Your scores have dipped recently — see the weak topic below.`}
              {summary.trend === 'stable' && `Your results have been steady.`}
            </p>
          )}
        </div>

        {/* ── Weak topic callout + streak/badges ──────────────────────── */}
        <div className="flex flex-col gap-4">
          <div className="card p-5">
            <h2 className="section-title mb-3">Focus Area</h2>
            {weakest ? (
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 flex-shrink-0"><AlertTriangle size={18} /></div>
                <div className="min-w-0">
                  <p className="font-display font-semibold text-primary">{weakest.topic_name}</p>
                  <p className="text-xs text-secondary">Averaging {weakest.average}% — {viewerRole === 'guardian' ? 'their' : 'your'} weakest topic right now.</p>
                  {viewerRole === 'self' && (
                    <Link to="/analytics/topics" className="text-xs font-display font-semibold text-azure-400 hover:text-azure-300 inline-flex items-center gap-1 mt-2">
                      Practice this topic <ArrowRight size={12} />
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted">No topic-level data yet.</p>
            )}
            {strongest && strongest !== weakest && (
              <p className="text-xs text-secondary mt-3 pt-3 border-t border-surface">
                💪 Strongest: <span className="text-emerald-400 font-semibold">{strongest.topic_name}</span> ({strongest.average}%)
              </p>
            )}
          </div>

          <div className="card p-5">
            <h2 className="section-title mb-3">Streak &amp; Badges</h2>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400"><Flame size={18} /></div>
              <div>
                <p className="font-display font-bold text-primary">{progress?.streak?.current_streak ?? 0} exams passed in a row</p>
                <p className="text-xs text-muted">Best: {progress?.streak?.longest_streak ?? 0}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 mt-3">
              <div className="p-2 rounded-lg bg-violet-500/10 text-violet-400"><Trophy size={18} /></div>
              <p className="text-sm text-secondary">{progress?.badges?.length ?? 0} badge{(progress?.badges?.length ?? 0) === 1 ? '' : 's'} earned</p>
            </div>
            {viewerRole === 'self' && (
              <Link to="/progress" className="text-xs font-display font-semibold text-azure-400 hover:text-azure-300 inline-flex items-center gap-1 mt-3">
                View full progress <ArrowRight size={12} />
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* ── Topic progress bars ─────────────────────────────────────── */}
      {sortedTopics.length > 0 && (
        <div className="card p-5">
          <h2 className="section-title mb-4">Topic Breakdown</h2>
          <div className="flex flex-col gap-3">
            {sortedTopics.map(t => (
              <div key={t.topic_id}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-secondary">{t.topic_name}</span>
                  <span className={`font-display font-semibold ${gradeColor(t.average)}`}>{t.average}%</span>
                </div>
                <div className="w-full h-2 rounded-full bg-surface-800 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${t.average}%`, backgroundColor: t.average >= 75 ? '#10b981' : t.average >= 45 ? '#f59e0b' : '#f43f5e' }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Today's mission / quiz progress ─────────────────────────── */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="section-title">Daily Quizzes</h2>
          {viewerRole === 'self' && (
            <Link to="/quizzes" className="text-xs font-display font-semibold text-azure-400 hover:text-azure-300 inline-flex items-center gap-1">
              Go to quizzes <ArrowRight size={12} />
            </Link>
          )}
        </div>
        {quizProgress?.summary ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div><p className="text-muted text-xs">Taken</p><p className="font-display font-semibold text-primary">{quizProgress.summary.quizzes_taken}</p></div>
            <div><p className="text-muted text-xs">Average</p><p className="font-display font-semibold text-primary">{quizProgress.summary.average ?? '—'}%</p></div>
            <div><p className="text-muted text-xs">Quiz streak</p><p className="font-display font-semibold text-primary">{quizProgress.streak?.current_streak ?? 0}</p></div>
            <div><p className="text-muted text-xs">Weakest topic</p><p className="font-display font-semibold text-primary truncate">{quizProgress.summary.weakest_topic ?? '—'}</p></div>
          </div>
        ) : (
          <p className="text-sm text-muted">No quiz activity yet.</p>
        )}
      </div>

      {/* ── Recent results ───────────────────────────────────────────── */}
      <div className="card p-5">
        <h2 className="section-title mb-3">Recent Results</h2>
        <div className="flex flex-col divide-y divide-surface">
          {summary.recent_scores.map(s => (
            <div key={s.exam_id} className="flex items-center justify-between py-2.5 text-sm">
              <div className="min-w-0">
                <p className="text-primary font-medium truncate">{s.exam_title}</p>
                <p className="text-xs text-muted">{formatDate(s.exam_date)}</p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className={`font-display font-bold ${gradeColor(s.percentage)}`}>{s.percentage}%</span>
                <span className="text-xs text-muted">({s.letter_grade})</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
