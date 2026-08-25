import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  HeartPulse, TrendingDown, Minus, Plus, ChevronRight, CheckCircle2, XCircle,
  Activity, Users2, ClipboardList,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { interventionsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Select } from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import { cn, apiErrorMessage } from '../../utils';
import type {
  SlowLearnerCandidate, InterventionProgram, InterventionAnalytics, Classroom, PaginatedResponse,
} from '../../types';

function listFrom<T>(data: PaginatedResponse<T> | T[] | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results ?? [];
}

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  active:       { label: 'Active',       color: 'text-azure-400',   bg: 'bg-azure-500/15' },
  completed:    { label: 'Completed',    color: 'text-emerald-400', bg: 'bg-emerald-500/15' },
  discontinued: { label: 'Discontinued', color: 'text-secondary',   bg: 'bg-surface-700' },
};

function CandidateCard({ candidate, classroomId }: { candidate: SlowLearnerCandidate; classroomId: number }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);

  const createMutation = useMutation({
    mutationFn: () => interventionsApi.create({
      student_id: candidate.student_id,
      trigger_reason: `${candidate.trend === 'falling' ? 'Falling' : 'Flat'} trend across ${candidate.exam_count} exams (slope ${candidate.slope} pts/exam).`,
    }),
    onSuccess: () => {
      toast.success(`Intervention started for ${candidate.student_name}.`);
      queryClient.invalidateQueries({ queryKey: ['intervention-candidates', classroomId] });
      queryClient.invalidateQueries({ queryKey: ['intervention-programs'] });
    },
    onError: (err: any) => toast.error(err?.response?.data?.[0] || 'Could not start program.'),
    onSettled: () => setCreating(false),
  });

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="card p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-display font-semibold text-primary">{candidate.student_name}</p>
          <p className="text-xs text-muted">{candidate.student_code} · {candidate.exam_count} exams on record</p>
        </div>
        <span className={cn(
          'flex items-center gap-1 text-xs font-display font-bold uppercase tracking-widest px-2 py-0.5 rounded-full',
          candidate.trend === 'falling' ? 'text-rose-400 bg-rose-500/15' : 'text-amber-400 bg-amber-500/15',
        )}>
          {candidate.trend === 'falling' ? <TrendingDown size={12} /> : <Minus size={12} />} {candidate.trend}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="bg-surface-700/40 rounded-lg p-2 text-center">
          <p className="text-muted">Early Avg</p><p className="font-mono font-semibold text-primary">{candidate.early_average}%</p>
        </div>
        <div className="bg-surface-700/40 rounded-lg p-2 text-center">
          <p className="text-muted">Recent Avg</p><p className="font-mono font-semibold text-primary">{candidate.recent_average}%</p>
        </div>
        <div className="bg-surface-700/40 rounded-lg p-2 text-center">
          <p className="text-muted">Slope</p><p className="font-mono font-semibold text-primary">{candidate.slope}/exam</p>
        </div>
      </div>
      <Button
        size="sm" onClick={() => { setCreating(true); createMutation.mutate(); }} loading={creating}
      >
        <Plus size={14} /> Start Intervention Plan
      </Button>
    </motion.div>
  );
}

function ProgramCard({ program }: { program: InterventionProgram }) {
  const meta = STATUS_META[program.status] ?? STATUS_META.active;
  const pct = program.stage_count ? Math.round((program.completed_stage_count / program.stage_count) * 100) : 0;
  return (
    <Link to={`/interventions/${program.id}`}>
      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="card p-4 flex flex-col gap-3 hover:border-azure-500/40 transition-colors cursor-pointer"
      >
        <div className="flex items-center justify-between">
          <p className="font-display font-semibold text-primary">{program.student_name}</p>
          <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-display font-bold uppercase tracking-widest', meta.color, meta.bg)}>
            {meta.label}
          </span>
        </div>
        <p className="text-xs text-muted truncate">{program.trigger_reason || 'Manually started'}</p>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-azure-500 rounded-full"
              initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.6 }}
            />
          </div>
          <span className="text-[10px] text-secondary font-mono shrink-0">{program.completed_stage_count}/{program.stage_count}</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted">Baseline {program.baseline_average}%</span>
          {program.improvement !== null && (
            <span className={cn('font-mono font-semibold', program.improvement >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
              {program.improvement >= 0 ? '+' : ''}{program.improvement} pts
            </span>
          )}
        </div>
      </motion.div>
    </Link>
  );
}

