import { useQuery } from '@tanstack/react-query';
import { Flame, Award, Flag, Star, TrendingUp, Trophy, Lock } from 'lucide-react';
import { gamificationApi } from '../../api';
import { LoadingPage, StatCard } from '../../components/ui';
import type { Badge, StudentProgress } from '../../types';

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

export default function MyProgressPage() {
  const { data: progress, isLoading: loadingProgress } = useQuery<StudentProgress>({
    queryKey: ['gamification-my-progress'],
    queryFn: () => gamificationApi.myProgress().then(r => r.data),
  });
  const { data: catalog, isLoading: loadingCatalog } = useQuery<Badge[]>({
    queryKey: ['gamification-badges'],
    queryFn: () => gamificationApi.badges().then(r => r.data),
  });

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
