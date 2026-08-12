import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Flame, Award, Flag, Star, TrendingUp, Trophy, Lock, ClipboardList, Download, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import toast from 'react-hot-toast';
import { gamificationApi, quizzesApi } from '../../api';
import { LoadingPage, StatCard, Button } from '../../components/ui';
import { downloadBlob, gradeColor } from '../../utils';
import type { Badge, StudentProgress, StudentQuizProgress } from '../../types';

const ICONS: Record<string, React.ElementType> = {
  flag: Flag, flame: Flame, star: Star, 'trending-up': TrendingUp, award: Award,
};

function BadgeIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICONS[name] ?? Award;
  return <Icon className={className} />;
}

function formatDate(iso: string | null) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString('en-TZ', { day: '2-digit', month: 'short', year: 'numeric' });
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'improving') return <ArrowUpRight size={13} className="text-emerald-400" />;
  if (trend === 'declining') return <ArrowDownRight size={13} className="text-rose-400" />;
  return <Minus size={13} className="text-secondary" />;
}

export default function MyProgressPage() {
  const [downloading, setDownloading] = useState(false);
  const { data: progress, isLoading: loadingProgress } = useQuery<StudentProgress>({
    queryKey: ['gamification-my-progress'],
    queryFn: () => gamificationApi.myProgress().then(r => r.data),
  });
  const { data: catalog, isLoading: loadingCatalog } = useQuery<Badge[]>({
    queryKey: ['gamification-badges'],
    queryFn: () => gamificationApi.badges().then(r => r.data),
  });
  const { data: quizProgress } = useQuery<StudentQuizProgress>({
    queryKey: ['quiz-my-progress'],
    queryFn: () => quizzesApi.myProgress().then(r => r.data),
  });

  const handleDownloadReport = async () => {
    if (!quizProgress?.student_id) return;
    setDownloading(true);
    try {
      const res = await quizzesApi.progressReportPdf(quizProgress.student_id);
      downloadBlob(res.data as Blob, 'quiz_progress_report.pdf');
    } catch {
      toast.error('Could not download report');
    } finally {
      setDownloading(false);
    }
  };

  if (loadingProgress || loadingCatalog) return <LoadingPage />;
  if (!progress) return null;

  const earnedCodes = new Set(progress.badges.map(b => b.badge.code));
  const earnedByCode = new Map(progress.badges.map(b => [b.badge.code, b]));
  const streak = progress.streak;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="page-title flex items-center gap-2"><Trophy size={22} className="text-amber-400" /> My Progress</h1>
        <p className="text-muted mt-0.5">Track your exam streak and earned badges</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <StatCard label="Current Streak" value={`${streak.current_streak} 🔥`} color="amber"
          sub={streak.current_streak > 0 ? 'exams passed in a row' : 'pass your next exam to start one'} icon={<Flame size={18} />} />
        <StatCard label="Longest Streak" value={String(streak.longest_streak)} color="violet"
          sub="personal best" icon={<Trophy size={18} />} />
        <StatCard label="Badges Earned" value={`${progress.badges.length} / ${catalog?.length ?? 0}`} color="green"
          sub="achievements unlocked" icon={<Award size={18} />} />
      </div>

      {streak.last_exam_title && (
        <div className="card p-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs text-secondary uppercase tracking-widest font-display font-semibold mb-1">Last Exam</p>
            <p className="font-display font-medium text-primary">{streak.last_exam_title}</p>
            {streak.last_exam_date && <p className="text-xs text-secondary mt-0.5">{formatDate(streak.last_exam_date)}</p>}
          </div>
          <span className={`badge ${streak.last_result_passed ? 'badge-green' : 'badge-amber'}`}>
            {streak.last_result_passed ? 'Passed' : 'Below Pass Mark'}
          </span>
        </div>
      )}

      {quizProgress && quizProgress.summary.quizzes_taken > 0 && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="section-title flex items-center gap-2"><ClipboardList size={16} className="text-azure-400" /> Daily Quiz Progress</h2>
            <Button variant="secondary" size="sm" onClick={handleDownloadReport} loading={downloading}>
              <Download size={13} /> Download Report
            </Button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Quiz Streak" value={`${quizProgress.streak.current_streak} 🔥`} color="amber"
              sub="quiz days in a row" icon={<Flame size={18} />} />
            <StatCard label="Quizzes Taken" value={String(quizProgress.summary.quizzes_taken)} color="blue"
              sub="all time" icon={<ClipboardList size={18} />} />
            <StatCard label="Average" value={quizProgress.summary.average != null ? `${quizProgress.summary.average}%` : '—'} color="green"
              sub="across all quizzes" icon={<Trophy size={18} />} />
            <StatCard label="Best Topic" value={quizProgress.summary.best_topic ?? '—'} color="violet"
              sub={quizProgress.summary.weakest_topic ? `Focus: ${quizProgress.summary.weakest_topic}` : ''} icon={<Star size={18} />} />
          </div>

          {quizProgress.topic_data.length > 0 && (
            <div className="card p-4">
              <p className="text-xs text-secondary uppercase tracking-widest font-display font-semibold mb-3">Topic Mastery</p>
              <div className="flex flex-col gap-2">
                {quizProgress.topic_data.map(t => (
                  <div key={t.topic_name} className="flex items-center justify-between gap-2 py-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <TrendIcon trend={t.trend} />
                      <span className="text-sm text-primary truncate">{t.topic_name}</span>
                      <span className="text-xs text-secondary flex-shrink-0">({t.attempts})</span>
                    </div>
                    <span className={`font-mono text-sm font-bold flex-shrink-0 ${gradeColor(t.average)}`}>{t.average}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div>
        <h2 className="section-title mb-3">Badges</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {(catalog ?? []).map(badge => {
            const earned = earnedCodes.has(badge.code);
            const award = earnedByCode.get(badge.code);
            return (
              <div
                key={badge.id}
                className={`card p-4 flex flex-col items-center text-center gap-2 ${earned ? '' : 'opacity-50'}`}
              >
                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 ${
                  earned ? 'bg-amber-500/15 text-amber-400' : 'bg-surface-700 text-secondary'
                }`}>
                  {earned ? <BadgeIcon name={badge.icon} className="w-6 h-6" /> : <Lock size={18} />}
                </div>
                <p className="font-display font-semibold text-sm text-primary leading-tight">{badge.name}</p>
                <p className="text-xs text-secondary leading-snug">{badge.description}</p>
                {earned && award && (
                  <p className="text-[10px] text-secondary mt-1">Earned {formatDate(award.awarded_at)}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
