import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { studentsApi } from '../../api';
import { Button, Input, Select } from '../../components/ui';
import type { Classroom, PaginatedResponse } from '../../types';

interface CreateStudentForm {
  first_name: string;
  last_name: string;
  email: string;
  student_id: string;
  classroom: string;
  date_of_birth: string;
  notes: string;
}

export default function CreateStudentPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData
    : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { register, handleSubmit, formState: { errors } } = useForm<CreateStudentForm>();

  const mutation = useMutation({
    mutationFn: (data: Partial<CreateStudentForm>) => studentsApi.createStudent(data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['students'] });
      const pw = res.data.generated_password;
      if (pw) {
        toast.success(`Student created! Generated password: ${pw}`, { duration: 8000 });
      } else {
        toast.success('Student created!');
      }
      navigate(`/students/${res.data.id}`);
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: Record<string, string[]> } };
      const msgs = error?.response?.data;
      if (msgs) {
        Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      } else {
        toast.error('Failed to create student');
      }
    },
  });

  const onSubmit = (data: CreateStudentForm) => {
    mutation.mutate({
      ...data,
      classroom: data.classroom || undefined,
      date_of_birth: data.date_of_birth || undefined,
    });
  };

  return (
    <div className="flex flex-col gap-6 max-w-2xl page-enter">
      <div>
        <button onClick={() => navigate('/students')} className="text-secondary hover:text-primary text-sm transition-colors mb-2">
          ← Back to Students
        </button>
        <h1 className="page-title">Add Student</h1>
        <p className="text-muted mt-1">A login password will be auto-generated and shown once.</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
        <div className="card p-6 flex flex-col gap-4">
          <h2 className="section-title">Personal Details</h2>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="First Name"
              placeholder="Alice"
              error={errors.first_name?.message}
              {...register('first_name', { required: 'First name is required' })}
            />
            <Input
              label="Last Name"
              placeholder="Adeyemi"
              error={errors.last_name?.message}
              {...register('last_name', { required: 'Last name is required' })}
            />
          </div>
          <Input
            label="Email Address"
            type="email"
            placeholder="alice.adeyemi@school.edu"
            error={errors.email?.message}
            {...register('email', {
              required: 'Email is required',
              pattern: { value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Invalid email' },
            })}
          />
          <Input
            label="Date of Birth"
            type="date"
            {...register('date_of_birth')}
          />
        </div>

        <div className="card p-6 flex flex-col gap-4">
          <h2 className="section-title">Enrolment</h2>
          <Input
            label="Student ID"
            placeholder="STU1001"
            error={errors.student_id?.message}
            {...register('student_id', { required: 'Student ID is required' })}
          />
          <Select
            label="Classroom (optional)"
            options={[
              { value: '', label: 'Assign later' },
              ...classrooms.map(c => ({
                value: c.id,
                label: `${c.name} — ${c.grade_level_name} (${c.academic_year})`,
              })),
            ]}
            {...register('classroom')}
          />
          <div className="flex flex-col gap-1.5">
            <label className="label">Notes (optional)</label>
            <textarea
              className="input resize-none"
              rows={3}
              placeholder="Any additional notes about the student..."
              {...register('notes')}
            />
          </div>
        </div>

        <div className="flex gap-3 justify-end">
          <Button type="button" variant="secondary" onClick={() => navigate('/students')}>
            Cancel
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            Create Student
          </Button>
        </div>
      </form>
    </div>
  );
}
