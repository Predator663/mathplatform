import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Plus } from 'lucide-react';
import toast from 'react-hot-toast';
import { studentsApi } from '../../api';
import { Button, Input, Select } from '../../components/ui';
import { PermissionGate } from '../../components/ui/PermissionGate';
import { EDUCATION_LEVEL_LABELS } from '../../utils';
import type { GradeLevel, PaginatedResponse } from '../../types';

interface FormData {
  name: string; grade_level: string; stream: string;
  academic_year: string;
}

export default function CreateClassroomPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: gradesData } = useQuery<GradeLevel[]>({
    queryKey: ['grade-levels'],
    queryFn: () => studentsApi.gradeLevels().then(r =>
      Array.isArray(r.data) ? r.data : (r.data as PaginatedResponse<GradeLevel>).results ?? []
    ),
  });
  const grades: GradeLevel[] = gradesData ?? [];

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    defaultValues: { academic_year: '2024', stream: 'general' },
  });

  const selectedGradeId = watch('grade_level');
  const selectedGrade = grades.find(g => String(g.id) === selectedGradeId);

  const mutation = useMutation({
    mutationFn: (data: object) => studentsApi.createClassroom(data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['classrooms'] });
      toast.success('Classroom created! Now assign a teacher below.');
      navigate(`/classrooms/${res.data.id}`);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[]> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to create classroom');
    },
  });

  const onSubmit = (data: FormData) => {
    mutation.mutate({
      name: data.name,
      grade_level: data.grade_level ? Number(data.grade_level) : undefined,
      stream: data.stream || 'general',
      academic_year: data.academic_year,
    });
  };

  // Group grades by education level
  const gradesByLevel = grades.reduce((acc, g) => {
    if (!acc[g.education_level]) acc[g.education_level] = [];
    acc[g.education_level].push(g);
    return acc;
  }, {} as Record<string, GradeLevel[]>);

  const levelOrder: string[] = ['pre_primary', 'primary', 'o_level', 'a_level', 'technical'];

  return (
    <PermissionGate resource="classrooms" action="add" backTo="/classrooms" backLabel="Back to Classrooms">
    <div className="flex flex-col gap-4 md:gap-6 max-w-lg">
      <div>
        <button onClick={() => navigate('/classrooms')} className="text-secondary hover:text-primary text-sm transition-colors mb-2">
          ← Back to Classrooms
        </button>
        <h1 className="page-title">Create Classroom</h1>
        <p className="text-muted mt-1 text-sm">Tanzania curriculum — Pre-Primary through A-Level</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 md:gap-5">
        <div className="card p-4 md:p-6 flex flex-col gap-4">
          <Input label="Classroom Name" placeholder="e.g. Form 2A, Standard 7B, Form 4 Science"
            error={errors.name?.message}
            {...register('name', { required: 'Classroom name is required' })} />

          {/* Grade level grouped by education level */}
          <div className="flex flex-col gap-1.5">
            <label className="label">Grade Level</label>
            {grades.length === 0 ? (
              <p className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
                No grade levels found. Run: <code className="font-mono">python manage.py seed_demo</code>
              </p>
            ) : (
              <select className="input" {...register('grade_level', { required: 'Grade level is required' })}>
                <option value="">Select grade level…</option>
                {levelOrder.filter(l => gradesByLevel[l]?.length).map(level => (
                  <optgroup key={level} label={EDUCATION_LEVEL_LABELS[level as keyof typeof EDUCATION_LEVEL_LABELS]}>
                    {gradesByLevel[level].map(g => (
                      <option key={g.id} value={g.id}>
                        {g.name}{g.necta_exam ? ` (${g.necta_exam})` : ''}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            )}
          </div>

          {/* Stream — only for O-Level and A-Level */}
          {selectedGrade && (selectedGrade.education_level === 'o_level' || selectedGrade.education_level === 'a_level') && (
            <Select label="Stream / Combination" options={[
              { value: 'general',   label: 'General' },
              { value: 'science',   label: 'Science (PCM / PCB)' },
              { value: 'arts',      label: 'Arts / Humanities' },
              { value: 'commerce',  label: 'Commerce' },
              { value: 'technical', label: 'Technical' },
            ]} {...register('stream')} />
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="Academic Year" placeholder="2024"
              error={errors.academic_year?.message}
              {...register('academic_year', { required: 'Year is required' })} />
          </div>
          <p className="text-xs text-secondary bg-surface-900 border border-surface rounded-xl px-3 py-2.5">
            Teacher and subject assignment happens after the classroom is created —
            you'll land on the classroom page to assign teachers there.
          </p>

          {/* Preview of what NECTA exam applies */}
          {selectedGrade?.necta_exam && (
            <div className="bg-azure-500/10 border border-azure-500/20 rounded-xl px-3 py-2.5">
              <p className="text-xs text-azure-400">
                <span className="font-semibold">NECTA Exam:</span> {selectedGrade.necta_exam} applies to this grade level.
              </p>
              <p className="text-xs text-secondary mt-0.5">Math Subject: {selectedGrade.math_subject}</p>
            </div>
          )}
        </div>

        <div className="flex gap-3 justify-end">
          <Button type="button" variant="secondary" onClick={() => navigate('/classrooms')}>Cancel</Button>
          <Button type="submit" loading={mutation.isPending}>
            <Plus size={14} /> Create Classroom
          </Button>
        </div>
      </form>
    </div>
    </PermissionGate>
  );
}
