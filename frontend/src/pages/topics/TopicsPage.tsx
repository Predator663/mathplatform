import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import {
  BookMarked, Plus, Search, Edit2, Trash2, RotateCcw, ArrowUp, ArrowDown,
  Eye, EyeOff, GripVertical,
} from 'lucide-react';
import { examsApi, subjectsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Input, Select, Modal } from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import type { MathTopic, Subject, PaginatedResponse } from '../../types';

interface TopicFormData {
  subject: number; name: string; description: string; color: string;
}

const DEFAULT_COLORS = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4', '#ec4899'];

export default function TopicsPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin';
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [modalTopic, setModalTopic] = useState<MathTopic | null | 'new'>(null);

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
  });
  const subjects: Subject[] = Array.isArray(subjectsData) ? subjectsData : subjectsData?.results ?? [];

  const { data: topicsData, isLoading } = useQuery<{ results?: MathTopic[] } | MathTopic[]>({
    queryKey: ['topics-management', subjectFilter, showInactive],
    queryFn: () => examsApi.topics({
      subject: subjectFilter || undefined,
      include_inactive: showInactive ? 'true' : undefined,
      page_size: 300,
    }).then(r => r.data),
  });
  const allTopics: MathTopic[] = Array.isArray(topicsData) ? topicsData : topicsData?.results ?? [];
  const filtered = allTopics.filter(t => !search || t.name.toLowerCase().includes(search.toLowerCase()));

  // Group by subject, ordered within each group by `order`.
  const grouped = new Map<number, { subject: string; color: string; topics: MathTopic[] }>();
  filtered.forEach(t => {
    const key = t.subject ?? 0;
    if (!grouped.has(key)) grouped.set(key, { subject: t.subject_name ?? 'Unassigned', color: t.subject_color ?? '#6366f1', topics: [] });
    grouped.get(key)!.topics.push(t);
  });
  grouped.forEach(g => g.topics.sort((a, b) => a.order - b.order));

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
    onError: () => toast.error('Failed to reorder topics'),
  });

  const moveTopic = (group: MathTopic[], index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= group.length) return;
    const a = group[index], b = group[targetIndex];
    reorderMutation.mutate([{ id: a.id, order: b.order }, { id: b.id, order: a.order }]);
  };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title flex items-center gap-2"><BookMarked className="text-violet-400" size={22} /> Topics</h1>
          <p className="text-muted mt-0.5">Curriculum topics used for exam breakdowns, daily quizzes, and topic analytics.</p>
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
        <div className="w-56">
          <Select label="Subject"
            options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
            value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)} />
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

      {isLoading ? <LoadingPage /> : grouped.size === 0 ? (
        <EmptyState icon={<BookMarked size={36} />} title="No topics found" message="Try a different search or filter, or create the first topic." />
      ) : (
        <div className="flex flex-col gap-5">
          {Array.from(grouped.entries()).map(([subjectId, group]) => (
            <div key={subjectId} className="card p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: group.color }} />
                <h2 className="font-display font-semibold text-primary text-sm">{group.subject}</h2>
                <span className="text-xs text-secondary">({group.topics.length})</span>
              </div>
              <div className="flex flex-col gap-1.5">
                {group.topics.map((topic, i) => (
                  <div
                    key={topic.id}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors ${topic.is_active ? 'bg-surface-900' : 'bg-surface-900/40 opacity-60'}`}
                  >
                    {isAdmin && (
                      <div className="flex flex-col flex-shrink-0">
                        <button disabled={i === 0} onClick={() => moveTopic(group.topics, i, -1)} className="text-secondary hover:text-primary disabled:opacity-20 transition-colors">
                          <ArrowUp size={12} />
                        </button>
                        <button disabled={i === group.topics.length - 1} onClick={() => moveTopic(group.topics, i, 1)} className="text-secondary hover:text-primary disabled:opacity-20 transition-colors">
                          <ArrowDown size={12} />
                        </button>
                      </div>
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
                              onClick={() => { if (confirm(`Deactivate "${topic.name}"? It stays in historical records but won't be selectable for new exams/quizzes.`)) deleteMutation.mutate(topic.id); }}
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
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {modalTopic && (
        <TopicFormModal
          topic={modalTopic === 'new' ? null : modalTopic}
          subjects={subjects}
          onClose={() => setModalTopic(null)}
          onSaved={() => { setModalTopic(null); invalidate(); }}
        />
      )}
    </div>
  );
}

function TopicFormModal({ topic, subjects, onClose, onSaved }: {
  topic: MathTopic | null; subjects: Subject[]; onClose: () => void; onSaved: () => void;
}) {
  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<TopicFormData>({
    defaultValues: topic
      ? { subject: topic.subject ?? undefined, name: topic.name, description: topic.description, color: topic.color }
      : { color: DEFAULT_COLORS[0] },
  });
  const selectedColor = watch('color');

  const mutation = useMutation({
    mutationFn: (data: TopicFormData) =>
      topic ? examsApi.updateTopic(topic.id, data) : examsApi.createTopic(data),
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
