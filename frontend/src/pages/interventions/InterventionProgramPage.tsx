import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  ChevronLeft, Lock, PlayCircle, CheckCircle2, Circle, Sparkles, TrendingUp, TrendingDown,
  Ban, Search, Target, Users, ClipboardCheck, GraduationCap,
} from 'lucide-react';
import { interventionsApi } from '../../api';
import { LoadingPage, Button, Modal } from '../../components/ui';
import { cn } from '../../utils';
import type { InterventionProgramDetail, InterventionStage } from '../../types';

const STAGE_ICONS = [Search, Target, Users, ClipboardCheck, GraduationCap];

function StageNode({ stage, index, canStart, onStart, onComplete, starting, completing }: {
  stage: InterventionStage; index: number; canStart: boolean;
  onStart: () => void; onComplete: (notes: string) => void;
  starting: boolean; completing: boolean;
}) {
  const [notesOpen, setNotesOpen] = useState(false);
  const [notes, setNotes] = useState('');
  const Icon = STAGE_ICONS[index % STAGE_ICONS.length];

  const isLocked = stage.status === 'pending';
  const isActive = stage.status === 'active';
  const isDone = stage.status === 'completed';

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.06 }}
      className="flex gap-4"
    >
      <div className="flex flex-col items-center">
        <motion.div
          animate={isActive ? { scale: [1, 1.08, 1] } : {}}
          transition={{ repeat: isActive ? Infinity : 0, duration: 1.8 }}
          className={cn(
            'w-11 h-11 rounded-full flex items-center justify-center shrink-0 border-2',
            isDone && 'bg-emerald-500/15 border-emerald-500 text-emerald-400',
            isActive && 'bg-azure-500/15 border-azure-500 text-azure-400 shadow-[0_0_16px_rgba(59,130,246,0.35)]',
            isLocked && 'bg-surface-700 border-surface text-secondary',
          )}
        >
          {isDone ? <CheckCircle2 size={20} /> : isLocked ? (canStart ? <PlayCircle size={18} /> : <Lock size={16} />) : <Icon size={18} />}
        </motion.div>
        <div className="w-0.5 flex-1 bg-surface-700 my-1 min-h-[24px]" />
      </div>

      <div className={cn('flex-1 pb-6 rounded-xl px-4 py-3', isActive && 'bg-azure-500/5 border border-azure-500/20', isDone && 'opacity-90')}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h4 className="font-display font-semibold text-primary">{stage.order}. {stage.title}</h4>
          {isDone && stage.improvement !== null && (
            <span className={cn(
              'flex items-center gap-1 text-xs font-mono font-semibold px-2 py-0.5 rounded-full',
              stage.improvement >= 0 ? 'text-emerald-400 bg-emerald-500/15' : 'text-rose-400 bg-rose-500/15',
            )}>
              {stage.improvement >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {stage.improvement >= 0 ? '+' : ''}{stage.improvement} pts
            </span>
          )}
        </div>
        <p className="text-sm text-secondary mt-1">{stage.description}</p>

        {(isDone || isActive) && (
          <div className="flex items-center gap-4 mt-2 text-xs text-muted font-mono">
            {stage.measured_before !== null && <span>Before: {stage.measured_before}%</span>}
            {stage.measured_after !== null && <span>After: {stage.measured_after}%</span>}
          </div>
        )}
        {stage.notes && <p className="text-xs text-muted italic mt-1.5">"{stage.notes}"</p>}

        <div className="mt-3">
          {isLocked && !canStart && <span className="text-xs text-secondary flex items-center gap-1.5"><Lock size={12} /> Complete the earlier stage to unlock</span>}
          {isLocked && canStart && (
            <Button size="sm" variant="secondary" onClick={onStart} loading={starting}>
              <PlayCircle size={14} /> Start Stage
            </Button>
          )}
          {isActive && (
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={() => setNotesOpen(true)}>
                <CheckCircle2 size={14} /> Mark Complete
              </Button>
            </div>
          )}
          {isDone && <span className="text-xs text-emerald-400 flex items-center gap-1.5"><CheckCircle2 size={12} /> Completed</span>}
        </div>

        <Modal open={notesOpen} onClose={() => setNotesOpen(false)} title={`Complete: ${stage.title}`} size="sm">
          <textarea
            className="input w-full min-h-[90px]" placeholder="Optional notes on what was done…"
            value={notes} onChange={e => setNotes(e.target.value)}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => setNotesOpen(false)}>Cancel</Button>
            <Button
              onClick={() => { onComplete(notes); setNotesOpen(false); setNotes(''); }}
              loading={completing}
            >
              Confirm Complete
            </Button>
          </div>
        </Modal>
      </div>
    </motion.div>
  );
}

