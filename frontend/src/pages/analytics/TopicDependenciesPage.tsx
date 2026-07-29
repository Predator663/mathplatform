import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { GitBranch, ArrowRight, Network } from 'lucide-react';
import { analyticsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Select } from '../../components/ui';
import { useSubjectStore } from '../../store/subject';
import type { TopicDependencyChains, Classroom, PaginatedResponse, Stream } from '../../types';

export default function TopicDependenciesPage() {
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
    queryKey: ['streams-for-dependencies', selectedClass],
    queryFn: () => studentsApi.streams({ classroom: selectedClass, page_size: 200 }).then(r => r.data),
    enabled: !!selectedClass,
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const { data, isLoading } = useQuery<TopicDependencyChains>({
    queryKey: ['topic-dependencies', selectedClass, activeSubjectId, streamId],
    queryFn: () => analyticsApi.topicDependencies(selectedClass!, {
      stream_id: streamId || undefined,
      ...(activeSubjectId ? { subject_id: activeSubjectId } : {}),
    }).then(r => r.data),
    enabled: !!selectedClass,
  });

  const chains = data?.dependency_chains ?? [];

  return (
    <div className="flex flex-col gap-4 md:gap-5 page-enter">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <GitBranch size={20} className="text-violet-400" />
          Root-Cause Topic Dependencies
        </h1>
        <p className="text-muted mt-1 text-sm">
          Detects when weakness in one topic statistically predicts weakness in another — e.g. students weak in
          Fractions failing Algebra at a much higher rate than the class baseline. A <strong>lift</strong> above 1.3×
          is surfaced as a candidate root-cause dependency.
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
        <EmptyState icon={<Network size={36} className="text-muted" />} title="Choose a classroom" message="Select a classroom above to detect topic dependency chains." />
      ) : isLoading ? (
        <LoadingPage />
      ) : chains.length === 0 ? (
        <EmptyState icon={<Network size={36} className="text-emerald-400" />} title="No strong dependencies detected" message="Either topics are largely independent in this classroom, or there isn't enough data yet (needs at least 5 co-occurring students per pair)." />
      ) : (
        <div className="flex flex-col gap-2.5">
          {chains.map((c, idx) => (
            <div
              key={`${c.from_topic}-${c.to_topic}`}
              className="card p-4 border border-violet-500/20"
              style={{ animationDelay: `${idx * 30}ms` }}
            >
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="badge badge-rose text-[11px]">{c.from_topic}</span>
                <ArrowRight size={14} className="text-secondary flex-shrink-0" />
                <span className="badge badge-amber text-[11px]">{c.to_topic}</span>
                <span className="ml-auto font-display font-black text-lg text-violet-400">{c.lift}×</span>
              </div>
              <p className="text-xs text-secondary leading-relaxed">
                Students weak in <strong className="text-primary">{c.from_topic}</strong> are weak in{' '}
                <strong className="text-primary">{c.to_topic}</strong>{' '}
                <strong className="text-violet-400">{c.lift}× more often</strong> than the class baseline
                ({c.conditional_weak_rate}% vs {c.baseline_weak_rate}%, based on {c.sample_size} students).
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
