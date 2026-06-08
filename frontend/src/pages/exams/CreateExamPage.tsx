import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Plus, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { examsApi, studentsApi } from '../../api';
import { Button, Input, Select } from '../../components/ui';
import type { MathTopic, Classroom, PaginatedResponse } from '../../types';

interface TopicWeightRow { topic: number; max_marks: number }
interface FormData {
  title: string; exam_type: string; term: string; academic_year: string;
  exam_date: string; max_score: number; passing_score: number; description: string;
}

export default function CreateExamPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [topicWeights, setTopicWeights] = useState<TopicWeightRow[]>([]);
  const [selectedClassrooms, setSelectedClassrooms] = useState<number[]>([]);

  const { data: topicsData } = useQuery<{ results?: MathTopic[] } | MathTopic[]>({
    queryKey: ['topics'],
    queryFn: () => examsApi.topics().then(r => r.data),
  });
  const topics: MathTopic[] = Array.isArray(topicsData) ? topicsData : (topicsData as { results?: MathTopic[] })?.results ?? [];

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData) ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    defaultValues: { academic_year: '2024', passing_score: 30 },
  });
  const maxScore = watch('max_score');

  const mutation = useMutation({
    mutationFn: (data: object) => examsApi.createExam(data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['exams'] });
      toast.success('Exam created!');
      navigate(`/exams/${res.data.id}`);
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[]> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to create exam');
    },
  });

  const onSubmit = (data: FormData) => {
    const total = topicWeights.reduce((s, tw) => s + Number(tw.max_marks), 0);
    if (topicWeights.length > 0 && total !== Number(data.max_score)) {
      toast.error(`Topic total (${total}) must equal max score (${data.max_score})`);
      return;
    }
    mutation.mutate({
      ...data,
      classrooms: selectedClassrooms,
      topic_weights: topicWeights.map(tw => ({
        topic: tw.topic,
        max_marks: tw.max_marks,
        weight_percentage: maxScore ? (tw.max_marks / Number(maxScore)) * 100 : 0,
      })),
    });
  };

  const topicTotal = topicWeights.reduce((s, tw) => s + Number(tw.max_marks), 0);
  const toggleClass = (id: number) =>
    setSelectedClassrooms(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]);

  return (
    <div className="flex flex-col gap-4 md:gap-6 max-w-2xl">
      <div>
        <button onClick={() => navigate('/exams')} className="text-secondary hover:text-primary text-sm transition-colors mb-2">← Back to Exams</button>
        <h1 className="page-title">Create Exam</h1>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 md:gap-6">
        {/* Basic Info */}
        <div className="card p-4 md:p-6 flex flex-col gap-4">
          <h2 className="section-title">Basic Information</h2>
          <Input label="Exam Title" placeholder="e.g. Mid-Term I Examination 2024"
            error={errors.title?.message} {...register('title', { required: 'Title is required' })} />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select label="Exam Type" options={[
              { value: 'monthly_test', label: 'Monthly Test' },
              { value: 'mid_term',     label: 'Mid-Term Exam' },
              { value: 'terminal',     label: 'Terminal Exam (End of Term)' },
              { value: 'mock',         label: 'Mock Exam (Mazoezi)' },
              { value: 'necta',        label: 'NECTA' },
              { value: 'psle',         label: 'PSLE (Std 7)' },
              { value: 'csee',         label: 'CSEE (Form 4)' },
              { value: 'acsee',        label: 'ACSEE (Form 6)' },
              { value: 'diagnostic',   label: 'Diagnostic Test' },
            ]} {...register('exam_type', { required: true })} />
            <Select label="Term" options={[
              { value: 'term_1', label: 'Term I (January–April)' },
              { value: 'term_2', label: 'Term II (May–August)' },
              { value: 'term_3', label: 'Term III (September–December)' },
              { value: 'annual', label: 'Annual' },
            ]} {...register('term', { required: true })} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="Academic Year" placeholder="2024"
              {...register('academic_year', { required: true })} />
            <Input label="Exam Date" type="date"
              error={errors.exam_date?.message} {...register('exam_date', { required: 'Date is required' })} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input label="Max Score" type="number" min={1} placeholder="100"
              error={errors.max_score?.message}
              {...register('max_score', { required: true, min: 1, valueAsNumber: true })} />
            <div>
              <Input label="Passing Score" type="number" min={0} placeholder="30"
                {...register('passing_score', { required: true, min: 0, valueAsNumber: true })} />
              <p className="text-xs text-secondary mt-1">Tanzania O-Level pass mark: 30%</p>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label">Description</label>
            <textarea className="input resize-none" rows={2} placeholder="Optional notes…" {...register('description')} />
          </div>
        </div>

        {/* Classrooms */}
        <div className="card p-4 md:p-6 flex flex-col gap-3">
          <h2 className="section-title">Assign to Classrooms</h2>
          <div className="flex flex-wrap gap-2">
            {classrooms.map(c => (
              <button key={c.id} type="button" onClick={() => toggleClass(c.id)}
                className={`px-3 py-1.5 rounded-xl text-xs md:text-sm font-display font-medium border transition-all ${
                  selectedClassrooms.includes(c.id)
                    ? 'bg-azure-500/20 border-azure-500/50 text-azure-400'
                    : 'bg-surface-900 border-surface text-secondary hover:border-azure-500/50 hover:text-primary'
                }`}>
                {c.name}
              </button>
            ))}
            {classrooms.length === 0 && <p className="text-muted text-sm">No classrooms available.</p>}
          </div>
        </div>

        {/* Topic Weights */}
        <div className="card p-4 md:p-6 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="section-title">Topic Weights</h2>
              <p className="text-muted text-xs mt-0.5">Optional — marks per topic</p>
            </div>
            <Button type="button" variant="secondary" size="sm"
              onClick={() => setTopicWeights(prev => [...prev, { topic: topics[0]?.id ?? 0, max_marks: 0 }])}>
              <Plus size={13} /> Topic
            </Button>
          </div>
          {topicWeights.length > 0 && (
            <div className="flex flex-col gap-2">
              {topicWeights.map((tw, i) => (
                <div key={i} className="flex items-center gap-2 bg-surface-900 rounded-xl p-3">
                  <select className="input flex-1 text-sm" value={tw.topic}
                    onChange={e => setTopicWeights(p => p.map((t, idx) => idx === i ? { ...t, topic: Number(e.target.value) } : t))}>
                    {topics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                  <input type="number" className="input w-20 text-sm text-center" placeholder="Marks" min={0}
                    value={tw.max_marks}
                    onChange={e => setTopicWeights(p => p.map((t, idx) => idx === i ? { ...t, max_marks: Number(e.target.value) } : t))} />
                  <button type="button" onClick={() => setTopicWeights(p => p.filter((_, idx) => idx !== i))}
                    className="text-secondary hover:text-rose-400 transition-colors p-1 flex-shrink-0">
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              <p className={`text-xs font-mono px-1 ${maxScore && topicTotal === Number(maxScore) ? 'text-emerald-400' : 'text-amber-400'}`}>
                Total: {topicTotal} / {maxScore ?? 0}
              </p>
            </div>
          )}
        </div>

        <div className="flex gap-3 justify-end">
          <Button type="button" variant="secondary" onClick={() => navigate('/exams')}>Cancel</Button>
          <Button type="submit" loading={mutation.isPending}>Create Exam</Button>
        </div>
      </form>
    </div>
  );
}
