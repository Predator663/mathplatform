import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { ArrowLeft, Save, ChevronDown, ChevronUp, UserCog } from 'lucide-react';
import { groupAssignmentsApi } from '../../api';
import { LoadingPage, Button, EmptyState } from '../../components/ui';
import { formatDate, gradeColor, ASSIGNMENT_TYPE_LABELS } from '../../utils';
import type { GroupAssignmentRoster } from '../../types';

interface MemberAdjustment { adjustment: string; is_excused: boolean; note: string }
interface GroupRow {
  group_id: number; group_name: string; stream_name: string | null;
  score: string; is_absent: boolean; remarks: string;
  members: { student_id: number; student_name: string }[];
  adjustments: Record<number, MemberAdjustment>;
}

export default function GroupAssignmentMarksPage() {
  const { id } = useParams<{ id: string }>();
  const assignmentId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [rows, setRows] = useState<GroupRow[]>([]);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);

  const { data: roster, isLoading } = useQuery<GroupAssignmentRoster>({
    queryKey: ['group-assignment-roster', assignmentId],
    queryFn: () => groupAssignmentsApi.roster(assignmentId).then(r => r.data),
    enabled: !!assignmentId,
  });

  useEffect(() => {
    if (!roster) return;
    setRows(roster.groups.map(g => {
      const adjustments: Record<number, MemberAdjustment> = {};
      g.members.forEach(m => {
        const existing = g.score?.member_marks.find(mm => mm.student_id === m.student_id);
        adjustments[m.student_id] = {
          adjustment: existing ? String(existing.adjustment) : '0',
          is_excused: existing?.is_excused ?? false,
          note: existing?.note ?? '',
        };
      });
      return {
        group_id: g.group_id, group_name: g.group_name, stream_name: g.stream_name,
        score: g.score ? String(g.score.score) : '',
        is_absent: g.score?.is_absent ?? false,
        remarks: g.score?.remarks ?? '',
        members: g.members,
        adjustments,
      };
    }));
  }, [roster]);

  const toggleExpanded = (groupId: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(groupId) ? next.delete(groupId) : next.add(groupId);
      return next;
    });
  };

  const updateRow = (groupId: number, patch: Partial<GroupRow>) => {
    setRows(prev => prev.map(r => r.group_id === groupId ? { ...r, ...patch } : r));
  };

  const updateAdjustment = (groupId: number, studentId: number, patch: Partial<MemberAdjustment>) => {
    setRows(prev => prev.map(r => r.group_id !== groupId ? r : {
      ...r, adjustments: { ...r.adjustments, [studentId]: { ...r.adjustments[studentId], ...patch } },
    }));
  };

  const recordMutation = useMutation({
    mutationFn: (entries: object[]) => groupAssignmentsApi.recordScores(assignmentId, entries),
    onSuccess: (res) => {
      const errors = res.data?.errors ?? [];
      if (errors.length) {
        errors.forEach((e: string) => toast.error(e));
      } else {
        toast.success('Marks saved.');
      }
      queryClient.invalidateQueries({ queryKey: ['group-assignment-roster', assignmentId] });
      queryClient.invalidateQueries({ queryKey: ['group-assignments'] });
    },
    onError: () => toast.error('Could not save marks.'),
    onSettled: () => setSaving(false),
  });

  const handleSaveAll = () => {
    const dirtyRows = rows.filter(r => r.score !== '' || r.is_absent);
    if (dirtyRows.length === 0) {
      toast('Enter at least one group score first.', { icon: 'ℹ️' });
      return;
    }
    setSaving(true);
    const entries = dirtyRows.map(r => ({
      group_id: r.group_id,
      score: r.is_absent ? 0 : Number(r.score) || 0,
      is_absent: r.is_absent,
      remarks: r.remarks,
      member_adjustments: r.members.map(m => {
        const adj = r.adjustments[m.student_id];
        return {
          student_id: m.student_id,
          adjustment: Number(adj?.adjustment) || 0,
          is_excused: adj?.is_excused ?? false,
          note: adj?.note ?? '',
        };
      }),
    }));
    recordMutation.mutate(entries);
  };

  if (isLoading) return <LoadingPage />;
  if (!roster) return <EmptyState title="Assignment not found" />;

  const { assignment } = roster;
  const maxScore = Number(assignment.max_score);

  return (
    <div className="p-4 md:p-6 flex flex-col gap-5 max-w-5xl mx-auto page-enter">
      <button onClick={() => navigate('/groups/assignments')}
        className="flex items-center gap-1.5 text-sm text-secondary hover:text-primary w-fit">
        <ArrowLeft size={14} /> Back to Group Assignments
      </button>

      <div className="card p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-display font-bold text-primary">{assignment.title}</h1>
          <p className="text-sm text-secondary mt-0.5">
            <span className="badge badge-violet mr-2">{ASSIGNMENT_TYPE_LABELS[assignment.assignment_type]}</span>
            {assignment.subject_name && <span className="mr-2">{assignment.subject_name} · </span>}
            {formatDate(assignment.date_given)} · Max score {assignment.max_score}
            {assignment.stream_name && <> · {assignment.stream_name} stream only</>}
          </p>
        </div>
        <Button onClick={handleSaveAll} loading={saving}>
          <Save size={14} /> Save All Marks
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No groups to mark"
          message="No peer groups match this assignment's stream restriction yet." />
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map(row => {
            const pct = row.score !== '' && !row.is_absent ? Math.round((Number(row.score) / maxScore) * 1000) / 10 : null;
            const isOpen = expanded.has(row.group_id);
            return (
              <div key={row.group_id} className="card p-4">
                <div className="flex flex-col md:flex-row md:items-center gap-3">
                  <div className="flex-1 min-w-[160px]">
                    <p className="font-display font-semibold text-primary">{row.group_name}</p>
                    <p className="text-xs text-muted">
                      {row.stream_name || 'No stream'} · {row.members.length} member{row.members.length === 1 ? '' : 's'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="number" min={0} max={maxScore} step="0.5"
                      className="input w-24" placeholder={`/ ${maxScore}`}
                      value={row.score} disabled={row.is_absent}
                      onChange={e => updateRow(row.group_id, { score: e.target.value })}
                    />
                    <span className="text-xs text-muted">/ {assignment.max_score}</span>
                    {pct !== null && <span className={`font-mono font-semibold text-sm ${gradeColor(pct)}`}>{pct}%</span>}
                  </div>
                  <label className="flex items-center gap-1.5 text-xs text-secondary whitespace-nowrap">
                    <input type="checkbox" checked={row.is_absent}
                      onChange={e => updateRow(row.group_id, { is_absent: e.target.checked })} />
                    Whole group absent
                  </label>
                  <input
                    className="input flex-1 min-w-[140px]" placeholder="Remarks (optional)"
                    value={row.remarks} onChange={e => updateRow(row.group_id, { remarks: e.target.value })}
                  />
                  <Button variant="ghost" size="sm" onClick={() => toggleExpanded(row.group_id)}>
                    <UserCog size={14} /> Per-student {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </Button>
                </div>

                {isOpen && (
                  <div className="mt-3 pt-3 border-t border-surface">
                    <p className="text-xs text-muted mb-2">
                      Every member defaults to the group score above. Adjust a student here for
                      a bonus, penalty, or excuse — everyone else stays untouched.
                    </p>
                    <div className="grid gap-2">
                      {row.members.map(m => {
                        const adj = row.adjustments[m.student_id] || { adjustment: '0', is_excused: false, note: '' };
                        const effective = row.is_absent ? 0 : Math.max(0, Math.min(
                          (Number(row.score) || 0) + (Number(adj.adjustment) || 0), maxScore,
                        ));
                        return (
                          <div key={m.student_id} className="flex flex-wrap items-center gap-2 text-sm bg-surface-700/30 rounded-lg px-3 py-2">
                            <span className="flex-1 min-w-[120px] text-primary/90">{m.student_name}</span>
                            <input
                              type="number" step="0.5" className="input w-20"
                              value={adj.adjustment}
                              onChange={e => updateAdjustment(row.group_id, m.student_id, { adjustment: e.target.value })}
                            />
                            <span className="text-xs text-muted w-24">→ {effective}/{maxScore}</span>
                            <label className="flex items-center gap-1 text-xs text-secondary">
                              <input type="checkbox" checked={adj.is_excused}
                                onChange={e => updateAdjustment(row.group_id, m.student_id, { is_excused: e.target.checked })} />
                              Excuse
                            </label>
                            <input
                              className="input flex-1 min-w-[120px]" placeholder="Note (optional)"
                              value={adj.note}
                              onChange={e => updateAdjustment(row.group_id, m.student_id, { note: e.target.value })}
                            />
                          </div>
                        );
                      })}
                    </div>
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
