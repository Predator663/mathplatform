import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Edit2, ToggleLeft, ToggleRight, BookMarked, Users, BookOpen } from 'lucide-react';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { subjectsApi } from '../../api';
import { useSubjectStore } from '../../store/subject';
import type { Subject, PaginatedResponse } from '../../types';

interface SubjectForm {
  name: string; code: string; color: string; icon: string; is_active: boolean;
}

export default function SubjectsPage() {
  const qc = useQueryClient();
  const { setSubjects } = useSubjectStore();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Subject | null>(null);

  const { data, isLoading } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects'],
    queryFn: () => subjectsApi.list().then(r => r.data),
  });

  const subjects: Subject[] = Array.isArray(data)
    ? data
    : (data as PaginatedResponse<Subject>)?.results ?? [];

  const { register, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<SubjectForm>({
    defaultValues: { name: '', code: '', color: '#6366f1', icon: 'book-open', is_active: true },
  });
  const currentColor = watch('color');
  const currentIcon = watch('icon');

  const createMutation = useMutation({
    mutationFn: (d: SubjectForm) => subjectsApi.create(d),
    onSuccess: () => {
      toast.success('Subject created');
      qc.invalidateQueries({ queryKey: ['subjects'] });
      closeModal();
    },
    onError: () => toast.error('Failed to create subject'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<SubjectForm> }) =>
      subjectsApi.update(id, data),
    onSuccess: () => {
      toast.success('Subject updated');
      qc.invalidateQueries({ queryKey: ['subjects'] });
      closeModal();
    },
    onError: () => toast.error('Failed to update subject'),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      subjectsApi.update(id, { is_active }),
    onSuccess: (_, vars) => {
      toast.success(vars.is_active ? 'Subject activated' : 'Subject deactivated');
      qc.invalidateQueries({ queryKey: ['subjects'] });
    },
    onError: () => toast.error('Failed to update subject'),
  });

  function openCreate() {
    setEditing(null);
    reset({ name: '', code: '', color: '#6366f1', icon: 'book-open', is_active: true });
    setModalOpen(true);
  }

  function openEdit(s: Subject) {
    setEditing(s);
    reset({ name: s.name, code: s.code, color: s.color, icon: s.icon, is_active: s.is_active });
    setModalOpen(true);
  }

  function closeModal() { setModalOpen(false); setEditing(null); }

  function onSubmit(d: SubjectForm) {
    if (editing) updateMutation.mutate({ id: editing.id, data: d });
    else createMutation.mutate(d);
  }

  const ICON_PRESETS = [
    'book-open', 'calculator', 'globe', 'zap', 'flask-conical',
    'leaf', 'languages', 'landmark', 'scale', 'atom',
  ];

  const COLOR_PRESETS = [
    '#6366f1', '#0ea5e9', '#f59e0b', '#10b981', '#84cc16',
    '#ec4899', '#8b5cf6', '#f97316', '#14b8a6', '#ef4444',
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-primary">Subjects</h1>
          <p className="text-sm text-secondary mt-0.5">
            Manage school subjects. Teachers are assigned to subjects via classrooms.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-azure-500 hover:bg-azure-600 text-white text-sm font-medium rounded-xl transition-colors"
        >
          <Plus size={16} />
          Add Subject
        </button>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-32 bg-surface-700 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : subjects.length === 0 ? (
        <div className="text-center py-20 text-secondary">
          <BookMarked size={40} className="mx-auto mb-3 opacity-30" />
          <p className="font-medium">No subjects yet</p>
          <p className="text-sm mt-1">Add your first subject to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {subjects.map(s => (
            <div
              key={s.id}
              className={`relative bg-surface-800 border rounded-2xl p-5 flex flex-col gap-3 transition-all ${
                s.is_active ? 'border-surface' : 'border-surface opacity-50'
              }`}
            >
              {/* Color bar */}
              <div
                className="absolute top-0 left-0 right-0 h-1 rounded-t-2xl"
                style={{ backgroundColor: s.color }}
              />
              <div className="flex items-start justify-between mt-1">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-lg font-bold"
                    style={{ backgroundColor: s.color + '25', color: s.color }}
                  >
                    {s.code.slice(0, 2)}
                  </div>
                  <div>
                    <p className="font-semibold text-primary text-sm">{s.name}</p>
                    <p className="text-xs text-secondary">{s.code}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => openEdit(s)}
                    className="p-1.5 text-secondary hover:text-primary hover:bg-surface-700 rounded-lg transition-colors"
                  >
                    <Edit2 size={13} />
                  </button>
                  <button
                    onClick={() => toggleMutation.mutate({ id: s.id, is_active: !s.is_active })}
                    className="p-1.5 text-secondary hover:text-primary hover:bg-surface-700 rounded-lg transition-colors"
                    title={s.is_active ? 'Deactivate' : 'Activate'}
                  >
                    {s.is_active ? <ToggleRight size={15} className="text-emerald-400" /> : <ToggleLeft size={15} />}
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-4 text-xs text-secondary">
                <span className="flex items-center gap-1">
                  <Users size={11} />
                  {s.teacher_count ?? 0} teachers
                </span>
                <span className="flex items-center gap-1">
                  <BookOpen size={11} />
                  {s.exam_count ?? 0} exams
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-800 border border-surface rounded-2xl w-full max-w-md shadow-2xl">
            <div className="px-6 py-4 border-b border-surface">
              <h2 className="font-display font-bold text-lg text-primary">
                {editing ? 'Edit Subject' : 'Add Subject'}
              </h2>
            </div>
            <form onSubmit={handleSubmit(onSubmit)} className="px-6 py-5 flex flex-col gap-4">
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider">Name *</label>
                <input
                  {...register('name', { required: 'Name is required' })}
                  className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                  placeholder="e.g. Mathematics"
                />
                {errors.name && <p className="text-xs text-red-400 mt-1">{errors.name.message}</p>}
              </div>
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider">Code *</label>
                <input
                  {...register('code', { required: 'Code is required', maxLength: { value: 10, message: 'Max 10 characters' } })}
                  className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500 uppercase"
                  placeholder="e.g. MATH"
                />
                {errors.code && <p className="text-xs text-red-400 mt-1">{errors.code.message}</p>}
              </div>
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider mb-2 block">Color</label>
                <div className="flex items-center gap-2 flex-wrap">
                  {COLOR_PRESETS.map(c => {
                    return (
                      <button
                        key={c}
                        type="button"
                        onClick={() => setValue('color', c, { shouldDirty: true })}
                        className={`w-7 h-7 rounded-lg border-2 transition-transform hover:scale-110 ${
                          currentColor === c ? 'ring-2 ring-offset-2 ring-azure-400 ring-offset-surface-800' : ''
                        }`}
                        style={{ backgroundColor: c, borderColor: c }}
                      />
                    );
                  })}
                  <input
                    type="color"
                    {...register('color')}
                    className="w-7 h-7 rounded-lg border border-surface cursor-pointer bg-transparent"
                    title="Custom color"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider mb-2 block">Icon (Lucide name)</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {ICON_PRESETS.map(ic => (
                    <button
                      key={ic}
                      type="button"
                      onClick={() => setValue('icon', ic, { shouldDirty: true })}
                      className={`px-2 py-1 text-xs rounded-lg transition-colors ${
                        currentIcon === ic
                          ? 'bg-azure-500/20 text-azure-400 border border-azure-500/40'
                          : 'bg-surface-700 hover:bg-surface-600 text-secondary hover:text-primary'
                      }`}
                    >
                      {ic}
                    </button>
                  ))}
                </div>
                <input
                  {...register('icon')}
                  className="w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                  placeholder="e.g. calculator"
                />
              </div>
              <div className="flex items-center gap-3">
                <input type="checkbox" id="is_active" {...register('is_active')} className="w-4 h-4 accent-azure-500" />
                <label htmlFor="is_active" className="text-sm text-primary">Active</label>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 px-4 py-2 text-sm font-medium text-secondary hover:text-primary border border-surface rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="flex-1 px-4 py-2 text-sm font-medium bg-azure-500 hover:bg-azure-600 text-white rounded-xl transition-colors disabled:opacity-50"
                >
                  {(createMutation.isPending || updateMutation.isPending) ? 'Saving…' : editing ? 'Save Changes' : 'Create Subject'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
