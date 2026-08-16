import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  Swords, Trophy, Crown, Shield, ShieldCheck, Zap, Sparkles, Star, TrendingUp, Flag,
  Plus, X, Play, Lock, Radio, Target, Users2, School, Clock, ChevronRight, Award, Flame,
  CheckCircle2, AlertTriangle, Ban, Skull, Eye, ScanLine, ListChecks,
} from 'lucide-react';
import { tournamentsApi, studentsApi, examsApi, gamificationApi } from '../../api';
import {
  LoadingPage, EmptyState, Button, Input, Select, Modal, StatCard, SearchableSelect,
} from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import { cn, gradeColor } from '../../utils';
import type {
  Tournament, TournamentDetail, TournamentEntry, Challenge, EntryResult, TournamentIntel,
  MyTournamentEntryRow, Classroom, Stream, Exam, PaginatedResponse, Badge, StudentProgress,
} from '../../types';

// ── Badge icon map (mirrors MyProgressPage's) ──────────────────────────────
const BADGE_ICONS: Record<string, React.ElementType> = {
  flag: Flag, flame: Flame, star: Star, 'trending-up': TrendingUp, award: Award,
  shield: Shield, 'shield-check': ShieldCheck, swords: Swords, crown: Crown,
  zap: Zap, sparkles: Sparkles, trophy: Trophy,
};
function BadgeGlyph({ name, className }: { name: string; className?: string }) {
  const Icon = BADGE_ICONS[name] ?? Award;
  return <Icon className={className} />;
}

const STATUS_META: Record<string, { label: string; color: string; bg: string; icon: React.ElementType }> = {
  draft:                { label: 'Draft',               color: 'text-secondary',  bg: 'bg-surface-700',      icon: Lock },
  registration_open:    { label: 'Registration Open',   color: 'text-emerald-400', bg: 'bg-emerald-500/15',  icon: Radio },
  registration_closed:  { label: 'Registration Closed', color: 'text-amber-400',   bg: 'bg-amber-500/15',    icon: Ban },
  live:                 { label: 'Live',                color: 'text-rose-400',    bg: 'bg-rose-500/15',     icon: Play },
  completed:            { label: 'Completed',           color: 'text-azure-400',   bg: 'bg-azure-500/15',    icon: CheckCircle2 },
  cancelled:            { label: 'Cancelled',           color: 'text-secondary',   bg: 'bg-surface-700',     icon: Ban },
};

function StatusPill({ status }: { status: string }) {
  const m = STATUS_META[status] ?? STATUS_META.draft;
  const Icon = m.icon;
  return (
    <span className={cn('inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-display font-bold uppercase tracking-widest', m.color, m.bg)}>
      <Icon size={10} /> {m.label}
    </span>
  );
}

// ── Live countdown ──────────────────────────────────────────────────────────
function useCountdown(targetIso: string | null | undefined) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!targetIso) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [targetIso]);
  if (!targetIso) return null;
  const target = new Date(targetIso).getTime();
  const diff = target - now;
  const expired = diff <= 0;
  const abs = Math.abs(diff);
  const days = Math.floor(abs / 86_400_000);
  const hours = Math.floor((abs % 86_400_000) / 3_600_000);
  const minutes = Math.floor((abs % 3_600_000) / 60_000);
  const seconds = Math.floor((abs % 60_000) / 1000);
  return { expired, days, hours, minutes, seconds };
}

function CountdownBlock({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center gap-0.5 min-w-[46px]">
      <span className="font-mono font-black text-lg md:text-xl text-primary tabular-nums">{String(value).padStart(2, '0')}</span>
      <span className="text-[9px] uppercase tracking-widest text-secondary">{label}</span>
    </div>
  );
}

