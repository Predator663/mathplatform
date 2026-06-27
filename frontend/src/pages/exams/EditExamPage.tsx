import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Plus, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { examsApi, studentsApi } from '../../api';
import { LoadingPage, Button, Input, Select } from '../../components/ui';
import type { Exam, MathTopic, Classroom, PaginatedResponse } from '../../types';

interface TopicWeightRow { topic: number; max_marks: number }
interface FormData {
  title: string;
  exam_type: string;
  term: string;
  academic_year: string;
  exam_date: string;
  max_score: number;
  passing_score: number;
  description: string;
}

export default function EditExamPage() {
  const { id } = useParams<{ id: string }>();
  const examId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [topicWeights, setTopicWeights] = useState<TopicWeightRow[]>([]);
  const [selectedClassrooms, setSelectedClassrooms] = useState<number[]>([]);

  const { data: exam, isLoading } = useQuery<Exam>({
    queryKey: ['exam', examId],
    queryFn: () => examsApi.exam(examId).then(r => r.data),
  });

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

  const { register, handleSubmit, reset, watch, formState: { errors } } = useForm<FormData>();
  const maxScore = watch('max_score');

  // Pre-fill form when exam loads
  useEffect(() => {
    if (!exam) return;
    reset({
      title: exam.title,
      exam_type: exam.exam_type,
      term: exam.term,
      academic_year: exam.academic_year,
      exam_date: exam.exam_date,
      max_score: exam.max_score,
      passing_score: exam.passing_score,
      description: exam.description,
    });
    setTopicWeights(exam.topic_weights.map(tw => ({ topic: tw.topic, max_marks: tw.max_marks })));
    setSelectedClassrooms(exam.classrooms);
  }, [exam, reset]);

  const mutation = useMutation({
    mutationFn: (data: object) => examsApi.updateExam(examId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exam', examId] });
      queryClient.invalidateQueries({ queryKey: ['exams'] });
      toast.success('Exam updated!');
      navigate(`/exams/${examId}`);
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: Record<string, string[]> } };
      const msgs = error?.response?.data;
      if (msgs) {
        Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      } else {
        toast.error('Failed to update exam');
      }
    },
  });

  const onSubmit = (data: FormData) => {
    if (selectedClassrooms.length === 0) {
      toast.error('Select at least one classroom for this exam.');
      return;
    }
    const totalTopicMarks = topicWeights.reduce((s, tw) => s + Number(tw.max_marks), 0);
    if (topicWeights.length > 0 && totalTopicMarks !== Number(data.max_score)) {
      toast.error(`Topic marks total (${totalTopicMarks}) must equal max score (${data.max_score})`);
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

  const addTopicWeight = () => setTopicWeights(prev => [...prev, { topic: topics[0]?.id ?? 0, max_marks: 0 }]);
  const removeTopicWeight = (i: number) => setTopicWeights(prev => prev.filter((_, idx) => idx !== i));
  const updateTopicWeight = (i: number, field: keyof TopicWeightRow, value: number) =>
    setTopicWeights(prev => prev.map((tw, idx) => idx === i ? { ...tw, [field]: value } : tw));
  const toggleClassroom = (cid: number) =>
    setSelectedClassrooms(prev => prev.includes(cid) ? prev.filter(c => c !== cid) : [...prev, cid]);

  const topicMarksTotal = topicWeights.reduce((s, tw) => s + Number(tw.max_marks), 0);

  if (isLoading) return <LoadingPage />;
  if (!exam) return <div className="text-muted">Exam not found.</div>;

  return (
    <div className="flex flex-col gap-6 max-w-3xl page-enter">
      <div>
        <button onClick={() => navigate(`/exams/${examId}`)} className="text-secondary hover:text-primary text-sm transition-colors mb-2">
          ← Back to Exam
        </button>
        <h1 className="page-title">Edit Exam</h1>
        <p className="text-muted mt-1">{exam.title}</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
        {/* Basic Info */}
        <div className="card p-6 flex flex-col gap-4">
          <h2 className="section-title">Basic Information</h2>
          <Input
            label="Exam Title"
            error={errors.title?.message}
            {...register('title', { required: 'Title is required' })}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Select
                label="Exam Type"
                options={[
                  { value: 'monthly_test', label: 'Monthly Test' },
                  { value: 'mid_term',     label: 'Mid-Term Exam ¹' },
                  { value: 'terminal',     label: 'Terminal Exam (End of Term) ¹' },
                  { value: 'mock',         label: 'Mock Exam (Mazoezi)' },
                  { value: 'necta',        label: 'NECTA ¹' },
                  { value: 'psle',         label: 'PSLE (Std 7) ¹' },
                  { value: 'csee',         label: 'CSEE (Form 4) ¹' },
                  { value: 'acsee',        label: 'ACSEE (Form 6) ¹' },
                  { value: 'diagnostic',   label: 'Diagnostic Test' },
                ]}
                {...register('exam_type', { required: true })}
              />
              <p className="text-xs text-secondary leading-snug">
                Types marked <span className="font-mono text-primary">¹</span> allow only one per classroom per term.
                Monthly tests, diagnostics and mocks are unlimited.
              </p>
            </div>
            <Select
              label="Term"
              options={[
                { value: 'term_1', label: 'Term I (January–April)' },
                { value: 'term_2', label: 'Term II (May–August)' },
                { value: 'term_3', label: 'Term III (September–December)' },
                { value: 'annual', label: 'Annual' },
              ]}
              {...register('term', { required: true })}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="Academic Year" {...register('academic_year', { required: true })} />
            <Input label="Exam Date" type="date" {...register('exam_date', { required: true })} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Maximum Score"
              type="number"
              min={1}
              error={errors.max_score?.message}
              {...register('max_score', { required: true, min: 1, valueAsNumber: true })}
            />
            <Input
              label="Passing Score"
              type="number"
              min={0}
              {...register('passing_score', { required: true, min: 0, valueAsNumber: true })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label">Description</label>
            <textarea className="input resize-none" rows={3} {...register('description')} />
          </div>
        </div>

        {/* Classrooms */}
        <div className="card p-6 flex flex-col gap-4">
          <h2 className="section-title">Assigned Classrooms *</h2>
          <div className="flex flex-wrap gap-2">
            {classrooms.map(c => (
              <button
                key={c.id}
                type="button"
                onClick={() => toggleClassroom(c.id)}
                className={`px-3 py-1.5 rounded-xl text-sm font-display font-medium border transition-all ${
                  selectedClassrooms.includes(c.id)
                    ? 'bg-azure-500/20 border-azure-500/50 text-azure-400'
                    : 'bg-surface-900 border-surface text-secondary hover:border-azure-500/50 hover:text-primary'
                }`}
              >
                {c.name} · {c.grade_level_name}
              </button>
            ))}
          </div>
        </div>

        {/* Topic Weights */}
        <div className="card p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="section-title">Topic Weights</h2>
              <p className="text-muted text-xs mt-0.5">Marks allocated per math topic</p>
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={addTopicWeight}>
              <Plus size={13} /> Add Topic
            </Button>
          </div>
          {topicWeights.length > 0 && (
            <div className="flex flex-col gap-2">
              {topicWeights.map((tw, i) => (
                <div key={i} className="flex items-center gap-3 bg-surface-900 rounded-xl p-3">
                  <select
                    className="input flex-1"
                    value={tw.topic}
                    onChange={e => updateTopicWeight(i, 'topic', Number(e.target.value))}
                  >
                    {topics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                  <input
                    type="number"
                    className="input w-28"
                    placeholder="Marks"
                    min={0}
                    value={tw.max_marks}
                    onChange={e => updateTopicWeight(i, 'max_marks', Number(e.target.value))}
                  />
                  <button type="button" onClick={() => removeTopicWeight(i)} className="text-secondary hover:text-rose-400 transition-colors p-1">
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              <div className={`flex justify-between text-xs font-mono px-1 ${
                maxScore && topicMarksTotal === Number(maxScore) ? 'text-emerald-400' : 'text-amber-400'
              }`}>
                <span>Topic total: {topicMarksTotal}</span>
                <span>Max score: {maxScore ?? 0}</span>
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-3 justify-end">
          <Button type="button" variant="secondary" onClick={() => navigate(`/exams/${examId}`)}>Cancel</Button>
          <Button type="submit" loading={mutation.isPending}>Save Changes</Button>
        </div>
      </form>
    </div>
  );
}
