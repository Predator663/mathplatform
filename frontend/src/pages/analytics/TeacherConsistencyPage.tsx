import { useQuery } from '@tanstack/react-query';
import { Scale, TrendingUp, TrendingDown } from 'lucide-react';
import { analyticsApi } from '../../api';
import { LoadingPage, EmptyState } from '../../components/ui';
import { useSubjectStore } from '../../store/subject';
import type { TeacherGradingConsistency } from '../../types';

export default function TeacherConsistencyPage() {
  const { activeSubjectId } = useSubjectStore();

  const { data, isLoading } = useQuery<TeacherGradingConsistency>({
    queryKey: ['teacher-consistency', activeSubjectId],
    queryFn: () => analyticsApi.teacherConsistency(
      activeSubjectId ? { subject_id: activeSubjectId } : undefined
    ).then(r => r.data),
  });

  const flags = data?.flags ?? [];

  return (
    <div className="flex flex-col gap-4 md:gap-5 page-enter">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <Scale size={20} className="text-violet-400" />
          Teacher Grading Consistency
        </h1>
        <p className="text-muted mt-1 text-sm">
          Compares each teacher's average score on the same topic against their peers. A teacher whose average sits
          1.5 standard deviations or more from the peer mean is flagged as grading meaningfully more leniently or
          harshly than colleagues on the same material.
        </p>
      </div>

      {isLoading ? (
        <LoadingPage />
      ) : flags.length === 0 ? (
        <EmptyState icon={<Scale size={36} className="text-emerald-400" />} title="No inconsistencies detected" message="Grading is consistent across teachers for topics with enough shared data (min. 2 teachers, 5 scores each)." />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {flags.map((f, idx) => (
            <div
              key={`${f.topic}-${f.teacher_id}`}
              className={`card p-4 border ${f.direction === 'lenient' ? 'border-emerald-500/25' : 'border-rose-500/25'}`}
              style={{ animationDelay: `${idx * 30}ms` }}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="min-w-0">
                  <p className="font-display font-semibold text-primary text-sm truncate">{f.teacher_name}</p>
                  <p className="text-xs text-secondary truncate">{f.topic}</p>
                </div>
                <span className={`badge flex items-center gap-1 flex-shrink-0 ${f.direction === 'lenient' ? 'badge-green' : 'badge-rose'}`}>
                  {f.direction === 'lenient' ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                  {f.direction === 'lenient' ? 'Lenient' : 'Harsh'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-[10px] text-secondary uppercase tracking-wider">Their Avg</p>
                  <p className="font-mono font-bold text-primary">{f.teacher_average}%</p>
                </div>
                <div>
                  <p className="text-[10px] text-secondary uppercase tracking-wider">Peer Avg</p>
                  <p className="font-mono font-bold text-secondary">{f.peer_average}%</p>
                </div>
                <div>
                  <p className="text-[10px] text-secondary uppercase tracking-wider">Z-Score</p>
                  <p className={`font-mono font-bold ${f.direction === 'lenient' ? 'text-emerald-400' : 'text-rose-400'}`}>{f.z_score}</p>
                </div>
              </div>
              <p className="text-[11px] text-muted mt-2">Based on {f.sample_size} graded scores.</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