function Countdown({ targetIso, expiredLabel }: { targetIso: string | null | undefined; expiredLabel: string }) {
  const cd = useCountdown(targetIso);
  if (!cd) return null;
  if (cd.expired) {
    return (
      <div className="flex items-center gap-1.5 text-rose-400 font-display font-semibold text-sm">
        <Clock size={14} /> {expiredLabel}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2.5">
      <CountdownBlock label="Days" value={cd.days} />
      <span className="text-secondary font-bold pb-3">:</span>
      <CountdownBlock label="Hrs" value={cd.hours} />
      <span className="text-secondary font-bold pb-3">:</span>
      <CountdownBlock label="Min" value={cd.minutes} />
      <span className="text-secondary font-bold pb-3">:</span>
      <CountdownBlock label="Sec" value={cd.seconds} />
    </div>
  );
}

function listFrom<T>(data: PaginatedResponse<T> | T[] | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results ?? [];
}

// ── Create Tournament Modal ─────────────────────────────────────────────────
function CreateTournamentModal({ open, onClose, classrooms }: { open: boolean; onClose: () => void; classrooms: Classroom[] }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState('');
  const [codename, setCodename] = useState('');
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState<'individual' | 'stream'>('individual');
  const [classroomId, setClassroomId] = useState('');
  const [examId, setExamId] = useState('');
  const [deadline, setDeadline] = useState('');
  const [maxEntrants, setMaxEntrants] = useState('');
  const [isPublic, setIsPublic] = useState(true);

  const { data: examsData } = useQuery<PaginatedResponse<Exam> | Exam[]>({
    queryKey: ['exams-for-tournament', classroomId],
    queryFn: () => examsApi.exams({ classrooms: classroomId, page_size: 100 }).then(r => r.data),
    enabled: !!classroomId,
  });
  const exams = listFrom(examsData);

  const reset = () => {
    setTitle(''); setCodename(''); setDescription(''); setMode('individual');
    setClassroomId(''); setExamId(''); setDeadline(''); setMaxEntrants(''); setIsPublic(true);
  };

  const createMutation = useMutation({
    mutationFn: () => tournamentsApi.create({
      title, codename, description, mode,
      classroom: Number(classroomId), exam: Number(examId),
      registration_deadline: new Date(deadline).toISOString(),
      max_entrants: maxEntrants ? Number(maxEntrants) : null,
      is_public: isPublic,
    }),
    onSuccess: () => {
      toast.success('Operation created — open registration when ready');
      queryClient.invalidateQueries({ queryKey: ['tournaments'] });
      reset(); onClose();
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Could not create tournament'),
  });

  return (
    <Modal open={open} onClose={onClose} title="Launch New Tournament" size="lg" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button onClick={() => createMutation.mutate()} loading={createMutation.isPending}
          disabled={!title || !classroomId || !examId || !deadline}>
          <Plus size={14} /> Create Operation
        </Button>
      </>
    }>
      <div className="flex flex-col gap-4">
        <Input label="Title" placeholder="Form 4 Terminal Showdown" value={title} onChange={e => setTitle(e.target.value)} />
        <Input label="Codename (optional)" placeholder="OPERATION HISABATI" value={codename} onChange={e => setCodename(e.target.value)} />
        <div className="flex flex-col gap-1.5">
          <label className="label">Description</label>
          <textarea className="input min-h-[70px]" value={description} onChange={e => setDescription(e.target.value)} placeholder="What's this tournament about?" />
        </div>

        <div>
          <label className="label mb-1.5 block">Mode</label>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" onClick={() => setMode('individual')}
              className={cn('card p-3 flex items-center gap-2 text-sm font-display font-semibold transition-all',
                mode === 'individual' ? 'ring-2 ring-azure-500 text-azure-400' : 'text-secondary')}>
              <Swords size={16} /> Student vs Student
            </button>
            <button type="button" onClick={() => setMode('stream')}
              className={cn('card p-3 flex items-center gap-2 text-sm font-display font-semibold transition-all',
                mode === 'stream' ? 'ring-2 ring-violet-500 text-violet-400' : 'text-secondary')}>
              <Users2 size={16} /> Stream vs Stream
            </button>
          </div>
        </div>

        <Select label="Classroom" value={classroomId} onChange={e => { setClassroomId(e.target.value); setExamId(''); }}
          options={[{ value: '', label: 'Select classroom…' }, ...classrooms.map(c => ({ value: c.id, label: `${c.name} — ${c.academic_year}` }))]} />

        <Select label="Decisive Exam" value={examId} onChange={e => setExamId(e.target.value)} disabled={!classroomId}
          options={[{ value: '', label: classroomId ? 'Select exam…' : 'Choose a classroom first' },
            ...exams.map(ex => ({ value: ex.id, label: `${ex.title} (${ex.exam_date})` }))]} />

        <Input label="Registration Deadline" type="datetime-local" value={deadline} onChange={e => setDeadline(e.target.value)} />
        <Input label="Max Entrants (optional)" type="number" min="2" value={maxEntrants} onChange={e => setMaxEntrants(e.target.value)} placeholder="No limit" />

        <label className="flex items-center gap-2 text-sm text-primary cursor-pointer">
          <input type="checkbox" checked={isPublic} onChange={e => setIsPublic(e.target.checked)} className="w-4 h-4 rounded accent-azure-500" />
          Students may self-register
        </label>
      </div>
    </Modal>
  );
}

// ── Register Entry Modal ────────────────────────────────────────────────────
function RegisterEntryModal({ open, onClose, tournament }: { open: boolean; onClose: () => void; tournament: TournamentDetail }) {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const isStaff = user?.role === 'teacher' || user?.role === 'super_admin';
  const [studentId, setStudentId] = useState('');
  const [streamId, setStreamId] = useState('');

  const { data: studentsData } = useQuery<PaginatedResponse<any> | any[]>({
    queryKey: ['students-for-tournament', tournament.classroom],
    queryFn: () => studentsApi.students({ classroom: tournament.classroom, page_size: 300 }).then(r => r.data),
    enabled: open && tournament.mode === 'individual' && isStaff,
  });
  const students = listFrom(studentsData);
  const registeredStudentIds = new Set(tournament.entries.filter(e => e.student_id).map(e => e.student_id));

  const { data: streamsData } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams-for-tournament', tournament.classroom],
    queryFn: () => studentsApi.streams({ classroom: tournament.classroom, page_size: 100 }).then(r => r.data),
    enabled: open && tournament.mode === 'stream',
  });
  const streams = listFrom(streamsData);
  const registeredStreamIds = new Set(tournament.entries.filter(e => e.stream_id).map(e => e.stream_id));

  const registerMutation = useMutation({
    mutationFn: () => tournamentsApi.register(tournament.id, tournament.mode === 'individual'
      ? { student_id: Number(studentId) } : { stream_id: Number(streamId) }),
    onSuccess: () => {
      toast.success('Registered for the operation');
      queryClient.invalidateQueries({ queryKey: ['tournament', tournament.id] });
      setStudentId(''); setStreamId(''); onClose();
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Registration failed'),
  });

  const selfRegister = () => {
    const my = (user as any)?.student_profile_id;
    tournamentsApi.register(tournament.id, { student_id: my }).then(() => {
      toast.success("You're in! Good luck.");
      queryClient.invalidateQueries({ queryKey: ['tournament', tournament.id] });
      onClose();
    }).catch((err: any) => toast.error(err?.response?.data?.detail || 'Could not register'));
  };

  return (
    <Modal open={open} onClose={onClose} title={tournament.mode === 'individual' ? 'Register a Combatant' : 'Register a Stream'}
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button onClick={() => registerMutation.mutate()} loading={registerMutation.isPending}
          disabled={tournament.mode === 'individual' ? !studentId : !streamId}>
          <Plus size={14} /> Register
        </Button>
      </>}>
      {tournament.mode === 'individual' ? (
        <SearchableSelect
          label="Student"
          placeholder="Search students…"
          options={students
            .filter((s: any) => !registeredStudentIds.has(s.id))
            .map((s: any) => ({ value: s.id, label: `${s.full_name} (${s.student_id})` }))}
          value={studentId}
          onChange={setStudentId}
        />
      ) : (
        <Select label="Stream" value={streamId} onChange={e => setStreamId(e.target.value)}
          options={[{ value: '', label: 'Select a stream…' },
            ...streams.filter(s => !registeredStreamIds.has(s.id)).map(s => ({ value: s.id, label: `${s.name} (${s.student_count} students)` }))]} />
      )}
    </Modal>
  );
}

