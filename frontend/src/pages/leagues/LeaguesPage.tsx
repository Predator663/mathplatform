import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  Swords, Shield, Trophy, Crown, Plus, X, ChevronRight, ChevronLeft, ArrowUp, Check,
  Ban, Users2, Target, Sparkles, Award, Settings2, PlayCircle, Archive, RotateCcw, Gem, AlertTriangle,
  TrendingUp, TrendingDown, Minus, Download,
} from 'lucide-react';
import { leaguesApi, studentsApi, examsApi } from '../../api';
import {
  LoadingPage, EmptyState, Button, Input, Select, Modal, StatCard,
} from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import { cn, apiErrorMessage, downloadBlob } from '../../utils';
import type {
  LeagueSeason, LeagueSeasonDetail, LeagueGroup, PromotionEvent, Classroom, Exam,
  PaginatedResponse, LeagueIntervalMode, LeaguePromotionMode, LeagueAnalytics, LeagueBandStat,
} from '../../types';
import { Link } from 'react-router-dom';

function listFrom<T>(data: PaginatedResponse<T> | T[] | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results ?? [];
}

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  draft:    { label: 'Draft',    color: 'text-secondary',   bg: 'bg-surface-700' },
  active:   { label: 'Active',   color: 'text-emerald-400', bg: 'bg-emerald-500/15' },
  archived: { label: 'Archived', color: 'text-secondary',   bg: 'bg-surface-700' },
};

function StatusPill({ status }: { status: string }) {
  const m = STATUS_META[status] ?? STATUS_META.draft;
  return (
    <span className={cn('inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-display font-bold uppercase tracking-widest', m.color, m.bg)}>
      {m.label}
    </span>
  );
}