export default function InterventionProgramPage() {
  const { id } = useParams<{ id: string }>();
  const programId = Number(id);
  const queryClient = useQueryClient();
  const [discontinuing, setDiscontinuing] = useState(false);

  const { data: program, isLoading } = useQuery<InterventionProgramDetail>({
    queryKey: ['intervention-program', programId],
    queryFn: () => interventionsApi.program(programId).then(r => r.data),
  });

  const startMutation = useMutation({
    mutationFn: (stageId: number) => interventionsApi.startStage(stageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['intervention-program', programId] });
    },
    onError: (err: any) => toast.error(err?.response?.data?.[0] || 'Could not start this stage.'),
  });

  const completeMutation = useMutation({
    mutationFn: ({ stageId, notes }: { stageId: number; notes: string }) => interventionsApi.completeStage(stageId, notes),
    onSuccess: (_res, vars) => {
      toast.success('Stage completed.');
      queryClient.invalidateQueries({ queryKey: ['intervention-program', programId] });
      queryClient.invalidateQueries({ queryKey: ['intervention-programs'] });
    },
    onError: (err: any) => toast.error(err?.response?.data?.[0] || 'Could not complete this stage.'),
  });

  const discontinueMutation = useMutation({
    mutationFn: () => interventionsApi.discontinue(programId),
    onSuccess: () => {
      toast('Program discontinued.');
      queryClient.invalidateQueries({ queryKey: ['intervention-program', programId] });
      queryClient.invalidateQueries({ queryKey: ['intervention-programs'] });
    },
  });

  if (isLoading || !program) return <LoadingPage />;

  const stages = [...program.stages].sort((a, b) => a.order - b.order);
  const pct = program.stage_count ? Math.round((program.completed_stage_count / program.stage_count) * 100) : 0;

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <Link to="/interventions" className="flex items-center gap-1.5 text-sm text-secondary hover:text-primary w-fit">
        <ChevronLeft size={16} /> Back to interventions
      </Link>

      <div>
        <h1 className="text-2xl font-display font-bold text-primary flex items-center gap-2">
          <Sparkles className="text-azure-400" /> {program.student_name}'s Comeback Plan
        </h1>
        <p className="text-secondary text-sm mt-1">{program.trigger_reason}</p>
      </div>

      <div className="card p-4 flex items-center gap-4">
        <div className="flex-1">
          <div className="flex items-center justify-between text-xs text-secondary mb-1">
            <span>Progress</span><span>{program.completed_stage_count}/{program.stage_count} stages</span>
          </div>
          <div className="h-2 bg-surface-700 rounded-full overflow-hidden">
            <motion.div className="h-full bg-gradient-to-r from-azure-500 to-emerald-500 rounded-full"
              initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.7 }} />
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs text-muted">Baseline {program.baseline_average}%</p>
          {program.latest_average !== null && (
            <p className={cn('font-mono font-bold', (program.improvement ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
              Now {program.latest_average}% ({(program.improvement ?? 0) >= 0 ? '+' : ''}{program.improvement})
            </p>
          )}
        </div>
      </div>

      {program.status === 'completed' && (
        <div className="card p-4 bg-emerald-500/10 border-emerald-500/30 flex items-center gap-3">
          <CheckCircle2 className="text-emerald-400" size={22} />
          <p className="text-sm text-primary/90">Program complete — every stage finished. Great work!</p>
        </div>
      )}
      {program.status === 'discontinued' && (
        <div className="card p-4 bg-surface-700/40 border-surface flex items-center gap-3">
          <Ban className="text-secondary" size={20} />
          <p className="text-sm text-secondary">This program was discontinued.</p>
        </div>
      )}

      <div className="flex flex-col">
        <AnimatePresence>
          {stages.map((stage, i) => {
            const prevDone = i === 0 || stages[i - 1].status === 'completed' || stages[i - 1].status === 'skipped';
            return (
              <StageNode
                key={stage.id} stage={stage} index={i} canStart={stage.status === 'pending' && prevDone}
                onStart={() => startMutation.mutate(stage.id)}
                onComplete={(notes) => completeMutation.mutate({ stageId: stage.id, notes })}
                starting={startMutation.isPending}
                completing={completeMutation.isPending}
              />
            );
          })}
        </AnimatePresence>
      </div>

      {program.status === 'active' && (
        <Button variant="ghost" size="sm" className="w-fit" onClick={() => setDiscontinuing(true)}>
          <Ban size={14} /> Discontinue Program
        </Button>
      )}

      <Modal open={discontinuing} onClose={() => setDiscontinuing(false)} title="Discontinue Program?" size="sm">
        <p className="text-sm text-secondary">This stops the plan without marking it complete. You can always start a new one later.</p>
        <div className="flex justify-end gap-3 pt-4">
          <Button variant="ghost" onClick={() => setDiscontinuing(false)}>Cancel</Button>
          <Button variant="danger" onClick={() => { discontinueMutation.mutate(); setDiscontinuing(false); }}>Discontinue</Button>
        </div>
      </Modal>
    </div>
  );
}
