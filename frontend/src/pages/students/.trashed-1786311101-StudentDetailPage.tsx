import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { BarChart3, Edit2, Save, X, Trash2, ToggleLeft, ToggleRight } from 'lucide-react';
import { studentsApi } from '../../api';
import { useCanManage } from '../../hooks/useCanManage';
import { LoadingPage, Button, Input, Select } from '../../components/ui';
import { formatDate } from '../../utils';
import type { StudentProfile, Classroom, PaginatedResponse } from '../../types';
import toast from 'react-hot-toast';
import { useForm } from 'react-hook-form';

interface EditForm {
  first_name: string; last_name: string; student_id: string;
  classroom: string; date_of_birth: string; notes: string;
  index_number: string; parent_name: string; parent_phone: string;
  district: string; region: string; is_active: boolean;
}

export default function StudentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const canEdit = useCanManage('students', 'edit');
  const canDelete = useCanManage('students', 'delete');

  const { data: student, isLoading } = useQuery<StudentProfile>({
    queryKey: ['student', id],
    queryFn: () => studentsApi.student(Number(id)).then(r => r.data),
  });

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData
    : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { register, handleSubmit, reset, formState: { errors } } = useForm<EditForm>();

  const updateMutation = useMutation({
    mutationFn: (data: Partial<EditForm>) =>
      studentsApi.updateStudent(Number(id), data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['student', id] });
      queryClient.invalidateQueries({ queryKey: ['students'] });
      setEditing(false);
      toast.success('Student updated');
    },
    onError: () => toast.error('Failed to update student'),
  });

  const toggleActiveMut = useMutation({
    mutationFn: (is_active: boolean) => studentsApi.updateStudent(Number(id), { is_active }),
    onSuccess: (_, active) => {
      queryClient.invalidateQueries({ queryKey: ['student', id] });
      queryClient.invalidateQueries({ queryKey: ['students'] });
      toast.success(active ? 'Student reactivated' : 'Student deactivated');
    },
    onError: () => toast.error('Failed to update status'),
  });

  const deleteMut = useMutation({
    mutationFn: () => studentsApi.deleteStudent(Number(id)),
    onSuccess: () => { navigate('/students'); toast.success('Student deleted'); },
    onError: () => toast.error('Failed to delete student'),
  });

  const startEdit = () => {
    if (!student) return;
    reset({
      first_name: student.first_name, last_name: student.last_name,
      student_id: student.student_id,
      classroom: student.classroom ? String(student.classroom) : '',
      date_of_birth: student.date_of_birth ?? '',
      notes: student.notes,
      index_number: student.index_number ?? '',
      parent_name: student.parent_name ?? '',
      parent_phone: student.parent_phone ?? '',
      district: student.district ?? '',
      region: student.region ?? '',
      is_active: student.is_active,
    });
    setEditing(true);
  };

  const onSubmit = (data: EditForm) => {
    updateMutation.mutate({
      ...data,
      classroom: data.classroom ? data.classroom : undefined,
    });
  };

  if (isLoading) return <LoadingPage />;
  if (!student) return <div className="text-muted">Student not found.</div>;

  return (
    <div className="flex flex-col gap-6 page-enter max-w-3xl">
      {/* Breadcrumb */}
      <div>
        <div className="flex items-center gap-2 text-sm mb-2 min-w-0">
          <button onClick={() => navigate('/students')} className="text-secondary hover:text-primary transition-colors flex-shrink-0">
            Students
          </button>
          <span className="text-secondary flex-shrink-0">/</span>
          <span className="text-primary truncate">{student.full_name}</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3 sm:gap-4 min-w-0">
            <div className="w-11 h-11 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-base sm:text-lg font-display font-bold text-primary flex-shrink-0">
              {student.first_name?.[0]}{student.last_name?.[0]}
            </div>
            <div className="min-w-0">
              <h1 className="page-title break-words">{student.full_name}</h1>
              <p className="text-muted mt-0.5 flex flex-wrap items-center gap-2">
                <span className="font-mono text-secondary text-xs bg-surface-800 px-2 py-0.5 rounded">{student.student_id}</span>
                <span className="truncate">{student.classroom_name ?? 'No classroom assigned'}</span>
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 sm:flex-shrink-0">
            <Button
              variant="primary"
              size="sm"
              className="w-full sm:w-auto justify-center"
              onClick={() => navigate(`/analytics/student/${student.id}`)}
            >
              <BarChart3 size={13} /> Analytics
            </Button>
            {!editing && (canEdit || canDelete) && (
              <>
                {canEdit && (
                  <button
                    onClick={() => toggleActiveMut.mutate(!student.is_active)}
                    className={`flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-colors w-full sm:w-auto ${student.is_active ? 'text-amber-400 bg-amber-500/10 hover:bg-amber-500/15' : 'text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/15'}`}
                    title={student.is_active ? 'Deactivate' : 'Reactivate'}
                  >
                    {student.is_active ? <ToggleRight size={13} /> : <ToggleLeft size={13} />}
                    {student.is_active ? 'Deactivate' : 'Reactivate'}
                  </button>
                )}
                {canDelete && (
                  <button
                    onClick={() => { if (confirm('Delete this student? This cannot be undone.')) deleteMut.mutate(); }}
                    className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium text-rose-400 bg-rose-500/10 hover:bg-rose-500/15 transition-colors w-full sm:w-auto"
                  >
                    <Trash2 size={13} /> Delete
                  </button>
                )}
                {canEdit && (
                  <Button variant="secondary" size="sm" className="w-full sm:w-auto justify-center" onClick={startEdit}>
                    <Edit2 size={13} /> Edit
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Profile card */}
      <div className="card p-4 sm:p-6">
        {editing ? (
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="section-title">Edit Profile</h2>
              <button type="button" onClick={() => setEditing(false)} className="text-secondary hover:text-primary transition-colors">
                <X size={16} />
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="First Name"
                error={errors.first_name?.message}
                {...register('first_name', { required: 'Required' })}
              />
              <Input
                label="Last Name"
                error={errors.last_name?.message}
                {...register('last_name', { required: 'Required' })}
              />
            </div>
            <Input
              label="Student ID"
              error={errors.student_id?.message}
              {...register('student_id', { required: 'Required' })}
            />
            <Select
              label="Classroom"
              options={[
                { value: '', label: 'None' },
                ...classrooms.map(c => ({ value: c.id, label: `${c.name} — ${c.grade_level_name} (${c.academic_year})` })),
              ]}
              {...register('classroom')}
            />
            <Input
              label="Date of Birth"
              type="date"
              {...register('date_of_birth')}
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="Index Number" {...register('index_number')} />
              <Input label="Region" {...register('region')} />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="District" {...register('district')} />
              <Input label="Parent / Guardian Name" {...register('parent_name')} />
            </div>
            <Input label="Parent Phone" type="tel" {...register('parent_phone')} />
            <div className="flex flex-col gap-1.5">
              <label className="label">Notes</label>
              <textarea className="input resize-none" rows={3} {...register('notes')} />
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" className="w-4 h-4 rounded" {...register('is_active')} />
              <span className="text-sm text-primary">Active student</span>
            </label>
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
              <Button type="submit" loading={updateMutation.isPending}>
                <Save size={13} /> Save Changes
              </Button>
            </div>
          </form>
        ) : (
          <>
            <h2 className="section-title mb-5">Profile Information</h2>
            <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
              {[
                { dt: 'Full Name', dd: student.full_name },
                { dt: 'Email Address', dd: student.email },
                { dt: 'Student ID', dd: student.student_id },
                { dt: 'Classroom', dd: student.classroom_name ?? '—' },
                { dt: 'Date of Birth', dd: student.date_of_birth ? formatDate(student.date_of_birth) : '—' },
                { dt: 'Enrolled', dd: formatDate(student.enrollment_date) },
                { dt: 'Status', dd: student.is_active ? 'Active' : 'Inactive' },
                { dt: 'Index Number', dd: student.index_number || '—' },
                { dt: 'Region', dd: student.region || '—' },
                { dt: 'District', dd: student.district || '—' },
                { dt: 'Parent / Guardian', dd: student.parent_name || '—' },
                { dt: 'Parent Phone', dd: student.parent_phone || '—' },
                { dt: 'Notes', dd: student.notes || '—' },
              ].map(({ dt, dd }) => (
                <div key={dt} className="flex flex-col gap-0.5">
                  <dt className="label">{dt}</dt>
                  <dd className={`text-sm font-medium ${dt === 'Status' ? (student.is_active ? 'text-emerald-400' : 'text-rose-400') : 'text-primary'}`}>
                    {dd}
                  </dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </div>

      {/* Quick links */}
      {!editing && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: 'View Performance Timeline', desc: 'Score history across all exams', action: () => navigate(`/analytics/student/${student.id}`) },
            { label: 'Topic Mastery', desc: 'Breakdown by math topic', action: () => navigate(`/analytics/student/${student.id}`) },
            { label: 'All Scores', desc: 'Every recorded exam score', action: () => navigate(`/analytics/student/${student.id}`) },
          ].map(({ label, desc, action }) => (
            <button
              key={label}
              onClick={action}
              className="card-hover p-4 text-left"
            >
              <p className="font-display font-semibold text-sm text-primary">{label}</p>
              <p className="text-muted text-xs mt-0.5">{desc}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