// ── Create Season Modal ─────────────────────────────────────────────────────
function CreateSeasonModal({ open, onClose, classrooms }: { open: boolean; onClose: () => void; classrooms: Classroom[] }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState('');
  const [classroomId, setClassroomId] = useState('');
  const [examId, setExamId] = useState('');
  const [intervalMode, setIntervalMode] = useState<LeagueIntervalMode>('auto');
  const [bandWidth, setBandWidth] = useState('10');
  const [promotionMode, setPromotionMode] = useState<LeaguePromotionMode>('manual');
  const [manualBands, setManualBands] = useState([
    { name: 'Foundation', min_mark: 0, max_mark: 49 },
    { name: 'Elite Circle', min_mark: 50, max_mark: 100 },
  ]);

  const { data: examsData } = useQuery<PaginatedResponse<Exam> | Exam[]>({
    queryKey: ['exams-for-league', classroomId],
    queryFn: () => examsApi.exams({ classrooms: classroomId, page_size: 100 }).then(r => r.data),
    enabled: !!classroomId,
  });
  const exams = listFrom(examsData);

  const reset = () => {
    setTitle(''); setClassroomId(''); setExamId(''); setIntervalMode('auto');
    setBandWidth('10'); setPromotionMode('manual');
    setManualBands([{ name: 'Foundation', min_mark: 0, max_mark: 49 }, { name: 'Elite Circle', min_mark: 50, max_mark: 100 }]);
  };

  const createMutation = useMutation({
    mutationFn: () => leaguesApi.createSeason({
      title, classroom_id: Number(classroomId), baseline_exam_id: Number(examId),
      interval_mode: intervalMode, band_width: Number(bandWidth), promotion_mode: promotionMode,
      manual_bands: intervalMode === 'manual' ? manualBands : undefined,
    }),
    onSuccess: (res) => {
      const unplaced = res.data.unplaced ?? [];
      toast.success(unplaced.length
        ? `League created — ${unplaced.length} student(s) need manual placement.`
        : 'League created and every student placed.');
      queryClient.invalidateQueries({ queryKey: ['league-seasons'] });
      reset(); onClose();
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || err?.response?.data?.[0] || 'Could not create league.'),
  });

  return (
    <Modal open={open} onClose={() => { reset(); onClose(); }} title="Create League Season" size="lg">
      <div className="flex flex-col gap-4">
        <Input label="Season title" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Term 2 Skill League" />
        <Select
          label="Classroom" value={classroomId} onChange={e => { setClassroomId(e.target.value); setExamId(''); }}
          options={[{ value: '', label: 'Select classroom…' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]}
        />
        <Select
          label="Baseline exam (first individual exam used to place students)"
          value={examId} onChange={e => setExamId(e.target.value)} disabled={!classroomId}
          options={[{ value: '', label: classroomId ? 'Select exam…' : 'Pick a classroom first' }, ...exams.map(e => ({ value: e.id, label: e.title }))]}
        />

        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Band intervals" value={intervalMode} onChange={e => setIntervalMode(e.target.value as LeagueIntervalMode)}
            options={[{ value: 'auto', label: 'Automatic (evenly spaced)' }, { value: 'manual', label: 'Manual (custom)' }]}
          />
          <Select
            label="Promotion" value={promotionMode} onChange={e => setPromotionMode(e.target.value as LeaguePromotionMode)}
            options={[{ value: 'manual', label: 'Stage for approval' }, { value: 'auto', label: 'Auto-apply' }]}
          />
        </div>

        {intervalMode === 'auto' ? (
          <Input
            label="Band width (percentage points)" type="number" min={1} max={50}
            value={bandWidth} onChange={e => setBandWidth(e.target.value)}
          />
        ) : (
          <div className="flex flex-col gap-2">
            <label className="label">Custom bands</label>
            {manualBands.map((b, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  className="input flex-1" placeholder="Band name" value={b.name}
                  onChange={e => setManualBands(bs => bs.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
                />
                <input
                  className="input w-20" type="number" placeholder="Min" value={b.min_mark}
                  onChange={e => setManualBands(bs => bs.map((x, j) => j === i ? { ...x, min_mark: Number(e.target.value) } : x))}
                />
                <span className="text-muted">–</span>
                <input
                  className="input w-20" type="number" placeholder="Max" value={b.max_mark}
                  onChange={e => setManualBands(bs => bs.map((x, j) => j === i ? { ...x, max_mark: Number(e.target.value) } : x))}
                />
                <button
                  onClick={() => setManualBands(bs => bs.filter((_, j) => j !== i))}
                  className="text-secondary hover:text-rose-400 p-1"
                >
                  <X size={16} />
                </button>
              </div>
            ))}
            <Button variant="secondary" size="sm" onClick={() => setManualBands(bs => [...bs, { name: '', min_mark: 0, max_mark: 0 }])}>
              <Plus size={14} /> Add band
            </Button>
          </div>
        )}
      </div>
      <div className="flex justify-end gap-3 pt-5">
        <Button variant="ghost" onClick={() => { reset(); onClose(); }}>Cancel</Button>
        <Button
          onClick={() => createMutation.mutate()}
          loading={createMutation.isPending}
          disabled={!title || !classroomId || !examId}
        >
          Create League
        </Button>
      </div>
    </Modal>
  );
}

// ── Evaluate Promotions Modal ───────────────────────────────────────────────
function EvaluatePromotionsModal({ open, onClose, season }: { open: boolean; onClose: () => void; season: LeagueSeason }) {
  const queryClient = useQueryClient();
  const [examId, setExamId] = useState('');
  const { data: examsData } = useQuery<PaginatedResponse<Exam> | Exam[]>({
    queryKey: ['exams-for-league-eval', season.classroom],
    queryFn: () => examsApi.exams({ classrooms: season.classroom, page_size: 100 }).then(r => r.data),
    enabled: open,
  });
  const exams = listFrom(examsData);

  const evalMutation = useMutation({
    mutationFn: () => leaguesApi.evaluatePromotions(season.id, Number(examId)),
    onSuccess: (res) => {
      const { staged, auto_applied, evaluated } = res.data;
      toast.success(`Evaluated ${evaluated} student(s) — ${auto_applied} promoted, ${staged} staged for approval.`);
      queryClient.invalidateQueries({ queryKey: ['league-season', season.id] });
      queryClient.invalidateQueries({ queryKey: ['league-seasons'] });
      onClose();
    },
    onError: () => toast.error('Could not evaluate promotions.'),
  });

  return (
    <Modal open={open} onClose={onClose} title={`Evaluate Promotions — ${season.title}`}>
      <p className="text-secondary text-sm mb-4">
        Pick the exam that just happened. Every student whose score beats her current band's ceiling
        will be {season.promotion_mode === 'auto' ? 'promoted immediately' : 'staged for your approval'}.
      </p>
      <Select
        label="Trigger exam" value={examId} onChange={e => setExamId(e.target.value)}
        options={[{ value: '', label: 'Select exam…' }, ...exams.map(e => ({ value: e.id, label: e.title }))]}
      />
      <div className="flex justify-end gap-3 pt-5">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={() => evalMutation.mutate()} loading={evalMutation.isPending} disabled={!examId}>
          <PlayCircle size={16} /> Run Evaluation
        </Button>
      </div>
    </Modal>
  );
}

// ── Band tier card ───────────────────────────────────────────────────────────
function TrendGlyph({ trend }: { trend: 'improving' | 'declining' | 'stable' | null }) {
  if (trend === 'improving') return <TrendingUp size={12} className="text-emerald-400 shrink-0" />;
  if (trend === 'declining') return <TrendingDown size={12} className="text-rose-400 shrink-0" />;
  if (trend === 'stable') return <Minus size={12} className="text-secondary shrink-0" />;
  return null;
}

function BandCard({ group, detail, bandStat }: { group: LeagueGroup; detail?: LeagueSeasonDetail; bandStat?: LeagueBandStat }) {
  const members = (detail?.memberships ?? []).filter(m => m.group === group.id);
  const trendByStudent = new Map((bandStat?.members ?? []).map(m => [m.student_id, m]));
  const climberIds = new Set((bandStat?.climbers ?? []).map(c => c.student_id));

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className="card p-4 flex flex-col gap-3"
      style={{ borderColor: `${group.color}55` }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: group.color }} />
          <span className="font-display font-bold text-primary">{group.name}%</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-secondary">
          {bandStat && bandStat.rising_count > 0 && (
            <span className="flex items-center gap-0.5 text-emerald-400"><TrendingUp size={11} /> {bandStat.rising_count}</span>
          )}
          {bandStat && bandStat.declining_count > 0 && (
            <span className="flex items-center gap-0.5 text-rose-400"><TrendingDown size={11} /> {bandStat.declining_count}</span>
          )}
          <span className="flex items-center gap-1"><Users2 size={12} /> {members.length}</span>
        </div>
      </div>
      <div className="flex flex-col gap-1.5 max-h-64 overflow-y-auto">
        {members.length === 0 && <p className="text-xs text-muted italic">No students yet.</p>}
        {members.map(m => {
          const t = trendByStudent.get(m.student);
          const isClimber = climberIds.has(m.student);
          return (
            <div
              key={m.id}
              className={cn(
                'flex items-center justify-between text-sm px-2 py-1.5 rounded-lg',
                isClimber ? 'bg-emerald-500/10 ring-1 ring-emerald-500/30' : 'bg-surface-700/40',
              )}
            >
              <span className="text-primary/90 truncate flex items-center gap-1.5">
                {m.is_top_tier && <Crown size={12} className="text-amber-400 shrink-0" />}
                <TrendGlyph trend={t?.trend ?? null} />
                {m.student_name}
                {isClimber && <span className="text-[9px] text-emerald-400 font-display font-bold uppercase tracking-wide shrink-0">Climbing</span>}
              </span>
              <div className="flex items-center gap-1.5 shrink-0">
                {m.is_promotion_pending && (
                  <span className="badge bg-violet-500/15 text-violet-400 text-[10px] flex items-center gap-1">
                    <ArrowUp size={10} /> Staged {m.pending_target_group_name ? `→ ${m.pending_target_group_name}%` : ''}
                  </span>
                )}
                {!m.is_promotion_pending && t?.distance_to_promotion != null && (
                  <span className="text-[10px] text-muted">{t.distance_to_promotion}% to next</span>
                )}
                <span className="font-mono text-xs text-secondary">{m.latest_score ?? m.placement_score}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

// ── Pending promotion row ────────────────────────────────────────────────────
function PendingPromotionsPanel({ season }: { season: LeagueSeasonDetail }) {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ['league-promotions', season.id],
    queryFn: () => leaguesApi.promotions({ season: season.id, status: 'pending' }).then(r => listFrom<PromotionEvent>(r.data)),
  });
  const events = data ?? [];

  const approve = useMutation({
    mutationFn: (id: number) => leaguesApi.approvePromotion(id),
    onSuccess: () => {
      toast.success('Promotion approved.');
      queryClient.invalidateQueries({ queryKey: ['league-promotions', season.id] });
      queryClient.invalidateQueries({ queryKey: ['league-season', season.id] });
      queryClient.invalidateQueries({ queryKey: ['league-seasons'] });
    },
  });
  const reject = useMutation({
    mutationFn: (id: number) => leaguesApi.rejectPromotion(id),
    onSuccess: () => {
      toast('Promotion rejected.');
      queryClient.invalidateQueries({ queryKey: ['league-promotions', season.id] });
      queryClient.invalidateQueries({ queryKey: ['league-season', season.id] });
      queryClient.invalidateQueries({ queryKey: ['league-seasons'] });
    },
  });

  if (events.length === 0) return null;

  return (
    <div className="card p-4 border-violet-500/30 bg-violet-500/5">
      <h4 className="font-display font-semibold text-sm text-primary flex items-center gap-2 mb-3">
        <Sparkles size={14} className="text-violet-400" /> Staged for Promotion ({events.length})
      </h4>
      <div className="flex flex-col gap-2">
        {events.map(ev => (
          <div key={ev.id} className="flex items-center justify-between text-sm bg-surface-800/60 rounded-lg px-3 py-2">
            <span className="text-primary/90">
              {ev.student_name}: <span className="text-secondary">{ev.from_group_name}%</span>
              <ChevronRight size={12} className="inline mx-1 text-violet-400" />
              <span className="font-semibold text-violet-300">{ev.to_group_name}%</span>
              <span className="text-muted ml-1.5">({ev.trigger_score}% on {ev.trigger_exam_title})</span>
            </span>
            <div className="flex items-center gap-2 shrink-0">
              <Button size="sm" variant="secondary" onClick={() => approve.mutate(ev.id)} loading={approve.isPending}>
                <Check size={12} /> Approve
              </Button>
              <Button size="sm" variant="ghost" onClick={() => reject.mutate(ev.id)} loading={reject.isPending}>
                <Ban size={12} /> Reject
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Error panel (shown instead of an endless spinner when a fetch fails) ────
function ErrorPanel({ message, onRetry, onBack }: { message: string; onRetry: () => void; onBack?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center px-4">
      <AlertTriangle size={36} className="text-rose-400" />
      <p className="font-display font-semibold text-primary">Couldn't load this league</p>
      <p className="text-muted max-w-sm text-sm">{message}</p>
      <div className="flex items-center gap-2">
        {onBack && <Button variant="ghost" size="sm" onClick={onBack}><ChevronLeft size={14} /> Back</Button>}
        <Button variant="secondary" size="sm" onClick={onRetry}><RotateCcw size={14} /> Try again</Button>
      </div>
    </div>
  );
}

// ── Season Detail ────────────────────────────────────────────────────────────
function SeasonDetail({ seasonId, onBack }: { seasonId: number; onBack: () => void }) {
  const queryClient = useQueryClient();
  const [evalOpen, setEvalOpen] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);

  const { data: season, isLoading, isError, error, refetch } = useQuery<LeagueSeasonDetail>({
    queryKey: ['league-season', seasonId],
    queryFn: () => leaguesApi.season(seasonId).then(r => r.data),
    retry: 1,
  });

  const { data: analytics } = useQuery<LeagueAnalytics>({
    queryKey: ['league-season-analytics', seasonId],
    queryFn: () => leaguesApi.seasonAnalytics(seasonId).then(r => r.data),
    retry: 1,
  });
  const bandStatByGroupId = new Map<number, LeagueBandStat>((analytics?.band_stats ?? []).map(b => [b.group_id, b]));

  const archiveMutation = useMutation({
    mutationFn: () => season?.status === 'archived' ? leaguesApi.reactivateSeason(seasonId) : leaguesApi.archiveSeason(seasonId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['league-season', seasonId] });
      queryClient.invalidateQueries({ queryKey: ['league-seasons'] });
    },
  });

  const handleExportPdf = async () => {
    setExportingPdf(true);
    try {
      const res = await leaguesApi.exportSeasonRosterPdf(seasonId);
      const safe = (season?.title || 'league').replace(/\s+/g, '_').slice(0, 40);
      downloadBlob(res.data as Blob, `${safe}_roster.pdf`);
      toast.success('Export ready.');
    } catch {
      toast.error('Could not export the band listing.');
    } finally {
      setExportingPdf(false);
    }
  };

  if (isLoading) return <LoadingPage />;
  if (isError) return <ErrorPanel message={apiErrorMessage(error)} onRetry={() => refetch()} onBack={onBack} />;
  if (!season) return <ErrorPanel message="No data came back from the server." onRetry={() => refetch()} onBack={onBack} />;
  const groups = [...season.groups].sort((a, b) => a.order - b.order);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <button onClick={onBack} className="flex items-center gap-1.5 text-sm text-secondary hover:text-primary">
          <ChevronLeft size={16} /> Back to leagues
        </button>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setEvalOpen(true)}>
            <PlayCircle size={14} /> Evaluate Promotions
          </Button>
          <Button variant="secondary" size="sm" onClick={handleExportPdf} loading={exportingPdf}>
            <Download size={14} /> Export PDF
          </Button>
          <Button variant="ghost" size="sm" onClick={() => archiveMutation.mutate()} loading={archiveMutation.isPending}>
            {season.status === 'archived' ? <><RotateCcw size={14} /> Reactivate</> : <><Archive size={14} /> Archive</>}
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-xl font-display font-bold text-primary">{season.title}</h2>
        <StatusPill status={season.status} />
        <span className="text-xs text-secondary">{season.classroom_name} · Baseline: {season.baseline_exam_title}</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Bands" value={season.group_count} icon={<Shield size={16} />} />
        <StatCard label="Members" value={season.member_count} icon={<Users2 size={16} />} color="violet" />
        <StatCard label="Pending Promotions" value={season.pending_promotion_count} icon={<Sparkles size={16} />} color="amber" />
        <StatCard label="Promotion Mode" value={season.promotion_mode === 'auto' ? 'Auto' : 'Manual'} icon={<Settings2 size={16} />} color="green" />
      </div>

      <PendingPromotionsPanel season={season} />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <AnimatePresence>
          {groups.map(g => <BandCard key={g.id} group={g} detail={season} bandStat={bandStatByGroupId.get(g.id)} />)}
        </AnimatePresence>
      </div>

      <EvaluatePromotionsModal open={evalOpen} onClose={() => setEvalOpen(false)} season={season} />
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────
export default function LeaguesPage() {
  const { user } = useAuthStore();
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedSeasonId, setSelectedSeasonId] = useState<number | null>(null);

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms-for-leagues'],
    queryFn: () => studentsApi.classrooms({ page_size: 100 }).then(r => r.data),
  });
  const classrooms = listFrom(classroomsData);

  const { data: seasonsData, isLoading, isError, error, refetch } = useQuery<PaginatedResponse<LeagueSeason> | LeagueSeason[]>({
    queryKey: ['league-seasons'],
    queryFn: () => leaguesApi.seasons({ page_size: 100 }).then(r => r.data),
    retry: 1,
  });
  const seasons = listFrom(seasonsData);

  if (user?.role === 'student' || user?.role === 'parent') {
    return <EmptyState icon={<Shield size={40} />} title="Not available" message="League standings are managed by teachers and admins." />;
  }

  if (selectedSeasonId) {
    return <SeasonDetail seasonId={selectedSeasonId} onBack={() => setSelectedSeasonId(null)} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold text-primary flex items-center gap-2">
            <Shield className="text-azure-400" /> Skill Leagues
          </h1>
          <p className="text-secondary text-sm mt-1">
            Auto-group students by ability on their first exam, and let strong performers climb the tiers.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/leagues/hall-of-fame">
            <Button variant="secondary"><Trophy size={16} /> Hall of Fame</Button>
          </Link>
          <Button onClick={() => setCreateOpen(true)}><Plus size={16} /> New League</Button>
        </div>
      </div>

      {isLoading ? <LoadingPage /> : isError ? (
        <ErrorPanel message={apiErrorMessage(error)} onRetry={() => refetch()} />
      ) : seasons.length === 0 ? (
        <EmptyState
          icon={<Target size={40} />}
          title="No leagues yet"
          message="Create your first league to auto-group students into skill bands by their baseline exam score."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {seasons.map(season => (
            <motion.div
              key={season.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="card p-4 flex flex-col gap-3 cursor-pointer hover:border-azure-500/40 transition-colors"
              onClick={() => setSelectedSeasonId(season.id)}
            >
              <div className="flex items-center justify-between">
                <h3 className="font-display font-semibold text-primary">{season.title}</h3>
                <StatusPill status={season.status} />
              </div>
              <p className="text-xs text-secondary">{season.classroom_name} · Baseline: {season.baseline_exam_title}</p>
              <div className="flex items-center gap-4 text-xs text-secondary">
                <span className="flex items-center gap-1"><Shield size={12} /> {season.group_count} bands</span>
                <span className="flex items-center gap-1"><Users2 size={12} /> {season.member_count} students</span>
                {season.pending_promotion_count > 0 && (
                  <span className="flex items-center gap-1 text-violet-400"><Sparkles size={12} /> {season.pending_promotion_count} pending</span>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      <CreateSeasonModal open={createOpen} onClose={() => setCreateOpen(false)} classrooms={classrooms} />
    </div>
  );
}
