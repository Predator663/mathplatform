import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, Radar } from 'lucide-react';
import { analyticsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Select } from '../../components/ui';
import { useSubjectStore } from '../../store/subject';
import type { ClassroomRiskScores, Classroom, PaginatedResponse, RiskLevel, Stream } from '../../types';

const LEVEL_STYLE: Record<RiskLevel, { bg: string; text: string; label: string }> = {
  critical: { bg: 'bg-rose-500/10 border-rose-500/30',   text: 'text-rose-400',   label: 'Critical' },
  high:     { bg: 'bg-orange-500/10 border-orange-500/30', text: 'text-orange-400', label: 'High' },
  moderate: { bg: 'bg-amber-500/10 border-amber-500/30',  text: 'text-amber-400',  label: 'Moderate' },
  low:      { bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', label: 'Low' },
  insufficient_data: { bg: 'bg-surface-700 border-surface', text: 'text-secondary', label: 'Insufficient Data' },
};

export default function RiskScoresPage() {
  const navigate = useNavigate();
  const [selectedClass, setSelectedClass] = useState<number | null>(null);
  const [streamId, setStreamId] = useState('');
  const { activeSubjectId } = useSubjectStore();

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms', activeSubjectId],
    queryFn: () => studentsApi.classrooms(activeSubjectId ? { subject_id: activeSubjectId } : undefined).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data: streamsData } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams-for-risk', selectedClass],
    queryFn: () => studentsApi.streams({ classroom: selectedClass, page_size: 200 }).then(r => r.data),
    enabled: !!selectedClass,
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const { data, isLoading } = useQuery<ClassroomRiskScores>({
    queryKey: ['classroom-risk', selectedClass, activeSubjectId, streamId],
    queryFn: () => analyticsApi.classroomRisk(selectedClass!, {
      stream_id: streamId || undefined,
      ...(activeSubjectId ? { subject_id: activeSubjectId } : {}),
    }).then(r => r.data),
    enabled: !!selectedClass,
  });

  const students = data?.students ?? [];

  return (
    <div className="flex flex-col gap-4 md:gap-5 page-enter">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <ShieldAlert size={20} className="text-orange-400" />
          Composite Risk Scores
        </h1>
        <p className="text-muted mt-1 text-sm">
          A weighted 0–100 score combining trend, volatility, topic weakness, and pass margin — with the contributing
          factors shown so you can see <em>why</em> a student is flagged, not just that they are.
        </p>
      </div>

      <div className="card p-4 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[200px]">
          <Select
            label="Classroom"
            options={[
              { value: '', label: 'Select a classroom…' },
              ...classrooms.map(c => ({ value: c.id, label: `${c.name}${c.grade_level_name ? ` — ${c.grade_level_name}` : ''}` })),
            ]}
            value={selectedClass ?? ''}
            onChange={e => { setSelectedClass(e.target.value ? Number(e.target.value) : null); setStreamId(''); }}
          />
        </div>
        {streams.length > 0 && (
          <div className="w-44">
            <Select
              label="Stream"
              options={[{ value: '', label: 'All Streams' }, ...streams.map(s => ({ value: s.id, label: `Stream ${s.name}` }))]}
              value={streamId}
              onChange={e => setStreamId(e.target.value)}
            />
          </div>
        )}
      </div>

      {!selectedClass ? (
        <EmptyState icon={<Radar size={36} className="text-muted" />} title="Choose a classroom" message="Select a classroom above to compute risk scores for its students." />
      ) : isLoading ? (
        <LoadingPage />
      ) : students.length === 0 ? (
        <EmptyState icon={<ShieldAlert size={36} className="text-emerald-400" />} title="No risk data yet" message="Students in this classroom don't have enough exam history yet." />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {students.map((s, idx) => {
            const style = LEVEL_STYLE[s.risk_level];
            return (
              <div
                key={s.student_id}
                className={`card p-4 border cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-lg ${style.bg}`}
                style={{ animationDelay: `${idx * 40}ms` }}
                onClick={() => navigate(`/analytics/student/${s.student_id}`)}
              >
                <div className="flex items-start justify-between mb-3">
                  <p className="font-display font-semibold text-primary text-sm truncate pr-2">{s.student_name}</p>
                  <div className="flex flex-col items-end flex-shrink-0">
                    <span className={`font-display font-black text-2xl ${style.text}`}>{s.risk_score ?? '—'}</span>
                    <span className={`text-[10px] font-display font-semibold uppercase tracking-wider ${style.text}`}>{style.label}</span>
                  </div>
                </div>

                <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden mb-3">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${s.risk_score ?? 0}%`, backgroundColor: style.text.includes('rose') ? '#f43f5e' : style.text.includes('orange') ? '#fb923c' : style.text.includes('amber') ? '#f59e0b' : '#10b981' }}
                  />
                </div>

                {s.factors && (
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-secondary">
                    <p>Recent avg: <span className="text-primary font-mono">{s.factors.recent_average ?? '—'}%</span></p>
                    <p>Volatility: <span className="text-primary font-mono">{s.factors.volatility ?? '—'}</span></p>
                    <p>Trend slope: <span className="text-primary font-mono">{s.factors.recent_trend_slope ?? '—'}</span></p>
                    <p>Weakest topics: <span className="text-primary font-mono">{s.factors.weakest_topics_avg ?? '—'}%</span></p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
