import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { quizzesApi, examsApi, studentsApi, subjectsApi } from '../../api';
import { Button, Input, Select } from '../../components/ui';
import { PermissionGate } from '../../components/ui/PermissionGate';
import { useSubjectStore } from '../../store/subject';
import { useSiteSettingsStore } from '../../store/siteSettings';
import type { MathTopic, Classroom, Subject, PaginatedResponse } from '../../types';

interface FormData {
  date: string; classroom: number; subject: number; topic: number | '';
  title: string; term: string; academic_year: string;
  max_score: number; passing_score: number; notes: string;
}

const todayIso = () => new Date().toISOString().slice(0, 10);

export default function CreateQuizPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { activeSubjectId } = useSubjectStore();
  const { settings } = useSiteSettingsStore();

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
  });
  const subjects: Subject[] = Array.isArray(subjectsData) ? subjectsData : subjectsData?.results ?? [];

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData) ? classroomsData : classroomsData?.results ?? [];

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    defaultValues: {
      date: todayIso(),
      academic_year: settings.current_academic_year || new Date().getFullYear().toString(),
      term: settings.current_term || undefined,
      subject: activeSubjectId ?? undefined,
      max_score: 10, passing_score: 5,
    },
  });
  const watchedSubject = watch('subject');

  const { data: topicsData } = useQuery<{ results?: MathTopic[] } | MathTopic[]>({
    queryKey: ['topics', watchedSubject],
    queryFn: () => examsApi.topics({ subject: watchedSubject }).then(r => r.data),
    enabled: !!watchedSubject,
  });
  const topics: MathTopic[] = Array.isArray(topicsData) ? topicsData : topicsData?.results ?? [];

  const mutation = useMutation({
    mutationFn: (data: object) => quizzesApi.createQuiz(data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['quizzes'] });
      toast.success('Quiz created — ready for marks');
      navigate(`/quizzes/${res.data.id}/marks`);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[] | string> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to create quiz');
    },
  });

  const onSubmit = (data: FormData) => {
    mutation.mutate({ ...data, topic: data.topic || null });
  };

  return (
    <PermissionGate resource="quizzes" action="add" backTo="/quizzes" backLabel="Back to Quizzes">
      <div className="flex flex-col gap-4 md:gap-6 max-w-xl">
        <div>
          <button onClick={() => navigate('/quizzes')} className="text-secondary hover:text-primary text-sm transition-colors mb-2">← Back to Quizzes</button>
          <h1 className="page-title">New Daily Quiz</h1>
          <p className="text-muted mt-0.5">Quick setup — you'll enter marks right after.</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 md:gap-6">
          <div className="card p-4 md:p-6 flex flex-col gap-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="Date" type="date" error={errors.date?.message}
                {...register('date', { required: 'Date is required' })} />
              <div>
                <label className="text-xs font-medium text-secondary uppercase tracking-wider">Classroom *</label>
                <select
                  {...register('classroom', { required: 'Classroom is required', valueAsNumber: true })}
                  className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
                >
                  <option value="">Select classroom…</option>
                  {classrooms.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                {errors.classroom && <p className="text-xs text-red-400 mt-1">{errors.classroom.message}</p>}
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-secondary uppercase tracking-wider">Subject *</label>
              <select
                {...register('subject', { required: 'Subject is required', valueAsNumber: true })}
                className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
              >
                <option value="">Select subject…</option>
                {subjects.map(s => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
              </select>
              {errors.subject && <p className="text-xs text-red-400 mt-1">{errors.subject.message}</p>}
            </div>

            <div>
              <label className="text-xs font-medium text-secondary uppercase tracking-wider">Topic</label>
              <select
                {...register('topic')}
                disabled={!watchedSubject}
                className="mt-1 w-full bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500 disabled:opacity-50"
              >
                <option value="">Mixed / no single topic</option>
                {topics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              <p className="text-xs text-secondary mt-1">Tagging a topic powers the topic-level progress charts.</p>
            </div>

            <Input label="Title (optional)" placeholder="Defaults to the topic name + date"
              {...register('title')} />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select label="Term" options={[
                { value: 'term_1', label: 'Term I (January–April)' },
                { value: 'term_2', label: 'Term II (May–August)' },
                { value: 'term_3', label: 'Term III (September–December)' },
                { value: 'annual', label: 'Annual' },
              ]} {...register('term', { required: true })} />
              <Input label="Academic Year" placeholder="2026" {...register('academic_year', { required: true })} />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="Max Score" type="number" min={1} placeholder="10"
                error={errors.max_score?.message}
                {...register('max_score', { required: true, min: 1, valueAsNumber: true })} />
              <Input label="Passing Score" type="number" min={0} placeholder="5"
                {...register('passing_score', { required: true, min: 0, valueAsNumber: true })} />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="label">Notes</label>
              <textarea className="input resize-none" rows={2} placeholder="Optional notes…" {...register('notes')} />
            </div>
          </div>

          <div className="flex gap-3 justify-end">
            <Button type="button" variant="secondary" onClick={() => navigate('/quizzes')}>Cancel</Button>
            <Button type="submit" loading={mutation.isPending}>Create & Enter Marks</Button>
          </div>
        </form>
      </div>
    </PermissionGate>
  );
}
