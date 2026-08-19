import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { Reorder, AnimatePresence } from 'framer-motion';
import {
  BookMarked, Plus, Search, Edit2, Trash2, RotateCcw,
  Eye, EyeOff, GripVertical, GraduationCap,
} from 'lucide-react';
import { examsApi, subjectsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Input, Select, Modal } from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import type { MathTopic, Subject, GradeLevel, PaginatedResponse } from '../../types';

interface TopicFormData {
  subject: number; grade_level: number | ''; name: string; description: string; color: string;
}

const DEFAULT_COLORS = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4', '#ec4899'];
const UNASSIGNED_CLASS = 0;

function unwrap<T>(data: { results?: T[] } | T[] | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results ?? [];
}

export default function TopicsPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin';
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [classFilter, setClassFilter] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [modalTopic, setModalTopic] = useState<MathTopic | null | 'new'>(null);
  const [confirmDelete, setConfirmDelete] = useState<MathTopic | null>(null);

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
  });
  const subjects = unwrap<Subject>(subjectsData);

  const { data: gradesData } = useQuery<PaginatedResponse<GradeLevel> | GradeLevel[]>({
    queryKey: ['grade-levels'],
    queryFn: () => studentsApi.gradeLevels().then(r => r.data),
  });
  const grades = unwrap<GradeLevel>(gradesData).sort((a, b) => a.order - b.order);

  const { data: topicsData, isLoading } = useQuery<{ results?: MathTopic[] } | MathTopic[]>({
    queryKey: ['topics-management', subjectFilter, classFilter, showInactive],
    queryFn: () => examsApi.topics({
      subject: subjectFilter || undefined,
      grade_level: classFilter || undefined,
      include_inactive: showInactive ? 'true' : undefined,
      page_size: 500,
    }).then(r => r.data),
  });
  const allTopics = unwrap<MathTopic>(topicsData);
  const filtered = allTopics.filter(t => !search || t.name.toLowerCase().includes(search.toLowerCase()));

  // Group by subject, then by class within each subject — topics are
  // ordered (and reordered) within a single subject+class bucket, since
  // that's the unit a teacher actually sequences (e.g. Form 1 Mathematics
  // topic order is independent of Form 2 Mathematics topic order).
  const groups = useMemo(() => {
    const bySubject = new Map<number, { subject: string; color: string; byClass: Map<number, MathTopic[]> }>();
    filtered.forEach(t => {
      const subjectKey = t.subject ?? 0;
      if (!bySubject.has(subjectKey)) {
        bySubject.set(subjectKey, {
          subject: t.subject_name ?? 'Unassigned subject',
          color: t.subject_color ?? '#6366f1',
          byClass: new Map(),
        });
      }
      const classKey = t.grade_level ?? UNASSIGNED_CLASS;
      const byClass = bySubject.get(subjectKey)!.byClass;
      if (!byClass.has(classKey)) byClass.set(classKey, []);
      byClass.get(classKey)!.push(t);
    });
    bySubject.forEach(g => g.byClass.forEach(list => list.sort((a, b) => a.order - b.order)));
    return bySubject;
  }, [filtered]);

  const classLabel = (id: number): string => {
    if (id === UNASSIGNED_CLASS) return 'All classes';
    const g = grades.find(x => x.id === id);
    return g ? (g.short_name || g.name) : `Class #${id}`;
  };
  const classOrder = (id: number): number => {
    if (id === UNASSIGNED_CLASS) return -1;
    return grades.find(x => x.id === id)?.order ?? 999;
  };

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['topics-management'] });
    queryClient.invalidateQueries({ queryKey: ['topics'] });
  };

  const deleteMutation = useMutation({
    mutationFn: (id: number) => examsApi.deleteTopic(id),
    onSuccess: () => { toast.success('Topic deactivated'); invalidate(); },
    onError: () => toast.error('Failed to deactivate topic'),
  });
  const restoreMutation = useMutation({
    mutationFn: (id: number) => examsApi.restoreTopic(id),
    onSuccess: () => { toast.success('Topic restored'); invalidate(); },
    onError: () => toast.error('Failed to restore topic'),
  });
  const reorderMutation = useMutation({
    mutationFn: (order: { id: number; order: number }[]) => examsApi.reorderTopics(order),
    onSuccess: () => invalidate(),
    onError: () => { toast.error('Failed to save new order'); invalidate(); },
  });

  const handleReorder = (newList: MathTopic[]) => {
    // Optimistically write the new order straight into the cache so the
    // drag settles without a flicker, then persist it.
    queryClient.setQueryData<{ results?: MathTopic[] } | MathTopic[]>(
      ['topics-management', subjectFilter, classFilter, showInactive],
      (old) => {
        if (!old) return old;
        const ids = new Set(newList.map(t => t.id));
        const rest = unwrap<MathTopic>(old).filter(t => !ids.has(t.id));
        const merged = [...rest, ...newList];
        return Array.isArray(old) ? merged : { ...old, results: merged };
      }
    );
    reorderMutation.mutate(newList.map((t, i) => ({ id: t.id, order: i })));
  };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title flex items-center gap-2"><BookMarked className="text-violet-400" size={22} /> Topics</h1>
          <p className="text-muted mt-0.5">Curriculum topics per subject and class — used for exam breakdowns, daily quizzes, and topic analytics. Drag to reorder.</p>
        </div>
        {isAdmin && (
          <Button onClick={() => setModalTopic('new')} size="sm">
            <Plus size={14} /> New Topic
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
          <input className="input pl-10 w-full" placeholder="Search topics…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className="w-52">
          <Select label="Subject"
            options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
            value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)} />
        </div>
        <div className="w-48">
          <Select label="Class"
            options={[{ value: '', label: 'All classes' }, ...grades.map(g => ({ value: g.id, label: g.short_name || g.name }))]}
            value={classFilter} onChange={e => setClassFilter(e.target.value)} />
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowInactive(v => !v)}
            className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl text-xs font-display font-medium text-secondary hover:text-primary border border-surface hover:border-surface/80 transition-colors"
          >
            {showInactive ? <Eye size={13} /> : <EyeOff size={13} />}
            {showInactive ? 'Showing inactive' : 'Show inactive'}
          </button>
        )}
      </div>

      {isLoading ? <LoadingPage /> : groups.size === 0 ? (
        <EmptyState icon={<BookMarked size={36} />} title="No topics found" message="Try a different search or filter, or create the first topic." />
      ) : (
        <div className="flex flex-col gap-5">
          {Array.from(groups.entries()).map(([subjectId, group]) => {
            const classEntries = Array.from(group.byClass.entries())
              .sort(([a], [b]) => classOrder(a) - classOrder(b));
            const total = classEntries.reduce((n, [, list]) => n + list.length, 0);
            return (
              <div key={subjectId} className="card p-4">
                <div className="flex items-center gap-2 mb-4">
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: group.color }} />
                  <h2 className="font-display font-semibold text-primary text-sm">{group.subject}</h2>
                  <span className="text-xs text-secondary">({total})</span>
                </div>
                <div className="flex flex-col gap-4">
                  {classEntries.map(([classId, topics]) => (
                    <div key={classId}>
                      <div className="flex items-center gap-1.5 mb-2 pl-1">
                        <GraduationCap size={12} className="text-secondary" />
                        <span className="text-[11px] font-display font-medium text-secondary uppercase tracking-wider">
                          {classLabel(classId)}
                        </span>
                        <span className="text-[11px] text-secondary/60">({topics.length})</span>
                      </div>
                      <Reorder.Group
                        as="div"
                        axis="y"
                        values={topics}
                        onReorder={isAdmin ? handleReorder : () => {}}
                        className="flex flex-col gap-1.5"
                      >
                        <AnimatePresence initial={false}>
                          {topics.map(topic => (
                            <Reorder.Item
                              key={topic.id}
                              value={topic}
                              drag={isAdmin}
                              initial={{ opacity: 0, y: -6 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, height: 0 }}
                              whileDrag={{ scale: 1.02, boxShadow: '0 8px 24px rgba(0,0,0,0.35)', zIndex: 10 }}
                              transition={{ duration: 0.18 }}
                              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl relative ${topic.is_active ? 'bg-surface-900' : 'bg-surface-900/40 opacity-60'}`}
                            >
                              {isAdmin && (
                                <span className="text-secondary/50 hover:text-secondary cursor-grab active:cursor-grabbing flex-shrink-0" title="Drag to reorder">
                                  <GripVertical size={14} />
                                </span>
                              )}
                              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: topic.color }} />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-primary truncate">{topic.name}</p>
                                {topic.description && <p className="text-xs text-secondary truncate">{topic.description}</p>}
                              </div>
                              {!topic.is_active && <span className="badge text-[10px] flex-shrink-0">Inactive</span>}
                              {isAdmin && (
                                <div className="flex items-center gap-1 flex-shrink-0">
                                  {topic.is_active ? (
                                    <>
                                      <button onClick={() => setModalTopic(topic)} className="p-1.5 rounded-lg text-secondary hover:text-azure-400 hover:bg-azure-500/10 transition-colors" title="Edit">
                                        <Edit2 size={13} />
                                      </button>
                                      <button
                                        onClick={() => setConfirmDelete(topic)}
                                        className="p-1.5 rounded-lg text-secondary hover:text-rose-400 hover:bg-rose-500/10 transition-colors" title="Deactivate"
                                      >
                                        <Trash2 size={13} />
                                      </button>
                                    </>
                                  ) : (
                                    <button onClick={() => restoreMutation.mutate(topic.id)} className="p-1.5 rounded-lg text-secondary hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors" title="Restore">
                                      <RotateCcw size={13} />
                                    </button>
                                  )}
                                </div>
                              )}
                            </Reorder.Item>
                          ))}
                        </AnimatePresence>
                      </Reorder.Group>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modalTopic && (
        <TopicFormModal
          topic={modalTopic === 'new' ? null : modalTopic}
          subjects={subjects}
          grades={grades}
          onClose={() => setModalTopic(null)}
          onSaved={() => { setModalTopic(null); invalidate(); }}
        />
      )}

      {confirmDelete && (
        <Modal
          open onClose={() => setConfirmDelete(null)} title="Deactivate topic" size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmDelete(null)}>Cancel</Button>
              <Button
                onClick={() => { deleteMutation.mutate(confirmDelete.id); setConfirmDelete(null); }}
                loading={deleteMutation.isPending}
              >
                Deactivate
              </Button>
            </>
          }
        >
          <p className="text-sm text-secondary">
            Deactivate <span className="text-primary font-medium">"{confirmDelete.name}"</span>? It stays in historical
            records but won't be selectable for new exams or quizzes. You can restore it anytime.
          </p>
        </Modal>
      )}
    </div>
  );
}

function TopicFormModal({ topic, subjects, grades, onClose, onSaved }: {
  topic: MathTopic | null; subjects: Subject[]; grades: GradeLevel[]; onClose: () => void; onSaved: () => void;
}) {
  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<TopicFormData>({
    defaultValues: topic
      ? {
          subject: topic.subject ?? undefined,
          grade_level: topic.grade_level ?? '',
          name: topic.name,
          description: topic.description,
          color: topic.color,
        }
      : { grade_level: '', color: DEFAULT_COLORS[0] },
  });
  const selectedColor = watch('color');

  const mutation = useMutation({
    mutationFn: (data: TopicFormData) => {
      const payload = { ...data, grade_level: data.grade_level === '' ? null : data.grade_level };
      return topic ? examsApi.updateTopic(topic.id, payload) : examsApi.createTopic(payload);
    },
    onSuccess: () => { toast.success(topic ? 'Topic updated' : 'Topic created'); onSaved(); },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[] | string> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to save topic');
    },
  });

  return (
    <Modal open onClose={onClose} title={topic ? 'Edit Topic' : 'New Topic'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit(d => mutation.mutate(d))} loading={mutation.isPending}>Save</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-secondary uppercase tracking-wider">Subject *</label>
            <select
              {...register('subject', { required: 'Subject is required', valueAsNumber: true })}
              className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
            >
              <option value="">Select subject…</option>
              {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            {errors.subject && <p className="text-xs text-red-400 mt-1">{errors.subject.message}</p>}
          </div>
          <div>
            <label className="text-xs font-medium text-secondary uppercase tracking-wider">Class</label>
            <select
              {...register('grade_level')}
              className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
            >
              <option value="">All classes</option>
              {grades.map(g => <option key={g.id} value={g.id}>{g.short_name || g.name}</option>)}
            </select>
          </div>
        </div>
        <Input label="Topic Name" placeholder="e.g. Fractions" error={errors.name?.message}
          {...register('name', { required: 'Name is required' })} />
        <div className="flex flex-col gap-1.5">
          <label className="label">Description (optional)</label>
          <textarea className="input resize-none" rows={2} placeholder="What this topic covers…" {...register('description')} />
        </div>
        <div>
          <label className="label mb-1.5 block">Color</label>
          <div className="flex gap-2 flex-wrap">
            {DEFAULT_COLORS.map(c => (
              <button
                key={c} type="button" onClick={() => setValue('color', c)}
                className={`w-7 h-7 rounded-full transition-transform ${selectedColor === c ? 'scale-110 ring-2 ring-offset-2 ring-offset-surface-800 ring-white' : ''}`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}