// ── Create Challenge Modal ──────────────────────────────────────────────────
function CreateChallengeModal({ open, onClose, tournament }: { open: boolean; onClose: () => void; tournament: TournamentDetail }) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState('');
  const [selected, setSelected] = useState<number[]>([]);

  const toggle = (id: number) => setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const createMutation = useMutation({
    mutationFn: () => tournamentsApi.createChallenge(tournament.id, { label, entry_ids: selected }),
    onSuccess: () => {
      toast.success('Challenge declared!');
      queryClient.invalidateQueries({ queryKey: ['tournament', tournament.id] });
      setLabel(''); setSelected([]); onClose();
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Could not create the challenge'),
  });

  return (
    <Modal open={open} onClose={onClose} title="Declare a Challenge" size="md" footer={
      <>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button onClick={() => createMutation.mutate()} loading={createMutation.isPending} disabled={selected.length < 2}>
          <Swords size={14} /> Declare
        </Button>
      </>
    }>
      <div className="flex flex-col gap-4">
        <Input label="Label (optional)" placeholder="e.g. Front Row Showdown" value={label} onChange={e => setLabel(e.target.value)} />
        <div>
          <label className="label mb-2 block">Combatants (pick 2 or more)</label>
          <div className="flex flex-col gap-1.5 max-h-64 overflow-y-auto">
            {tournament.entries.map(entry => (
              <label key={entry.id} className={cn('flex items-center gap-2.5 px-3 py-2 rounded-xl cursor-pointer transition-colors',
                selected.includes(entry.id) ? 'bg-azure-500/15 text-azure-400' : 'hover:bg-surface-700 text-primary')}>
                <input type="checkbox" checked={selected.includes(entry.id)} onChange={() => toggle(entry.id)} className="w-4 h-4 rounded accent-azure-500" />
                <span className="text-sm font-medium flex-1">{entry.display_name}</span>
                {entry.seed_average != null && <span className="text-xs text-secondary font-mono">seed {entry.seed_average}%</span>}
              </label>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Leaderboard row ──────────────────────────────────────────────────────────
function RankBadge({ rank }: { rank: number | null }) {
  if (rank == null) return <span className="text-secondary text-xs">—</span>;
  if (rank === 1) return <span className="inline-flex items-center gap-1 text-amber-400 font-display font-black"><Crown size={16} /> 1st</span>;
  if (rank === 2) return <span className="inline-flex items-center gap-1 text-slate-300 font-display font-bold"><Trophy size={14} /> 2nd</span>;
  if (rank === 3) return <span className="inline-flex items-center gap-1 text-orange-400 font-display font-bold"><Trophy size={14} /> 3rd</span>;
  return <span className="font-mono text-sm text-secondary">#{rank}</span>;
}

function LeaderboardTable({ rows }: { rows: EntryResult[] }) {
  if (rows.length === 0) return <EmptyState icon={<ScanLine size={28} />} title="No results yet" message="Finalize the tournament once the exam is published and scored." />;
  return (
    <div className="flex flex-col gap-1.5">
      {rows.map(r => (
        <motion.div key={r.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
          className={cn('card p-3 flex items-center gap-3',
            r.is_champion && 'ring-1 ring-amber-500/50 bg-amber-500/5')}>
          <div className="w-14 flex-shrink-0"><RankBadge rank={r.rank} /></div>
          <div className="flex-1 min-w-0">
            <p className="font-display font-semibold text-sm text-primary truncate flex items-center gap-1.5">
              {r.entry.display_name}
              {r.is_champion && <Crown size={13} className="text-amber-400 flex-shrink-0" />}
              {r.is_rising_star && <Sparkles size={13} className="text-violet-400 flex-shrink-0" />}
            </p>
            {r.entry.classroom_name && <p className="text-[11px] text-secondary">{r.entry.classroom_name}</p>}
          </div>
          <div className="text-right flex-shrink-0">
            <p className={cn('font-mono font-bold text-base', r.score_percentage != null ? gradeColor(r.score_percentage) : 'text-secondary')}>
              {r.is_absent ? 'Absent' : r.score_percentage != null ? `${r.score_percentage}%` : '—'}
            </p>
            {r.delta != null && (
              <p className={cn('text-[11px] font-mono flex items-center justify-end gap-0.5', r.delta >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
                <TrendingUp size={10} /> {r.delta >= 0 ? '+' : ''}{r.delta}
              </p>
            )}
          </div>
        </motion.div>
      ))}
    </div>
  );
}

// ── Challenge card ───────────────────────────────────────────────────────────
function ChallengeCard({ challenge }: { challenge: Challenge }) {
  return (
    <div className="card p-3.5 flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-display font-semibold text-secondary uppercase tracking-widest flex items-center gap-1.5">
          <Swords size={12} /> {challenge.label || 'Unlabeled Duel'}
        </p>
        <span className={cn('badge', challenge.status === 'resolved' ? 'badge-green' : challenge.status === 'void' ? 'badge-rose' : 'badge-amber')}>
          {challenge.status === 'resolved' ? 'Resolved' : challenge.status === 'void' ? 'Void' : 'Pending'}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {challenge.entries.map((e, i) => (
          <div key={e.id} className="flex items-center gap-2">
            <div className={cn('px-2.5 py-1 rounded-lg text-xs font-display font-semibold flex items-center gap-1',
              challenge.winner?.id === e.id ? 'bg-emerald-500/15 text-emerald-400' : 'bg-surface-700 text-primary/80')}>
              {challenge.winner?.id === e.id && <Trophy size={11} />}
              {e.display_name}
              {e.live_score != null && <span className="font-mono opacity-70">({e.live_score}%)</span>}
            </div>
            {i < challenge.entries.length - 1 && <span className="text-secondary text-xs font-bold">VS</span>}
          </div>
        ))}
      </div>
      {challenge.is_tie && <p className="text-xs text-amber-400 flex items-center gap-1"><AlertTriangle size={11} /> Tied result</p>}
    </div>
  );
}

// ── Tournament Detail Panel ─────────────────────────────────────────────────
function TournamentDetailPanel({ tournamentId, onClose }: { tournamentId: number; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const isStaff = user?.role === 'teacher' || user?.role === 'super_admin';
  const isStudent = user?.role === 'student';
  const [tab, setTab] = useState<'roster' | 'challenges' | 'leaderboard'>('roster');
  const [registerOpen, setRegisterOpen] = useState(false);
  const [challengeOpen, setChallengeOpen] = useState(false);

  const { data: tournament, isLoading } = useQuery<TournamentDetail>({
    queryKey: ['tournament', tournamentId],
    queryFn: () => tournamentsApi.get(tournamentId).then(r => r.data),
    refetchInterval: 15_000,
  });

  const lifecycleMutation = useMutation({
    mutationFn: (action: 'open' | 'close' | 'finalize' | 'cancel') => {
      if (action === 'open') return tournamentsApi.openRegistration(tournamentId);
      if (action === 'close') return tournamentsApi.closeRegistration(tournamentId);
      if (action === 'cancel') return tournamentsApi.cancel(tournamentId);
      return tournamentsApi.finalize(tournamentId);
    },
    onSuccess: (_, action) => {
      const messages: Record<string, string> = {
        open: 'Registration is open — combatants may now sign up',
        close: 'Registration closed',
        finalize: 'Tournament finalized — leaderboard and badges are live',
        cancel: 'Tournament cancelled',
      };
      toast.success(messages[action]);
      queryClient.invalidateQueries({ queryKey: ['tournament', tournamentId] });
      queryClient.invalidateQueries({ queryKey: ['tournaments'] });
      if (action === 'finalize') setTab('leaderboard');
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Action failed'),
  });

  const withdrawMutation = useMutation({
    mutationFn: (entryId: number) => tournamentsApi.withdraw(tournamentId, entryId),
    onSuccess: () => {
      toast.success('Withdrawn');
      queryClient.invalidateQueries({ queryKey: ['tournament', tournamentId] });
    },
  });

  if (isLoading || !tournament) return <div className="card p-6"><LoadingPage /></div>;

  const myEntry = isStudent ? tournament.entries.find(e => e.student_id === user?.student_profile_id) : null;
  const canRegisterSelf = isStudent && tournament.is_public && tournament.status === 'registration_open'
    && tournament.mode === 'individual' && !myEntry;

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="card p-0 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="p-4 md:p-5 border-b flex flex-col gap-3" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, rgba(37,99,235,0.08), transparent)' }}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {tournament.codename && (
              <p className="text-[10px] font-mono font-bold text-azure-400 uppercase tracking-[0.2em] mb-1">// {tournament.codename}</p>
            )}
            <h2 className="font-display font-bold text-lg text-primary leading-tight">{tournament.title}</h2>
            <div className="flex items-center flex-wrap gap-2 mt-2">
              <StatusPill status={tournament.status} />
              <span className="badge badge-blue">{tournament.mode === 'individual' ? <><Swords size={10} /> Student vs Student</> : <><Users2 size={10} /> Stream vs Stream</>}</span>
              <span className="text-xs text-secondary flex items-center gap-1"><School size={11} /> {tournament.classroom_name}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-secondary hover:text-primary p-1.5 rounded-lg hover:bg-surface-700 flex-shrink-0"><X size={18} /></button>
        </div>

        {tournament.description && <p className="text-sm text-secondary">{tournament.description}</p>}

        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-secondary mb-1">
              {tournament.status === 'completed' ? 'Concluded' : tournament.status === 'registration_open' ? 'Registration closes in' : 'Countdown to exam'}
            </p>
            {tournament.status !== 'completed' && tournament.status !== 'cancelled' ? (
              <Countdown targetIso={tournament.status === 'registration_open' ? tournament.registration_deadline : tournament.exam_date}
                expiredLabel={tournament.status === 'registration_open' ? 'Registration deadline passed' : 'Exam day has arrived'} />
            ) : (
              <p className="font-display font-semibold text-sm text-primary">{tournament.exam_title} — {tournament.exam_date}</p>
            )}
          </div>
          {isStaff && (
            <div className="flex flex-wrap gap-2">
              {tournament.status === 'draft' && <Button size="sm" onClick={() => lifecycleMutation.mutate('open')} loading={lifecycleMutation.isPending}><Radio size={13} /> Open Registration</Button>}
              {tournament.status === 'registration_open' && <Button size="sm" variant="secondary" onClick={() => lifecycleMutation.mutate('close')} loading={lifecycleMutation.isPending}><Ban size={13} /> Close Registration</Button>}
              {(tournament.status === 'registration_closed' || tournament.status === 'live') && tournament.exam_is_published && (
                <Button size="sm" onClick={() => lifecycleMutation.mutate('finalize')} loading={lifecycleMutation.isPending}><Trophy size={13} /> Finalize &amp; Crown Winners</Button>
              )}
              {tournament.status === 'completed' && (
                <Button size="sm" variant="secondary" onClick={() => lifecycleMutation.mutate('finalize')} loading={lifecycleMutation.isPending}><Target size={13} /> Re-finalize</Button>
              )}
              {tournament.status !== 'completed' && tournament.status !== 'cancelled' && (
                <Button size="sm" variant="danger" onClick={() => lifecycleMutation.mutate('cancel')} loading={lifecycleMutation.isPending}><Skull size={13} /> Cancel</Button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b" style={{ borderColor: 'var(--border)' }}>
        {([
          ['roster', `Roster (${tournament.entries.length})`, Users2],
          ['challenges', `Challenges (${tournament.challenges.length})`, Swords],
          ['leaderboard', 'Leaderboard', Trophy],
        ] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)}
            className={cn('flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-display font-semibold transition-colors border-b-2',
              tab === key ? 'text-azure-400 border-azure-500' : 'text-secondary border-transparent hover:text-primary')}>
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="p-4 md:p-5 flex flex-col gap-3 max-h-[520px] overflow-y-auto">
        {tab === 'roster' && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-xs text-secondary">{tournament.entries.length} registered {tournament.max_entrants ? `/ ${tournament.max_entrants} max` : ''}</p>
              {(isStaff && tournament.status === 'registration_open') && (
                <Button size="sm" variant="secondary" onClick={() => setRegisterOpen(true)}><Plus size={13} /> Add Entrant</Button>
              )}
              {canRegisterSelf && (
                <Button size="sm" onClick={() => setRegisterOpen(true)}><Plus size={13} /> Register Me</Button>
              )}
            </div>
            {tournament.entries.length === 0 ? (
              <EmptyState icon={<Users2 size={28} />} title="No one's registered yet" message="Once registration opens, entrants will appear here." />
            ) : (
              <div className="grid sm:grid-cols-2 gap-2">
                {tournament.entries.map(e => (
                  <div key={e.id} className="card p-3 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-display font-semibold text-sm text-primary truncate">{e.display_name}</p>
                      <p className="text-[11px] text-secondary">{e.seed_average != null ? `Seed avg ${e.seed_average}%` : 'No prior average'}</p>
                    </div>
                    {(isStaff || (isStudent && e.student_id === user?.student_profile_id)) && tournament.status === 'registration_open' && (
                      <button onClick={() => withdrawMutation.mutate(e.id)} className="text-secondary hover:text-rose-400 p-1 flex-shrink-0"><X size={14} /></button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === 'challenges' && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-xs text-secondary">Declared head-to-head duels</p>
              {tournament.entries.length >= 2 && tournament.status !== 'completed' && tournament.status !== 'cancelled' && (
                <Button size="sm" variant="secondary" onClick={() => setChallengeOpen(true)}><Swords size={13} /> Declare Challenge</Button>
              )}
            </div>
            {tournament.challenges.length === 0 ? (
              <EmptyState icon={<Swords size={28} />} title="No challenges declared" message="Students can register to challenge each other here." />
            ) : (
              <div className="flex flex-col gap-2">
                {tournament.challenges.map(c => <ChallengeCard key={c.id} challenge={c} />)}
              </div>
            )}
          </>
        )}

        {tab === 'leaderboard' && <LeaderboardTable rows={tournament.leaderboard} />}
      </div>

      {registerOpen && <RegisterEntryModal open={registerOpen} onClose={() => setRegisterOpen(false)} tournament={tournament} />}
      {challengeOpen && <CreateChallengeModal open={challengeOpen} onClose={() => setChallengeOpen(false)} tournament={tournament} />}
    </motion.div>
  );
}

// ── Intel / Hall of Fame ─────────────────────────────────────────────────────
function IntelPanel({ classroomId }: { classroomId: number | null }) {
  const { data, isLoading } = useQuery<TournamentIntel>({
    queryKey: ['tournament-intel', classroomId],
    queryFn: () => tournamentsApi.intel(classroomId ? { classroom_id: classroomId } : {}).then(r => r.data),
  });

  if (isLoading) return <LoadingPage />;
  if (!data) return null;

  return (
    <div className="flex flex-col gap-5">
      <div className="card p-4 md:p-5 relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.04] pointer-events-none"
          style={{ backgroundImage: 'repeating-linear-gradient(45deg, currentColor 0, currentColor 1px, transparent 1px, transparent 14px)' }} />
        <div className="relative flex items-center gap-2 mb-1">
          <Eye size={16} className="text-azure-400" />
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.25em] text-azure-400">Classified — Tournament Intelligence</p>
        </div>
        <h2 className="font-display font-bold text-xl text-primary">Hall of Fame</h2>
        <p className="text-sm text-secondary mt-1">Aggregated across every finalized operation{classroomId ? ' in this classroom' : ' platform-wide'}.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <StatCard label="Operations Completed" value={data.tournaments_completed} color="blue" icon={<Flag size={16} />} />
        <StatCard label="Total Entrants" value={data.total_entrants} color="violet" icon={<Users2 size={16} />} />
        <StatCard label="Challenges Fought" value={data.total_challenges_fought} color="rose" icon={<Swords size={16} />} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card p-4">
          <p className="text-xs font-display font-bold uppercase tracking-widest text-secondary mb-3 flex items-center gap-1.5"><Crown size={13} className="text-amber-400" /> Most Decorated</p>
          {data.most_decorated.length === 0 ? <p className="text-sm text-secondary">No champions crowned yet.</p> : (
            <div className="flex flex-col gap-1.5">
              {data.most_decorated.map((r, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="text-primary font-medium">{i + 1}. {r.name}</span>
                  <span className="font-mono text-amber-400 font-bold">{r.count}x</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-4">
          <p className="text-xs font-display font-bold uppercase tracking-widest text-secondary mb-3 flex items-center gap-1.5"><Swords size={13} className="text-rose-400" /> Most Duel Wins</p>
          {data.most_duel_wins.length === 0 ? <p className="text-sm text-secondary">No duels resolved yet.</p> : (
            <div className="flex flex-col gap-1.5">
              {data.most_duel_wins.map((r, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="text-primary font-medium">{i + 1}. {r.name}</span>
                  <span className="font-mono text-rose-400 font-bold">{r.wins}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-4">
          <p className="text-xs font-display font-bold uppercase tracking-widest text-secondary mb-3 flex items-center gap-1.5"><Sparkles size={13} className="text-violet-400" /> Rising Stars</p>
          {data.rising_stars.length === 0 ? <p className="text-sm text-secondary">No breakout performances yet.</p> : (
            <div className="flex flex-col gap-1.5">
              {data.rising_stars.map((r, i) => (
                <div key={i} className="flex items-center justify-between text-sm gap-2">
                  <span className="text-primary font-medium truncate">{r.name} <span className="text-secondary font-normal">— {r.tournament}</span></span>
                  <span className="font-mono text-emerald-400 font-bold flex-shrink-0">+{r.delta}%</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-4">
          <p className="text-xs font-display font-bold uppercase tracking-widest text-secondary mb-3 flex items-center gap-1.5"><Users2 size={13} className="text-azure-400" /> Stream Standings</p>
          {data.stream_leaderboard.length === 0 ? <p className="text-sm text-secondary">No stream-vs-stream data yet.</p> : (
            <div className="flex flex-col gap-1.5">
              {data.stream_leaderboard.map((r, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="text-primary font-medium">{i + 1}. {r.name}</span>
                  <span className="text-xs text-secondary font-mono">{r.titles} titles · avg {r.average_score != null ? `${r.average_score}%` : '—'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Tournament Badge Showcase (student view) ────────────────────────────────
const TOURNAMENT_BADGE_CODES = [
  'tournament_recruit', 'tournament_veteran', 'tournament_duelist', 'tournament_gladiator',
  'tournament_warlord', 'tournament_champion', 'tournament_dynasty', 'tournament_undefeated',
  'tournament_giant_slayer', 'tournament_rising_star', 'tournament_flawless_duel', 'tournament_underdog',
];

function BadgeShowcase({ progress }: { progress: StudentProgress | undefined }) {
  const { data: allBadgesData } = useQuery<Badge[] | PaginatedResponse<Badge>>({
    queryKey: ['all-badges'],
    queryFn: () => gamificationApi.badges().then(r => r.data),
  });
  const allBadges = listFrom(allBadgesData).filter(b => TOURNAMENT_BADGE_CODES.includes(b.code));
  const earnedCodes = new Set((progress?.badges ?? []).map(b => b.badge.code));

  if (allBadges.length === 0) return null;

  return (
    <div className="card p-4 md:p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="font-display font-bold text-primary flex items-center gap-1.5"><Award size={16} className="text-amber-400" /> Tournament Badges</p>
        <span className="text-xs text-secondary font-mono">{allBadges.filter(b => earnedCodes.has(b.code)).length}/{allBadges.length} earned</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
        {allBadges.map(b => {
          const earned = earnedCodes.has(b.code);
          return (
            <div key={b.code} className={cn('flex flex-col items-center text-center gap-1.5 p-3 rounded-2xl border transition-all',
              earned ? 'border-amber-500/40 bg-amber-500/5' : 'border-surface opacity-45 grayscale')}>
              <div className={cn('w-9 h-9 rounded-full flex items-center justify-center', earned ? 'bg-amber-500/15 text-amber-400' : 'bg-surface-700 text-secondary')}>
                <BadgeGlyph name={b.icon} className="w-4.5 h-4.5" />
              </div>
              <p className="text-[11px] font-display font-semibold text-primary leading-tight">{b.name}</p>
              <p className="text-[9px] text-secondary leading-tight">{b.description}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Operation Card (list item) ───────────────────────────────────────────────
function OperationCard({ tournament, onOpen }: { tournament: Tournament; onOpen: () => void }) {
  const countdownTarget = tournament.status === 'registration_open' ? tournament.registration_deadline : tournament.exam_date;
  return (
    <motion.button
      layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} whileHover={{ y: -2 }}
      onClick={onOpen}
      className="card p-4 text-left flex flex-col gap-3 relative overflow-hidden group"
    >
      <div className={cn('absolute top-0 left-0 w-1 h-full', tournament.mode === 'individual' ? 'bg-azure-500' : 'bg-violet-500')} />
      <div className="flex items-start justify-between gap-2 pl-1.5">
        <div className="min-w-0">
          {tournament.codename && <p className="text-[9px] font-mono font-bold text-azure-400/80 uppercase tracking-widest">// {tournament.codename}</p>}
          <p className="font-display font-bold text-sm text-primary truncate group-hover:text-azure-400 transition-colors">{tournament.title}</p>
        </div>
        <ChevronRight size={16} className="text-secondary flex-shrink-0 mt-0.5" />
      </div>
      <div className="flex items-center flex-wrap gap-1.5 pl-1.5">
        <StatusPill status={tournament.status} />
        <span className="badge badge-blue text-[10px]">{tournament.mode === 'individual' ? <Swords size={9} /> : <Users2 size={9} />} {tournament.classroom_name}</span>
      </div>
      <div className="flex items-center justify-between pl-1.5">
        <div className="flex items-center gap-3 text-[11px] text-secondary">
          <span className="flex items-center gap-1"><Users2 size={11} /> {tournament.entry_count}</span>
          <span className="flex items-center gap-1"><Swords size={11} /> {tournament.challenge_count}</span>
        </div>
        {tournament.status !== 'completed' && tournament.status !== 'cancelled' && countdownTarget && (
          <MiniCountdown targetIso={countdownTarget} />
        )}
      </div>
    </motion.button>
  );
}

function MiniCountdown({ targetIso }: { targetIso: string }) {
  const cd = useCountdown(targetIso);
  if (!cd) return null;
  if (cd.expired) return <span className="text-[11px] text-rose-400 font-mono flex items-center gap-1"><Clock size={10} /> Due</span>;
  return (
    <span className="text-[11px] font-mono font-bold text-primary flex items-center gap-1">
      <Clock size={10} className="text-secondary" />
      {cd.days > 0 ? `${cd.days}d ${cd.hours}h` : `${cd.hours}h ${cd.minutes}m`}
    </span>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────
export default function TournamentPage() {
  const { user } = useAuthStore();
  const isStaff = user?.role === 'teacher' || user?.role === 'super_admin';
  const isStudent = user?.role === 'student';

  const [view, setView] = useState<'operations' | 'intel' | 'my-record'>('operations');
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [classroomFilter, setClassroomFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [modeFilter, setModeFilter] = useState('');

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms-for-tournaments'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
    enabled: isStaff,
  });
  const classrooms = listFrom(classroomsData);

  const { data: tournamentsData, isLoading } = useQuery<PaginatedResponse<Tournament> | Tournament[]>({
    queryKey: ['tournaments', classroomFilter, statusFilter, modeFilter],
    queryFn: () => tournamentsApi.list({
      classroom: classroomFilter || undefined,
      status: statusFilter || undefined,
      mode: modeFilter || undefined,
      page_size: 100,
    }).then(r => r.data),
  });
  const tournaments = listFrom(tournamentsData);

  const { data: myProgress } = useQuery<StudentProgress>({
    queryKey: ['my-progress-tournaments'],
    queryFn: () => gamificationApi.myProgress().then(r => r.data),
    enabled: isStudent,
  });

  const { data: myEntries } = useQuery<MyTournamentEntryRow[]>({
    queryKey: ['my-tournament-entries'],
    queryFn: () => tournamentsApi.myEntries().then(r => r.data),
    enabled: isStudent && view === 'my-record',
  });

  const active = tournaments.filter(t => ['draft', 'registration_open', 'registration_closed', 'live'].includes(t.status));
  const finished = tournaments.filter(t => ['completed', 'cancelled'].includes(t.status));

  return (
    <div className="flex flex-col gap-5 pb-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-mono font-bold text-azure-400 uppercase tracking-[0.25em] mb-1 flex items-center gap-1.5">
            <ScanLine size={12} /> Competitive Operations
          </p>
          <h1 className="page-title flex items-center gap-2"><Trophy className="text-amber-400" size={26} /> Tournaments</h1>
          <p className="text-secondary text-sm mt-1">Exam-linked duels, stream wars, and the hall of fame — all in one command center.</p>
        </div>
        {isStaff && (
          <Button onClick={() => setCreateOpen(true)}><Plus size={15} /> New Operation</Button>
        )}
      </div>

      {/* View tabs */}
      <div className="flex items-center gap-1.5 border-b overflow-x-auto" style={{ borderColor: 'var(--border)' }}>
        {([
          ['operations', 'Operations', ListChecks],
          ['intel', 'Intelligence', Eye],
          ...(isStudent ? [['my-record', 'My Record', Target] as const] : []),
        ] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setView(key)}
            className={cn('flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-display font-semibold border-b-2 transition-colors whitespace-nowrap',
              view === key ? 'text-azure-400 border-azure-500' : 'text-secondary border-transparent hover:text-primary')}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {view === 'operations' && (
        <div className="grid lg:grid-cols-[1fr] gap-5">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            {isStaff && (
              <Select value={classroomFilter} onChange={e => setClassroomFilter(e.target.value)} className="w-auto min-w-[160px]"
                options={[{ value: '', label: 'All classrooms' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]} />
            )}
            <Select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="w-auto min-w-[160px]"
              options={[{ value: '', label: 'All statuses' }, ...Object.entries(STATUS_META).map(([v, m]) => ({ value: v, label: m.label }))]} />
            <Select value={modeFilter} onChange={e => setModeFilter(e.target.value)} className="w-auto min-w-[160px]"
              options={[{ value: '', label: 'All modes' }, { value: 'individual', label: 'Student vs Student' }, { value: 'stream', label: 'Stream vs Stream' }]} />
          </div>

          {isLoading ? <LoadingPage /> : tournaments.length === 0 ? (
            <EmptyState icon={<Trophy size={32} />} title="No tournaments yet"
              message={isStaff ? 'Launch an operation to get students registering and challenging each other.' : 'Check back once your teacher launches a tournament.'} />
          ) : (
            <div className="flex flex-col gap-6">
              {active.length > 0 && (
                <div>
                  <p className="text-xs font-display font-bold uppercase tracking-widest text-secondary mb-2.5">Active Operations</p>
                  <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
                    {active.map(t => <OperationCard key={t.id} tournament={t} onOpen={() => setSelectedId(t.id)} />)}
                  </div>
                </div>
              )}
              {finished.length > 0 && (
                <div>
                  <p className="text-xs font-display font-bold uppercase tracking-widest text-secondary mb-2.5">Archived</p>
                  <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
                    {finished.map(t => <OperationCard key={t.id} tournament={t} onOpen={() => setSelectedId(t.id)} />)}
                  </div>
                </div>
              )}
            </div>
          )}

          <AnimatePresence>
            {selectedId != null && (
              <TournamentDetailPanel tournamentId={selectedId} onClose={() => setSelectedId(null)} />
            )}
          </AnimatePresence>
        </div>
      )}

      {view === 'intel' && (
        <div className="flex flex-col gap-5">
          {isStaff && (
            <Select value={classroomFilter} onChange={e => setClassroomFilter(e.target.value)} className="w-auto min-w-[200px] self-start"
              options={[{ value: '', label: 'All classrooms' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]} />
          )}
          <IntelPanel classroomId={classroomFilter ? Number(classroomFilter) : null} />
          {isStudent && <BadgeShowcase progress={myProgress} />}
        </div>
      )}

      {view === 'my-record' && isStudent && (
        <div className="flex flex-col gap-5">
          <BadgeShowcase progress={myProgress} />
          <div>
            <p className="text-xs font-display font-bold uppercase tracking-widest text-secondary mb-2.5">My Tournament History</p>
            {!myEntries || myEntries.length === 0 ? (
              <EmptyState icon={<Target size={28} />} title="No tournaments entered yet" message="Register for an open tournament to start building your record." />
            ) : (
              <div className="flex flex-col gap-2">
                {myEntries.map(row => (
                  <div key={row.entry_id} className="card p-4 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-display font-semibold text-sm text-primary truncate">{row.tournament.title}</p>
                      <p className="text-xs text-secondary">{row.tournament.classroom_name} · {row.tournament.exam_title}</p>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <StatusPill status={row.tournament.status} />
                      {row.result ? (
                        <div className="text-right">
                          <RankBadge rank={row.result.rank} />
                          <p className="text-xs font-mono text-secondary">{row.result.score_percentage != null ? `${row.result.score_percentage}%` : 'Absent'}</p>
                        </div>
                      ) : row.live_score != null ? (
                        <p className="font-mono text-sm text-primary">{row.live_score}%</p>
                      ) : (
                        <p className="text-xs text-secondary">Pending</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {isStaff && <CreateTournamentModal open={createOpen} onClose={() => setCreateOpen(false)} classrooms={classrooms} />}
    </div>
  );
}
