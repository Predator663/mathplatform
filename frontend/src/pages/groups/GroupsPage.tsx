import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  Users, Sparkles, Plus, Camera, Trash2, Edit2, ArrowRightLeft, X,
  FileText, FileSpreadsheet, Award, UserPlus, History, Check, TrendingUp, AlertTriangle,
} from 'lucide-react';
import { groupsApi, studentsApi, subjectsApi } from '../../api';
import {
  LoadingPage, EmptyState, Button, Select, Modal, StatCard,
} from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import { downloadBlob, TERM_LABELS } from '../../utils';
import type {
  Classroom, PaginatedResponse, Subject, GroupsOverview, StudentGroup,
  StudentPerformanceRow, PerformanceTier, GroupTransferLogEntry,
  GroupEffectivenessOverview, RebalanceSuggestions, PeerConstraintEntry,
} from '../../types';

const TIER_META: Record<PerformanceTier, { label: string; color: string; bg: string }> = {
  very_strong: { label: 'Very Strong', color: 'text-emerald-400', bg: 'bg-emerald-500/15' },
  strong:      { label: 'Strong',      color: 'text-azure-400',   bg: 'bg-azure-500/15' },
  average:     { label: 'Average',     color: 'text-amber-400',   bg: 'bg-amber-500/15' },
  weak:        { label: 'Weak',        color: 'text-rose-400',    bg: 'bg-rose-500/15' },
  unrated:     { label: 'Not Rated',   color: 'text-secondary',   bg: 'bg-surface-700' },
};

const BADGE_PALETTE = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#f43f5e', '#06b6d4', '#84cc16', '#ec4899'];

