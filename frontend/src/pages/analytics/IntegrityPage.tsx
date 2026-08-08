import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ShieldCheck, ArrowUpRight, Zap, Users } from 'lucide-react';
import { analyticsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Select, Pagination } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useSubjectStore } from '../../store/subject';
import { formatDate } from '../../utils';
import type { IntegrityFlags, Classroom, PaginatedResponse, Stream } from '../../types';

export default function IntegrityPage() {
  const [selectedClass, setSelectedClass] = useState<number | null>(null);
  const [streamId, setStreamId] = useState('');
  const [crossingsPage, setCrossingsPage] = useState(1);
  const [jumpsPage, setJumpsPage] = useState(1);
  const [editorsPage, setEditorsPage] = useState(1);
  const { activeSubjectId } = useSubjectStore();
  const { getPage } = useSiteSettingsStore();
  const pageSize = getPage('exams').page_size;

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms', activeSubjectId],
    queryFn: () => studentsApi.classrooms(activeSubjectId ? { subject_id: activeSubjectId } : undefined).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  // Streams are per-classroom, so this filter only appears once one classroom is chosen.
  const { data: streamsData } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams-for-integrity', selectedClass],
    queryFn: () => studentsApi.streams({ classroom: selectedClass, page_size: 200 }).then(r => r.data),
    enabled: !!selectedClass,
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const { data, isLoading } = useQuery<IntegrityFlags>({
    queryKey: ['integrity-flags', selectedClass, activeSubjectId, streamId],
    queryFn: () => analyticsApi.integrityFlags({
      ...(selectedClass ? { classroom_id: selectedClass } : {}),
      stream_id: streamId || undefined,
      ...(activeSubjectId ? { subject_id: activeSubjectId } : {}),
    }).then(r => r.data),
  });

  const boundaryCrossings = data?.boundary_crossings ?? [];
  const largeJumps = data?.large_jumps ?? [];
  const editorRates = data?.editor_rates ?? [];

  const pageSlice = <T,>(items: T[], page: number) => items.slice((page - 1) * pageSize, page * pageSize);
  const visibleCrossings = pageSlice(boundaryCrossings, crossingsPage);
  const visibleJumps = pageSlice(largeJumps, jumpsPage);
  const visibleEditors = pageSlice(editorRates, editorsPage);

  const handleClassroomChange = (val: number | null) => {
    setSelectedClass(val);
    setStreamId('');
    setCrossingsPage(1); setJumpsPage(1); setEditorsPage(1);
  };
  const handleStreamChange = (val: string) => {
    setStreamId(val);
    setCrossingsPage(1); setJumpsPage(1); setEditorsPage(1);
  };

  return (
    <div className="flex flex-col gap-4 md:gap-5 page-enter">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <ShieldCheck size={20} className="text-azure-400" />
          Grade Integrity
        </h1>
        <p className="text-muted mt-1 text-sm">
          Mines score-edit history for patterns worth a human review — these are descriptive flags, not accusations.
          A boundary-crossing edit and an honest correction can look identical in isolation.
        </p>
      </div>

      <div className="card p-4 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[200px]">
          <Select
            label="Classroom (optional)"
            options={[
              { value: '', label: 'All Classrooms' },
              ...classrooms.map(c => ({ value: c.id, label: `${c.name}${c.grade_level_name ? ` — ${c.grade_level_name}` : ''}` })),
            ]}
            value={selectedClass ?? ''}
            onChange={e => handleClassroomChange(e.target.value ? Number(e.target.value) : null)}
          />
        </div>
        {streams.length > 0 && (
          <div className="w-44">
            <Select
              label="Stream"
              options={[{ value: '', label: 'All Streams' }, ...streams.map(s => ({ value: s.id, label: `Stream ${s.name}` }))]}
              value={streamId}
              onChange={e => handleStreamChange(e.target.value)}
            />
          </div>
        )}
      </div>

      {isLoading ? (
        <LoadingPage />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="card p-4 border border-rose-500/20">
              <p className="text-[10px] text-secondary uppercase tracking-wider font-display">Boundary Crossings</p>
              <p className="font-display font-bold text-2xl text-rose-400 mt-1">{data?.boundary_crossing_count ?? 0}</p>
              <p className="text-[11px] text-muted mt-1">Edits that moved a score from fail to pass</p>
            </div>
            <div className="card p-4 border border-amber-500/20">
              <p className="text-[10px] text-secondary uppercase tracking-wider font-display">Large Jumps</p>
              <p className="font-display font-bold text-2xl text-amber-400 mt-1">{data?.large_jump_count ?? 0}</p>
              <p className="text-[11px] text-muted mt-1">Edits shifting a score by a large margin</p>
            </div>
            <div className="card p-4 border border-azure-500/20">
              <p className="text-[10px] text-secondary uppercase tracking-wider font-display">Editors Tracked</p>
              <p className="font-display font-bold text-2xl text-azure-400 mt-1">{editorRates.length}</p>
              <p className="text-[11px] text-muted mt-1">Teachers who have edited entered scores</p>
            </div>
          </div>

          {/* Boundary crossings */}
          <div className="card p-5">
            <h2 className="section-title mb-4 flex items-center gap-2"><ArrowUpRight size={16} className="text-rose-400" /> Boundary Crossings</h2>
            {boundaryCrossings.length === 0 ? (
              <p className="text-muted text-sm text-center py-6">No fail→pass edits found.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {visibleCrossings.map(e => (
                  <div key={e.edit_id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl bg-surface-900">
                    <div className="min-w-0">
                      <p className="text-sm font-display font-medium text-primary">{e.student_name} — {e.exam_title}</p>
                      <p className="text-xs text-secondary mt-0.5">
                        {formatDate(e.exam_date)} · edited by {e.changed_by} · {formatDate(e.changed_at)}
                        {e.reason ? ` · "${e.reason}"` : ''}
                      </p>
                    </div>
                    <span className="font-mono text-sm font-bold text-rose-400 flex-shrink-0">
                      {e.old_percentage}% → {e.new_percentage}%
                    </span>
                  </div>
                ))}
                <Pagination page={crossingsPage} pageSize={pageSize} total={boundaryCrossings.length} onChange={setCrossingsPage} />
              </div>
            )}
          </div>

          {/* Large jumps */}
          <div className="card p-5">
            <h2 className="section-title mb-4 flex items-center gap-2"><Zap size={16} className="text-amber-400" /> Large Score Jumps</h2>
            {largeJumps.length === 0 ? (
              <p className="text-muted text-sm text-center py-6">No large edits found.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {visibleJumps.map(e => (
                  <div key={e.edit_id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl bg-surface-900">
                    <div className="min-w-0">
                      <p className="text-sm font-display font-medium text-primary">{e.student_name} — {e.exam_title}</p>
                      <p className="text-xs text-secondary mt-0.5">
                        {formatDate(e.exam_date)} · edited by {e.changed_by} · {formatDate(e.changed_at)}
                        {e.reason ? ` · "${e.reason}"` : ''}
                      </p>
                    </div>
                    <span className={`font-mono text-sm font-bold flex-shrink-0 ${e.delta > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {e.delta > 0 ? '+' : ''}{e.delta} pts
                    </span>
                  </div>
                ))}
                <Pagination page={jumpsPage} pageSize={pageSize} total={largeJumps.length} onChange={setJumpsPage} />
              </div>
            )}
          </div>

          {/* Editor rates */}
          <div className="card p-5">
            <h2 className="section-title mb-4 flex items-center gap-2"><Users size={16} className="text-azure-400" /> Editor Rates</h2>
            {editorRates.length === 0 ? (
              <p className="text-muted text-sm text-center py-6">No edits recorded.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {visibleEditors.map(r => (
                  <div key={r.teacher_id} className="flex items-center justify-between gap-2 p-3 rounded-xl bg-surface-900">
                    <p className="text-sm font-display font-medium text-primary truncate">{r.teacher_name}</p>
                    <p className="text-xs text-secondary flex-shrink-0">
                      {r.edits_made} edits / {r.scores_entered} entered
                      {r.edit_rate_percent != null && (
                        <span className="ml-2 font-mono font-bold text-primary">{r.edit_rate_percent}%</span>
                      )}
                    </p>
                  </div>
                ))}
                <Pagination page={editorsPage} pageSize={pageSize} total={editorRates.length} onChange={setEditorsPage} />
              </div>
            )}
          </div>
        </>
      )}

      {!isLoading && boundaryCrossings.length === 0 && largeJumps.length === 0 && editorRates.length === 0 && (
        <EmptyState icon={<ShieldCheck size={36} className="text-emerald-400" />} title="No anomalies detected" message="No suspicious score-edit patterns were found in the selected scope." />
      )}
    </div>
  );
}
