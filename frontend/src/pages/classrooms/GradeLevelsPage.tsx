import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Edit2, Trash2, Layers } from 'lucide-react';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { studentsApi } from '../../api';
import { EDUCATION_LEVEL_LABELS } from '../../utils';
import type { GradeLevel, EducationLevel, PaginatedResponse } from '../../types';

interface GradeLevelForm {
  name: string; short_name: string; education_level: EducationLevel;
  order: number; necta_exam: string; math_subject: string;
}

const EDUCATION_LEVEL_OPTIONS: EducationLevel[] = ['pre_primary', 'primary', 'o_level', 'a_level', 'technical'];

export default function GradeLevelsPage() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<GradeLevel | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<GradeLevel | null>(null);

  const { data, isLoading } = useQuery<PaginatedResponse<GradeLevel> | GradeLevel[]>({
    queryKey: ['grade-levels'],
    queryFn: () => studentsApi.gradeLevels().then(r => r.data),
  });

  const grades: GradeLevel[] = Array.isArray(data)
    ? data
    : (data as PaginatedResponse<GradeLevel>)?.results ?? [];

  const { register, handleSubmit, reset, formState: { errors } } = useForm<GradeLevelForm>({
    defaultValues: { name: '', short_name: '', education_level: 'o_level', order: 0, necta_exam: '', math_subject: 'Mathematics' },
  });

  const createMutation = useMutation({
    mutationFn: (d: GradeLevelForm) => studentsApi.createGradeLevel(d),
    onSuccess: () => {
      toast.success('Grade level created');
      qc.invalidateQueries({ queryKey: ['grade-levels'] });
      closeModal();
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[]> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to create grade level');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<GradeLevelForm> }) =>
      studentsApi.updateGradeLevel(id, data),
    onSuccess: () => {
      toast.success('Grade level updated');
      qc.invalidateQueries({ queryKey: ['grade-levels'] });
      closeModal();
    },
    onError: () => toast.error('Failed to update grade level'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => studentsApi.deleteGradeLevel(id),
    onSuccess: () => {
      toast.success('Grade level deleted');
      qc.invalidateQueries({ queryKey: ['grade-levels'] });
      setConfirmDelete(null);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? 'Failed to delete — it may still have classrooms attached');
      setConfirmDelete(null);
    },
  });

  function openCreate() {
    setEditing(null);
    reset({ name: '', short_name: '', education_level: 'o_level', order: (grades.length ? Math.max(...grades.map(g => g.order)) + 1 : 0), necta_exam: '', math_subject: 'Mathematics' });
    setModalOpen(true);
  }

  function openEdit(g: GradeLevel) {
    setEditing(g);
    reset({
      name: g.name, short_name: g.short_name, education_level: g.education_level,
      order: g.order, necta_exam: g.necta_exam, math_subject: g.math_subject,
    });
    setModalOpen(true);
  }

  function closeModal() { setModalOpen(false); setEditing(null); }

  function onSubmit(d: GradeLevelForm) {
    if (editing) updateMutation.mutate({ id: editing.id, data: d });
    else createMutation.mutate(d);
  }

  const gradesByLevel = grades.reduce((acc, g) => {
    if (!acc[g.education_level]) acc[g.education_level] = [];
    acc[g.education_level].push(g);
    return acc;
  }, {} as Record<string, GradeLevel[]>);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-primary">Grade Levels</h1>
          <p className="text-sm text-secondary mt-0.5">
            Manage the curriculum grade levels (Standard 1–7, Form 1–6, etc.) available when creating classrooms.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-azure-500 hover:bg-azure-600 text-white text-sm font-medium rounded-xl transition-colors"
        >
          <Plus size={16} />
          Add Grade Level
        </button>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 bg-surface-700 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : grades.length === 0 ? (
        <div className="text-center py-20 text-secondary">
          <Layers size={40} className="mx-auto mb-3 opacity-30" />
          <p className="font-medium">No grade levels yet</p>
          <p className="text-sm mt-1">Add your first grade level so classrooms can be created against it.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {EDUCATION_LEVEL_OPTIONS.filter(l => gradesByLevel[l]?.length).map(level => (
            <div key={level}>
              <h2 className="text-xs font-display font-semibold uppercase tracking-wider text-secondary mb-2">
                {EDUCATION_LEVEL_LABELS[level]}
              </h2>
              <div className="flex flex-col gap-2">
                {gradesByLevel[level].map(g => (
                  <div key={g.id} className="flex items-center justify-between bg-surface-800 border border-surface rounded-xl px-4 py-3">
                    <div>
                      <p className="font-semibold text-primary text-sm">
                        {g.name}{g.short_name ? ` (${g.short_name})` : ''}
                      </p>
                      <p className="text-xs text-secondary mt-0.5">
                        {g.necta_exam ? `${g.necta_exam} · ` : ''}{g.math_subject}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => openEdit(g)}
                        className="p-1.5 text-secondary hover:text-primary hover:bg-surface-700 rounded-lg transition-colors"
                        title="Edit"
                      >
                        <Edit2 size={13} />
                      </button>
                      <button
                        onClick={() => setConfirmDelete(g)}
                        className="p-1.5 text-secondary hover:text-rose-400 hover:bg-surface-700 rounded-lg transition-colors"
                        title="Delete"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-800 border border-surface rounded-2xl w-full max-w-md shadow-2xl">
            <div className="px-6 py-4 border-b border-surface">
              <h2 className="font-display font-bold text-lg text-primary">
                {editing ? 'Edit Grade Level' : 'Add Grade Level'}
              </h2>
            </div>
            <form onSubmit={handleSubmit(onSubmit)} className="px-6 py-5 flex flex-col gap-4">
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider">Name *</label>
                <input
                  {...register('name', { required: 'Name is required' })}
                  className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                  placeholder="e.g. Form 4"
                />
                {errors.name && <p className="text-xs text-red-400 mt-1">{errors.name.message}</p>}
              </div>
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider">Short Name</label>
                <input
                  {...register('short_name')}
                  className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                  placeholder="e.g. Form 4"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider">Education Level *</label>
                <select
                  {...register('education_level', { required: true })}
                  className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                >
                  {EDUCATION_LEVEL_OPTIONS.map(l => (
                    <option key={l} value={l}>{EDUCATION_LEVEL_LABELS[l]}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-secondary uppercase tracking-wider">Sort Order</label>
                  <input
                    type="number"
                    {...register('order', { valueAsNumber: true })}
                    className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-secondary uppercase tracking-wider">NECTA Exam</label>
                  <input
                    {...register('necta_exam')}
                    className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                    placeholder="e.g. CSEE"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider">Math Subject</label>
                <input
                  {...register('math_subject')}
                  className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                  placeholder="e.g. Mathematics"
                />
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
                  {(createMutation.isPending || updateMutation.isPending) ? 'Saving…' : editing ? 'Save Changes' : 'Create Grade Level'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-800 border border-surface rounded-2xl w-full max-w-sm shadow-2xl p-6">
            <h2 className="font-display font-bold text-lg text-primary mb-2">Delete "{confirmDelete.name}"?</h2>
            <p className="text-sm text-secondary mb-5">
              Any classrooms using this grade level will also be deleted, along with their student links. This cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmDelete(null)}
                className="flex-1 px-4 py-2 text-sm font-medium text-secondary hover:text-primary border border-surface rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(confirmDelete.id)}
                disabled={deleteMutation.isPending}
                className="flex-1 px-4 py-2 text-sm font-medium bg-rose-500 hover:bg-rose-600 text-white rounded-xl transition-colors disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