function TierPill({ tier }: { tier: PerformanceTier }) {
  const m = TIER_META[tier] ?? TIER_META.unrated;
  return <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${m.color} ${m.bg}`}>{m.label}</span>;
}

export default function GroupsPage() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const canAccess = user?.role === 'super_admin' || user?.role === 'teacher';

  const [selectedClass, setSelectedClass] = useState<number | null>(null);
  const [subjectFilter, setSubjectFilter] = useState('');
  const [termFilter, setTermFilter] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'score' | 'members'>('name');

  const [autoGenOpen, setAutoGenOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [renameGroup, setRenameGroup] = useState<StudentGroup | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [effectivenessOpen, setEffectivenessOpen] = useState(false);
  const [rebalanceOpen, setRebalanceOpen] = useState(false);
  const [constraintsOpen, setConstraintsOpen] = useState(false);
  const [constraintStudentA, setConstraintStudentA] = useState('');
  const [constraintStudentB, setConstraintStudentB] = useState('');
  const [constraintType, setConstraintType] = useState<'avoid' | 'prefer'>('avoid');
  const [constraintReason, setConstraintReason] = useState('');
  const [movingStudent, setMovingStudent] = useState<{ studentId: number; name: string } | null>(null);

  const badgeInputRef = useRef<HTMLInputElement>(null);
  const [badgeTargetId, setBadgeTargetId] = useState<number | null>(null);

  // ── Data ──────────────────────────────────────────────────────────────
  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms-all-groups'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
    enabled: canAccess,
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects-all-groups'],
    queryFn: () => subjectsApi.list({ page_size: 100 }).then(r => r.data),
    enabled: canAccess,
  });
  const subjects: Subject[] = Array.isArray(subjectsData)
    ? subjectsData : (subjectsData as PaginatedResponse<Subject>)?.results ?? [];

  const overviewKey = ['groups-overview', selectedClass, subjectFilter, termFilter];
  const { data: overview, isLoading } = useQuery<GroupsOverview>({
    queryKey: overviewKey,
    queryFn: () => groupsApi.overview(selectedClass!, {
      subject_id: subjectFilter || undefined, term: termFilter || undefined,
    }).then(r => r.data),
    enabled: !!selectedClass,
  });

  const { data: transferLog } = useQuery<GroupTransferLogEntry[]>({
    queryKey: ['groups-transfers', selectedClass],
    queryFn: () => groupsApi.transfers(selectedClass!).then(r => r.data),
    enabled: !!selectedClass && historyOpen,
  });

  const { data: effectiveness, isLoading: effectivenessLoading } = useQuery<GroupEffectivenessOverview>({
    queryKey: ['groups-effectiveness', selectedClass, subjectFilter, termFilter],
    queryFn: () => groupsApi.effectiveness(selectedClass!, {
      subject_id: subjectFilter || undefined, term: termFilter || undefined,
    }).then(r => r.data),
    enabled: !!selectedClass && effectivenessOpen,
  });

  const { data: rebalance, isLoading: rebalanceLoading } = useQuery<RebalanceSuggestions>({
    queryKey: ['groups-rebalance', selectedClass, subjectFilter, termFilter],
    queryFn: () => groupsApi.rebalanceSuggestions(selectedClass!, {
      subject_id: subjectFilter || undefined, term: termFilter || undefined,
    }).then(r => r.data),
    enabled: !!selectedClass && rebalanceOpen,
  });

  const { data: constraints } = useQuery<PeerConstraintEntry[]>({
    queryKey: ['groups-constraints', selectedClass],
    queryFn: () => groupsApi.constraints(selectedClass!).then(r => r.data.results ?? r.data),
    enabled: !!selectedClass && constraintsOpen,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: overviewKey });

  // ── Mutations ─────────────────────────────────────────────────────────
  const autoGenMutation = useMutation({
    mutationFn: (payload: object) => groupsApi.autoGenerate(payload),
    onSuccess: (res) => {
      const warnings: string[] = res.data.warnings ?? [];
      toast.success(`Created ${res.data.groups.length} group(s).`);
      warnings.forEach((w: string) => toast(w, { icon: '⚠️', duration: 6000 }));
      invalidate();
      setAutoGenOpen(false);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? 'Auto-generation failed');
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: object) => groupsApi.create(data),
    onSuccess: () => { toast.success('Group created'); invalidate(); setCreateOpen(false); },
    onError: () => toast.error('Failed to create group'),
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: object }) => groupsApi.update(id, data),
    onSuccess: () => { toast.success('Group updated'); invalidate(); setRenameGroup(null); },
    onError: () => toast.error('Failed to update group'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => groupsApi.delete(id),
    onSuccess: () => { toast.success('Group deleted'); invalidate(); },
    onError: () => toast.error('Failed to delete group'),
  });

  const badgeMutation = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => groupsApi.uploadBadge(id, file),
    onSuccess: () => { toast.success('Badge updated'); invalidate(); },
    onError: () => toast.error('Badge upload failed (must be an image under 3MB)'),
  });

  const addMemberMutation = useMutation({
    mutationFn: ({ groupId, studentId }: { groupId: number; studentId: number }) =>
      groupsApi.addMember(groupId, studentId),
    onSuccess: () => { toast.success('Student added'); invalidate(); },
    onError: () => toast.error('Failed to add student'),
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ groupId, studentId }: { groupId: number; studentId: number }) =>
      groupsApi.removeMember(groupId, studentId),
    onSuccess: () => { toast.success('Student removed from group'); invalidate(); },
    onError: () => toast.error('Failed to remove student'),
  });

  const transferMutation = useMutation({
    mutationFn: ({ studentId, toGroupId, reason }: { studentId: number; toGroupId: number; reason?: string }) =>
      groupsApi.transferMember(studentId, toGroupId, reason),
    onSuccess: (res) => {
      toast.success(res.data.detail ?? 'Student moved');
      (res.data.warnings ?? []).forEach((w: string) => toast(w, { icon: '⚠️', duration: 6000 }));
      invalidate();
      queryClient.invalidateQueries({ queryKey: ['groups-rebalance', selectedClass] });
      setMovingStudent(null);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? 'Transfer failed');
    },
  });

  const createConstraintMutation = useMutation({
    mutationFn: (data: object) => groupsApi.createConstraint(data),
    onSuccess: () => {
      toast.success('Constraint added');
      queryClient.invalidateQueries({ queryKey: ['groups-constraints', selectedClass] });
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[]> } };
      const msg = e?.response?.data ? Object.values(e.response.data).flat().join(' ') : 'Failed to add constraint';
      toast.error(msg || 'Failed to add constraint');
    },
  });

  const deleteConstraintMutation = useMutation({
    mutationFn: (id: number) => groupsApi.deleteConstraint(id),
    onSuccess: () => {
      toast.success('Constraint removed');
      queryClient.invalidateQueries({ queryKey: ['groups-constraints', selectedClass] });
    },
    onError: () => toast.error('Failed to remove constraint'),
  });

  // ── Export handlers ──────────────────────────────────────────────────
  async function handleExport(kind: 'summary' | 'roster', format: 'pdf' | 'excel') {
    if (!selectedClass) return;
    try {
      const fn = kind === 'summary' ? groupsApi.exportSummary : groupsApi.exportRoster;
      const res = await fn(selectedClass, format, { sort_by: sortBy, term: termFilter || undefined });
      const ext = format === 'pdf' ? 'pdf' : 'xlsx';
      downloadBlob(res.data, `groups_${kind}.${ext}`);
      toast.success('Export downloaded');
    } catch {
      toast.error('Export failed — make sure this classroom has at least one group.');
    }
  }

  if (!canAccess) {
    return (
      <div className="p-6">
        <EmptyState icon={<Users size={40} />} title="Not available"
          message="Peer groups are managed by teachers and admins." />
      </div>
    );
  }

  const groups = overview?.groups ?? [];
  const sortedGroups = [...groups].sort((a, b) => {
    if (sortBy === 'name') return a.name.localeCompare(b.name);
    if (sortBy === 'score') return (b.group_average ?? -1) - (a.group_average ?? -1);
    return b.member_count - a.member_count;
  });

  return (
    <div className="p-4 md:p-6 flex flex-col gap-5 max-w-7xl mx-auto page-enter">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold text-primary flex items-center gap-2">
            <Users className="text-azure-400" size={24} /> Peer Learning Groups
          </h1>
          <p className="text-sm text-secondary mt-0.5">
            Auto-balance students into mixed-ability groups, or manage them by hand.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => setHistoryOpen(true)} disabled={!selectedClass}>
            <History size={14} /> Transfer History
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setEffectivenessOpen(true)} disabled={!selectedClass}>
            <TrendingUp size={14} /> Effectiveness
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setRebalanceOpen(true)} disabled={!selectedClass}>
            <AlertTriangle size={14} /> Rebalance Suggestions
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setConstraintsOpen(true)} disabled={!selectedClass}>
            <ArrowRightLeft size={14} /> Peer Constraints
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setCreateOpen(true)} disabled={!selectedClass}>
            <Plus size={14} /> New Group
          </Button>
          <Button size="sm" onClick={() => setAutoGenOpen(true)} disabled={!selectedClass}>
            <Sparkles size={14} /> Auto-Generate Groups
          </Button>
        </div>
      </div>

      {/* Classroom / filter bar */}
      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <div className="min-w-[220px]">
          <Select
            label="Classroom"
            options={[{ value: '', label: 'Select a classroom…' }, ...classrooms.map(c => ({
              value: c.id, label: `${c.name} (${c.grade_level_name})`,
            }))]}
            value={selectedClass ?? ''}
            onChange={e => setSelectedClass(e.target.value ? Number(e.target.value) : null)}
          />
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Subject (optional)"
            options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
            value={subjectFilter}
            onChange={e => setSubjectFilter(e.target.value)}
          />
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Term (optional)"
            options={[{ value: '', label: 'All terms' }, ...Object.entries(TERM_LABELS).map(([v, l]) => ({ value: v, label: l }))]}
            value={termFilter}
            onChange={e => setTermFilter(e.target.value)}
          />
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Sort groups by"
            options={[
              { value: 'name', label: 'Name' },
              { value: 'score', label: 'Group Average' },
              { value: 'members', label: 'Member Count' },
            ]}
            value={sortBy}
            onChange={e => setSortBy(e.target.value as 'name' | 'score' | 'members')}
          />
        </div>
      </div>

      {!selectedClass ? (
        <EmptyState icon={<Users size={40} />} title="Choose a classroom"
          message="Select a classroom above to view and manage its peer groups." />
      ) : isLoading ? (
        <LoadingPage />
      ) : (
        <>
          {/* Tier stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard label="Students" value={overview?.performance.length ?? 0} icon={<Users size={16} />} />
            <StatCard label="Very Strong" value={overview?.tier_counts.very_strong ?? 0} color="green" icon={<Award size={16} />} />
            <StatCard label="Strong" value={overview?.tier_counts.strong ?? 0} color="blue" icon={<Award size={16} />} />
            <StatCard label="Average" value={overview?.tier_counts.average ?? 0} color="amber" />
            <StatCard label="Weak" value={overview?.tier_counts.weak ?? 0} color="rose" />
          </div>

          {/* Export bar */}
          <div className="card p-4 flex flex-wrap items-center gap-2">
            <span className="text-xs font-display font-semibold uppercase tracking-wider text-secondary mr-1">
              Export ({sortBy === 'name' ? 'by name' : sortBy === 'score' ? 'by score' : 'by size'}):
            </span>
            <Button variant="secondary" size="sm" onClick={() => handleExport('summary', 'pdf')}>
              <FileText size={13} /> Summary PDF
            </Button>
            <Button variant="secondary" size="sm" onClick={() => handleExport('summary', 'excel')}>
              <FileSpreadsheet size={13} /> Summary Excel
            </Button>
            <Button variant="secondary" size="sm" onClick={() => handleExport('roster', 'pdf')}>
              <FileText size={13} /> Roster + Scores PDF
            </Button>
            <Button variant="secondary" size="sm" onClick={() => handleExport('roster', 'excel')}>
              <FileSpreadsheet size={13} /> Roster + Scores Excel
            </Button>
          </div>

          {/* Groups grid */}
          {sortedGroups.length === 0 ? (
            <EmptyState icon={<Sparkles size={40} />} title="No groups yet"
              message="Use Auto-Generate to balance students into groups, or create one manually." />
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {sortedGroups.map(group => (
                <div key={group.id} className="card p-0 overflow-hidden flex flex-col">
                  {/* Banner */}
                  <div className="flex items-center gap-3 px-4 py-3" style={{ backgroundColor: group.badge_color }}>
                    <button
                      onClick={() => { setBadgeTargetId(group.id); badgeInputRef.current?.click(); }}
                      className="relative w-11 h-11 rounded-full flex-shrink-0 flex items-center justify-center bg-black/20 hover:bg-black/30 transition-colors overflow-hidden"
                      title="Upload group badge"
                    >
                      {group.badge_image_url ? (
                        <img src={group.badge_image_url} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <Camera size={16} className="text-white/80" />
                      )}
                    </button>
                    <div className="flex-1 min-w-0">
                      <p className="font-display font-bold text-white truncate">{group.name}</p>
                      <p className="text-xs text-white/80">
                        {group.member_count} member{group.member_count !== 1 ? 's' : ''}
                        {group.group_average != null ? ` · Avg ${group.group_average}%` : ''}
                        {group.subject_name ? ` · ${group.subject_name}` : ''}
                      </p>
                    </div>
                    <button onClick={() => setRenameGroup(group)} className="text-white/80 hover:text-white p-1.5 rounded-lg hover:bg-black/20" title="Edit group">
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => { if (confirm(`Delete "${group.name}"? Members will become ungrouped.`)) deleteMutation.mutate(group.id); }}
                      className="text-white/80 hover:text-white p-1.5 rounded-lg hover:bg-black/20" title="Delete group"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>

                  {/* Members */}
                  <div className="flex-1 divide-y divide-surface">
                    {group.members.length === 0 && (
                      <p className="text-xs text-muted px-4 py-3">No members yet — add students below.</p>
                    )}
                    {group.members.map(m => (
                      <div key={m.id} className="flex items-center gap-2 px-4 py-2.5">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-primary truncate">
                            {m.student_name} {m.is_anchor && <span title="Anchor student">⭐</span>}
                          </p>
                          <p className="text-xs text-secondary">{m.student_code}</p>
                        </div>
                        <TierPill tier={m.tier} />
                        <span className="text-xs font-mono text-secondary w-12 text-right">
                          {m.average_at_placement != null ? `${m.average_at_placement}%` : '—'}
                        </span>
                        <button
                          onClick={() => setMovingStudent({ studentId: m.student_id, name: m.student_name })}
                          className="p-1.5 text-secondary hover:text-azure-400 hover:bg-surface-700 rounded-lg"
                          title="Move to another group"
                        >
                          <ArrowRightLeft size={13} />
                        </button>
                        <button
                          onClick={() => removeMemberMutation.mutate({ groupId: group.id, studentId: m.student_id })}
                          className="p-1.5 text-secondary hover:text-rose-400 hover:bg-surface-700 rounded-lg"
                          title="Remove from group"
                        >
                          <X size={13} />
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Add member (from ungrouped pool) */}
                  {(overview?.ungrouped_students.length ?? 0) > 0 && (
                    <div className="px-4 py-3 border-t border-surface">
                      <select
                        className="input text-xs"
                        value=""
                        onChange={e => {
                          if (e.target.value) addMemberMutation.mutate({ groupId: group.id, studentId: Number(e.target.value) });
                        }}
                      >
                        <option value="">+ Add ungrouped student…</option>
                        {overview!.ungrouped_students.map(s => (
                          <option key={s.student_id} value={s.student_id}>
                            {s.student_name} ({s.average != null ? `${s.average}%` : 'no data'})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Ungrouped students panel */}
          {(overview?.ungrouped_students.length ?? 0) > 0 && (
            <div className="card p-4">
              <h3 className="font-display font-semibold text-primary mb-3 flex items-center gap-2">
                <UserPlus size={16} className="text-amber-400" /> Ungrouped Students ({overview!.ungrouped_students.length})
              </h3>
              <div className="flex flex-col divide-y divide-surface">
                {overview!.ungrouped_students.map((s: StudentPerformanceRow) => (
                  <div key={s.student_id} className="flex items-center gap-2 py-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-primary">{s.student_name}</p>
                      <p className="text-xs text-secondary">{s.student_code}</p>
                    </div>
                    <TierPill tier={s.tier} />
                    <span className="text-xs font-mono text-secondary w-12 text-right">
                      {s.average != null ? `${s.average}%` : '—'}
                    </span>
                    {groups.length > 0 && (
                      <select
                        className="input text-xs w-40"
                        value=""
                        onChange={e => { if (e.target.value) addMemberMutation.mutate({ groupId: Number(e.target.value), studentId: s.student_id }); }}
                      >
                        <option value="">Add to group…</option>
                        {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                      </select>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Hidden badge file input, shared across group cards */}
      <input
        ref={badgeInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={e => {
          const file = e.target.files?.[0];
          if (file && badgeTargetId) badgeMutation.mutate({ id: badgeTargetId, file });
          e.target.value = '';
        }}
      />

      {/* ── Auto-Generate Modal ───────────────────────────────────────── */}
      {autoGenOpen && (
        <AutoGenerateModal
          onClose={() => setAutoGenOpen(false)}
          onSubmit={payload => autoGenMutation.mutate({ classroom_id: selectedClass, subject_id: subjectFilter || undefined, term: termFilter || undefined, ...payload })}
          loading={autoGenMutation.isPending}
        />
      )}

      {/* ── Create Group Modal ───────────────────────────────────────── */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Group"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              loading={createMutation.isPending}
              type="submit"
              form="create-group-form"
            >
              Create
            </Button>
          </>
        }
      >
        <CreateGroupForm
          onSubmit={data => createMutation.mutate({ ...data, classroom: selectedClass, academic_year: classrooms.find(c => c.id === selectedClass)?.academic_year })}
        />
      </Modal>

      {/* ── Rename / Edit Group Modal ────────────────────────────────── */}
      <Modal open={!!renameGroup} onClose={() => setRenameGroup(null)} title="Edit Group">
        {renameGroup && (
          <EditGroupForm
            group={renameGroup}
            onCancel={() => setRenameGroup(null)}
            onSubmit={data => renameMutation.mutate({ id: renameGroup.id, data })}
            loading={renameMutation.isPending}
          />
        )}
      </Modal>

      {/* ── Move Student Modal ───────────────────────────────────────── */}
      <Modal open={!!movingStudent} onClose={() => setMovingStudent(null)} title="Move Student">
        {movingStudent && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-secondary">
              Move <b className="text-primary">{movingStudent.name}</b> to:
            </p>
            <div className="flex flex-col gap-2">
              {groups.map(g => (
                <button
                  key={g.id}
                  onClick={() => transferMutation.mutate({ studentId: movingStudent.studentId, toGroupId: g.id })}
                  disabled={transferMutation.isPending}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl border border-surface hover:border-azure-500/50 hover:bg-surface-700/50 transition-colors text-left disabled:opacity-50"
                >
                  <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: g.badge_color }} />
                  <span className="text-sm text-primary flex-1">{g.name}</span>
                  <span className="text-xs text-secondary">{g.member_count} members</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </Modal>

      {/* ── Transfer History Modal ───────────────────────────────────── */}
      <Modal open={historyOpen} onClose={() => setHistoryOpen(false)} title="Transfer History" size="lg">
        <div className="flex flex-col divide-y divide-surface max-h-[60vh] overflow-y-auto">
          {(transferLog ?? []).length === 0 && <p className="text-sm text-muted py-4 text-center">No transfers recorded yet.</p>}
          {(transferLog ?? []).map(t => (
            <div key={t.id} className="py-2.5 text-sm">
              <p className="text-primary">
                <b>{t.student_name}</b>: {t.from_group_name ?? '—'} → {t.to_group_name ?? '—'}
              </p>
              <p className="text-xs text-secondary">
                {new Date(t.transferred_at).toLocaleString()} · {t.transferred_by_name ?? 'System'}
                {t.reason ? ` · ${t.reason}` : ''}
              </p>
              {t.warnings && <p className="text-xs text-amber-400 mt-0.5">⚠️ {t.warnings}</p>}
            </div>
          ))}
        </div>
      </Modal>

      {/* ── Group Effectiveness Modal ────────────────────────────────── */}
      <Modal open={effectivenessOpen} onClose={() => setEffectivenessOpen(false)} title="Group Effectiveness" size="lg">
        {effectivenessLoading ? (
          <LoadingPage />
        ) : !effectiveness || effectiveness.students_with_data === 0 ? (
          <p className="text-sm text-muted py-4 text-center">
            Not enough exam data yet since students joined their groups to measure movement.
          </p>
        ) : (
          <div className="flex flex-col gap-4 max-h-[70vh] overflow-y-auto">
            <p className="text-xs text-secondary">
              Score change per student since they joined their current group, vs. the average
              they had when placed. Positive means improvement.
            </p>
            <div className="grid grid-cols-3 gap-2">
              <DeltaStat label="Classroom avg" value={effectiveness.classroom_average_delta} />
              <DeltaStat label="Anchors (mentors)" value={effectiveness.anchor_average_delta} />
              <DeltaStat label="Non-anchors" value={effectiveness.non_anchor_average_delta} />
            </div>
            <div className="flex flex-col gap-3">
              {effectiveness.groups.map(g => (
                <div key={g.group_id} className="card p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-semibold text-primary text-sm">{g.group_name}</span>
                    <DeltaPill value={g.average_delta} />
                  </div>
                  {!g.has_sufficient_data ? (
                    <p className="text-xs text-muted">No post-placement exam data yet.</p>
                  ) : (
                    <div className="flex flex-col divide-y divide-surface">
                      {g.members.map(m => (
                        <div key={m.student_id} className="py-1.5 flex items-center justify-between text-sm">
                          <span className="text-primary flex items-center gap-1.5">
                            {m.student_name}
                            {m.is_anchor && <Award size={12} className="text-amber-400" />}
                          </span>
                          <span className="flex items-center gap-2 text-xs text-secondary">
                            {m.average_at_placement ?? '—'}% → {m.current_average_since_joining ?? '—'}%
                            <DeltaPill value={m.delta} />
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>

      {/* ── Rebalance Suggestions Modal ──────────────────────────────── */}
      <Modal open={rebalanceOpen} onClose={() => setRebalanceOpen(false)} title="Rebalance Suggestions" size="lg">
        {rebalanceLoading ? (
          <LoadingPage />
        ) : !rebalance || (rebalance.tier_changes.length === 0 && rebalance.groups_needing_attention.length === 0) ? (
          <p className="text-sm text-muted py-4 text-center">
            No drift detected — every group's live tiers still match how it was formed.
          </p>
        ) : (
          <div className="flex flex-col gap-5 max-h-[70vh] overflow-y-auto">
            {rebalance.groups_needing_attention.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-primary mb-2 flex items-center gap-1.5">
                  <AlertTriangle size={14} className="text-amber-400" /> Groups needing attention
                </h3>
                <div className="flex flex-col gap-2">
                  {rebalance.groups_needing_attention.map(g => (
                    <div key={g.group_id} className="card p-3">
                      <p className="text-sm text-primary font-medium">{g.group_name}</p>
                      <p className="text-xs text-secondary mb-2">{g.reason}</p>
                      {g.candidates.length === 0 ? (
                        <p className="text-xs text-muted">No spare anchor elsewhere to suggest right now.</p>
                      ) : (
                        <div className="flex flex-col gap-1.5">
                          {g.candidates.map(c => (
                            <div key={c.student_id} className="flex items-center justify-between text-xs">
                              <span className="text-secondary">
                                {c.student_name} — {c.current_average}% ({c.from_group_name})
                              </span>
                              <Button
                                size="sm" variant="secondary"
                                disabled={transferMutation.isPending}
                                onClick={() => transferMutation.mutate({
                                  studentId: c.student_id, toGroupId: g.group_id,
                                  reason: `Rebalance suggestion: moved to cover ${g.group_name}'s missing anchor`,
                                })}
                              >
                                Move here
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {rebalance.tier_changes.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-primary mb-2">Tier drift since placement</h3>
                <div className="flex flex-col divide-y divide-surface">
                  {rebalance.tier_changes.map(c => (
                    <div key={c.student_id} className="py-2 flex items-center justify-between text-sm">
                      <div>
                        <span className="text-primary">{c.student_name}</span>
                        <span className="text-xs text-secondary ml-1.5">({c.group_name})</span>
                      </div>
                      <span className="flex items-center gap-1.5 text-xs">
                        <TierPill tier={c.tier_at_placement} />
                        <span className={c.direction === 'up' ? 'text-emerald-400' : 'text-rose-400'}>→</span>
                        <TierPill tier={c.current_tier} />
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* ── Peer Constraints Modal ───────────────────────────────────── */}
      <Modal open={constraintsOpen} onClose={() => setConstraintsOpen(false)} title="Peer Constraints" size="lg">
        <div className="flex flex-col gap-4 max-h-[70vh] overflow-y-auto">
          <p className="text-xs text-secondary">
            Standing rules Auto-Generate will try to honour — "keep apart" is treated as a hard
            rule, "keep together" as best-effort. These persist across grouping rounds.
          </p>

          <div className="card p-3 flex flex-col gap-2">
            <div className="grid grid-cols-2 gap-2">
              <Select
                label="Student A"
                options={[{ value: '', label: 'Select…' }, ...(overview?.performance ?? []).map(p => ({
                  value: p.student_id, label: p.student_name,
                }))]}
                value={constraintStudentA}
                onChange={e => setConstraintStudentA(e.target.value)}
              />
              <Select
                label="Student B"
                options={[{ value: '', label: 'Select…' }, ...(overview?.performance ?? [])
                  .filter(p => String(p.student_id) !== constraintStudentA)
                  .map(p => ({ value: p.student_id, label: p.student_name }))]}
                value={constraintStudentB}
                onChange={e => setConstraintStudentB(e.target.value)}
              />
            </div>
            <Select
              label="Rule"
              options={[
                { value: 'avoid', label: 'Keep Apart' },
                { value: 'prefer', label: 'Keep Together' },
              ]}
              value={constraintType}
              onChange={e => setConstraintType(e.target.value as 'avoid' | 'prefer')}
            />
            <input
              className="input" placeholder="Reason (optional)"
              value={constraintReason} onChange={e => setConstraintReason(e.target.value)}
            />
            <Button
              size="sm"
              disabled={!constraintStudentA || !constraintStudentB || createConstraintMutation.isPending}
              onClick={() => {
                createConstraintMutation.mutate({
                  classroom: selectedClass, student_a: Number(constraintStudentA),
                  student_b: Number(constraintStudentB), constraint_type: constraintType,
                  reason: constraintReason,
                }, {
                  onSuccess: () => {
                    setConstraintStudentA(''); setConstraintStudentB(''); setConstraintReason('');
                  },
                });
              }}
            >
              <Plus size={14} /> Add Constraint
            </Button>
          </div>

          <div className="flex flex-col divide-y divide-surface">
            {(constraints ?? []).length === 0 && (
              <p className="text-sm text-muted py-4 text-center">No constraints set for this classroom yet.</p>
            )}
            {(constraints ?? []).map(c => (
              <div key={c.id} className="py-2.5 flex items-center justify-between text-sm">
                <div>
                  <p className="text-primary">
                    <b>{c.student_a_name}</b> & <b>{c.student_b_name}</b>
                    <span className={`ml-2 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                      c.constraint_type === 'avoid' ? 'text-rose-400 bg-rose-500/15' : 'text-emerald-400 bg-emerald-500/15'
                    }`}>
                      {c.constraint_type_display}
                    </span>
                  </p>
                  {c.reason && <p className="text-xs text-secondary">{c.reason}</p>}
                </div>
                <button
                  className="text-muted hover:text-rose-400"
                  onClick={() => deleteConstraintMutation.mutate(c.id)}
                  disabled={deleteConstraintMutation.isPending}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  );
}

function DeltaPill({ value }: { value: number | null }) {
  if (value === null) return <span className="text-[10px] text-muted">no data</span>;
  const positive = value > 0, negative = value < 0;
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
      positive ? 'text-emerald-400 bg-emerald-500/15' : negative ? 'text-rose-400 bg-rose-500/15' : 'text-secondary bg-surface-700'
    }`}>
      {positive ? '+' : ''}{value}%
    </span>
  );
}

function DeltaStat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="card p-3 text-center">
      <p className="text-[11px] text-muted">{label}</p>
      <p className={`text-lg font-bold ${
        value === null ? 'text-secondary' : value > 0 ? 'text-emerald-400' : value < 0 ? 'text-rose-400' : 'text-secondary'
      }`}>
        {value === null ? '—' : `${value > 0 ? '+' : ''}${value}%`}
      </p>
    </div>
  );
}

// ── Auto-Generate sub-form ─────────────────────────────────────────────────
function AutoGenerateModal({ onClose, onSubmit, loading }: {
  onClose: () => void; onSubmit: (payload: Record<string, unknown>) => void; loading: boolean;
}) {
  const [mode, setMode] = useState<'count' | 'size'>('count');
  const [value, setValue] = useState('4');
  const [namePrefix, setNamePrefix] = useState('Group');
  const [replaceExisting, setReplaceExisting] = useState(false);

  return (
    <Modal open onClose={onClose} title="Auto-Generate Balanced Groups"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={loading}
            onClick={() => onSubmit({
              [mode === 'count' ? 'group_count' : 'group_size']: Number(value) || undefined,
              name_prefix: namePrefix, replace_existing: replaceExisting,
            })}
          >
            <Sparkles size={14} /> Generate
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-xs text-secondary bg-azure-500/10 border border-azure-500/20 rounded-xl px-3 py-2">
          Students are ranked by average score and split using a balanced draft, so every group gets
          at least one Strong/Very-Strong peer mentor whenever there are enough of them to go around.
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setMode('count')}
            className={`flex-1 py-2 rounded-xl text-sm font-medium border transition-colors ${mode === 'count' ? 'border-azure-500 bg-azure-500/10 text-azure-400' : 'border-surface text-secondary'}`}
          >
            By number of groups
          </button>
          <button
            onClick={() => setMode('size')}
            className={`flex-1 py-2 rounded-xl text-sm font-medium border transition-colors ${mode === 'size' ? 'border-azure-500 bg-azure-500/10 text-azure-400' : 'border-surface text-secondary'}`}
          >
            By students per group
          </button>
        </div>
        <div>
          <label className="text-xs font-medium text-secondary uppercase tracking-wider">
            {mode === 'count' ? 'Number of groups' : 'Students per group'}
          </label>
          <input
            type="number" min={1} value={value} onChange={e => setValue(e.target.value)}
            className="input mt-1" placeholder="Leave blank to auto-decide from strong students"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-secondary uppercase tracking-wider">Group name prefix</label>
          <input value={namePrefix} onChange={e => setNamePrefix(e.target.value)} className="input mt-1" />
          <p className="text-xs text-muted mt-1">Groups will be named "{namePrefix} A", "{namePrefix} B", …</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
          <input type="checkbox" checked={replaceExisting} onChange={e => setReplaceExisting(e.target.checked)} />
          Replace all existing groups for this classroom/year (instead of adding alongside them)
        </label>
      </div>
    </Modal>
  );
}

function CreateGroupForm({ onSubmit }: { onSubmit: (data: Record<string, unknown>) => void }) {
  const [name, setName] = useState('');
  const [color, setColor] = useState(BADGE_PALETTE[0]);
  const [description, setDescription] = useState('');

  return (
    <form
      id="create-group-form"
      className="flex flex-col gap-4"
      onSubmit={e => { e.preventDefault(); if (name.trim()) onSubmit({ name: name.trim(), badge_color: color, description }); }}
    >
      <div>
        <label className="text-xs font-medium text-secondary uppercase tracking-wider">Group Name *</label>
        <input value={name} onChange={e => setName(e.target.value)} required className="input mt-1" placeholder="e.g. The Problem Solvers" />
      </div>
      <div>
        <label className="text-xs font-medium text-secondary uppercase tracking-wider">Badge Colour</label>
        <div className="flex gap-2 mt-1 flex-wrap">
          {BADGE_PALETTE.map(c => (
            <button key={c} type="button" onClick={() => setColor(c)}
              className="w-7 h-7 rounded-full border-2 transition-transform"
              style={{ backgroundColor: c, borderColor: color === c ? '#fff' : 'transparent', transform: color === c ? 'scale(1.15)' : 'scale(1)' }} />
          ))}
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-secondary uppercase tracking-wider">Description (optional)</label>
        <textarea value={description} onChange={e => setDescription(e.target.value)} className="input mt-1" rows={2} />
      </div>
    </form>
  );
}

function EditGroupForm({ group, onSubmit, onCancel, loading }: {
  group: StudentGroup; onSubmit: (data: Record<string, unknown>) => void; onCancel: () => void; loading: boolean;
}) {
  const [name, setName] = useState(group.name);
  const [color, setColor] = useState(group.badge_color);
  const [description, setDescription] = useState(group.description);

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={e => { e.preventDefault(); if (name.trim()) onSubmit({ name: name.trim(), badge_color: color, description }); }}
    >
      <div>
        <label className="text-xs font-medium text-secondary uppercase tracking-wider">Group Name *</label>
        <input value={name} onChange={e => setName(e.target.value)} required className="input mt-1" />
      </div>
      <div>
        <label className="text-xs font-medium text-secondary uppercase tracking-wider">Badge Colour</label>
        <div className="flex gap-2 mt-1 flex-wrap">
          {BADGE_PALETTE.map(c => (
            <button key={c} type="button" onClick={() => setColor(c)}
              className="w-7 h-7 rounded-full border-2 transition-transform"
              style={{ backgroundColor: c, borderColor: color === c ? '#fff' : 'transparent', transform: color === c ? 'scale(1.15)' : 'scale(1)' }} />
          ))}
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-secondary uppercase tracking-wider">Description</label>
        <textarea value={description} onChange={e => setDescription(e.target.value)} className="input mt-1" rows={2} />
      </div>
      <div className="flex gap-3 pt-1">
        <Button type="button" variant="secondary" className="flex-1" onClick={onCancel}>Cancel</Button>
        <Button type="submit" className="flex-1" loading={loading}><Check size={14} /> Save</Button>
      </div>
    </form>
  );
}