export default function InterventionsPage() {
  const { user } = useAuthStore();
  const [classroomId, setClassroomId] = useState('');

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms-for-interventions'],
    queryFn: () => studentsApi.classrooms({ page_size: 100 }).then(r => r.data),
  });
  const classrooms = listFrom(classroomsData);

  const { data: candidates, isLoading: candidatesLoading, isError: candidatesError, error: candidatesErr } = useQuery<SlowLearnerCandidate[]>({
    queryKey: ['intervention-candidates', classroomId],
    queryFn: () => interventionsApi.candidates(Number(classroomId)).then(r => r.data),
    enabled: !!classroomId,
    retry: 1,
  });

  const { data: programsData, isLoading: programsLoading, isError: programsError, error: programsErr } = useQuery<PaginatedResponse<InterventionProgram> | InterventionProgram[]>({
    queryKey: ['intervention-programs', classroomId],
    queryFn: () => interventionsApi.programs(classroomId ? { classroom: classroomId } : {}).then(r => r.data),
    retry: 1,
  });
  const programs = listFrom(programsData);

  const { data: analytics } = useQuery<InterventionAnalytics>({
    queryKey: ['intervention-analytics', classroomId],
    queryFn: () => interventionsApi.analytics(classroomId ? { classroom: classroomId } : {}).then(r => r.data),
  });

  if (user?.role === 'student' || user?.role === 'parent') {
    return <EmptyState icon={<HeartPulse size={40} />} title="Not available" message="Intervention plans are managed by teachers and admins." />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold text-primary flex items-center gap-2">
            <HeartPulse className="text-rose-400" /> Intervention Programs
          </h1>
          <p className="text-secondary text-sm mt-1">Spot students with a flat or falling trend and walk them through a staged comeback plan.</p>
        </div>
        <Select
          value={classroomId} onChange={e => setClassroomId(e.target.value)}
          options={[{ value: '', label: 'All classrooms' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]}
        />
      </div>

      {analytics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="stat-card"><span className="label">Active</span><p className="font-display font-bold text-xl text-primary">{analytics.active_count}</p></div>
          <div className="stat-card"><span className="label">Completed</span><p className="font-display font-bold text-xl text-primary">{analytics.completed_count}</p></div>
          <div className="stat-card"><span className="label">Avg Improvement</span><p className="font-display font-bold text-xl text-primary">{analytics.average_improvement ?? '—'}</p></div>
          <div className="stat-card"><span className="label">Success Rate</span><p className="font-display font-bold text-xl text-primary">{analytics.success_rate !== null ? `${analytics.success_rate}%` : '—'}</p></div>
        </div>
      )}

      <section>
        <h2 className="font-display font-semibold text-lg text-primary flex items-center gap-2 mb-3">
          <Activity className="text-amber-400" size={18} /> Candidates for Review
        </h2>
        {!classroomId ? (
          <p className="text-muted text-sm">Select a classroom to scan for students who haven't improved.</p>
        ) : candidatesLoading ? <LoadingPage /> : candidatesError ? (
          <p className="text-rose-400 text-sm">Couldn't load candidates: {apiErrorMessage(candidatesErr)}</p>
        ) : (candidates ?? []).length === 0 ? (
          <p className="text-muted text-sm">No flagged students right now — everyone's trending up.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {(candidates ?? []).map(c => <CandidateCard key={c.student_id} candidate={c} classroomId={Number(classroomId)} />)}
          </div>
        )}
      </section>

      <section>
        <h2 className="font-display font-semibold text-lg text-primary flex items-center gap-2 mb-3">
          <ClipboardList className="text-azure-400" size={18} /> Programs
        </h2>
        {programsLoading ? <LoadingPage /> : programsError ? (
          <p className="text-rose-400 text-sm">Couldn't load programs: {apiErrorMessage(programsErr)}</p>
        ) : programs.length === 0 ? (
          <EmptyState icon={<Users2 size={36} />} title="No programs yet" message="Start one from a flagged candidate above." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {programs.map(p => <ProgramCard key={p.id} program={p} />)}
          </div>
        )}
      </section>
    </div>
  );
}
