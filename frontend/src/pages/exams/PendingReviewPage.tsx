import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ClipboardCheck, Send, Eye, Calendar, User, BookOpen } from 'lucide-react';
import toast from 'react-hot-toast';
import { examsApi } from '../../api';
import { LoadingPage, EmptyState, Button } from '../../components/ui';
import { formatDate, EXAM_TYPE_LABELS, TERM_LABELS } from '../../utils';
import type { Exam, PaginatedResponse } from '../../types';

interface PendingResponse { results: Exam[]; count: number }

export default function PendingReviewPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<PendingResponse>({
    queryKey: ['exams-pending'],
    queryFn: () => examsApi.pendingReview().then(r => r.data),
  });

  const publishMutation = useMutation({
    mutationFn: (id: number) => examsApi.publishExam(id),
    onSuccess: (_res, id) => {
      toast.success('Exam published and now visible to students.');
      qc.invalidateQueries({ queryKey: ['exams-pending'] });
      qc.invalidateQueries({ queryKey: ['exams'] });
      qc.invalidateQueries({ queryKey: ['exam', id] });
    },
    onError: () => toast.error('Failed to publish exam.'),
  });

  const exams = data?.results ?? [];

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <ClipboardCheck size={22} className="text-azure-400" />
          Pending Review
        </h1>
        <p className="text-muted text-sm mt-1">
          Exams submitted by teachers awaiting your approval before students can see them.
        </p>
      </div>

      {/* Summary badge */}
      {!isLoading && (
        <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-medium ${
          exams.length > 0
            ? 'bg-amber-500/10 border-amber-500/25 text-amber-400'
            : 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
        }`}>
          <ClipboardCheck size={15} />
          {exams.length > 0
            ? `${exams.length} exam${exams.length !== 1 ? 's' : ''} waiting for review`
            : 'No exams pending — all clear!'}
        </div>
      )}

      {isLoading ? (
        <LoadingPage />
      ) : exams.length === 0 ? (
        <EmptyState
          icon={<ClipboardCheck size={40} />}
          title="Nothing pending"
          message="When a teacher creates an exam it will appear here for you to review and publish."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {exams.map(exam => (
            <div key={exam.id} className="card p-4 md:p-5 flex flex-col gap-3">
              {/* Header row */}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className={`badge text-[10px] ${exam.subject_color ? '' : 'badge-blue'}`}
                      style={exam.subject_color ? {
                        backgroundColor: exam.subject_color + '22',
                        color: exam.subject_color,
                        borderColor: exam.subject_color + '44',
                      } : undefined}
                    >
                      {exam.subject_code || exam.subject_name || 'No subject'}
                    </span>
                    <span className="badge badge-amber text-[10px]">Draft</span>
                    <span className="badge text-[10px]">
                      {EXAM_TYPE_LABELS[exam.exam_type] ?? exam.exam_type}
                    </span>
                  </div>
                  <h3 className="font-display font-semibold text-primary leading-tight">
                    {exam.title}
                  </h3>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => navigate(`/exams/${exam.id}`)}
                  >
                    <Eye size={13} /> Review
                  </Button>
                  <Button
                    size="sm"
                    loading={publishMutation.isPending && publishMutation.variables === exam.id}
                    onClick={() => publishMutation.mutate(exam.id)}
                  >
                    <Send size={13} /> Publish
                  </Button>
                </div>
              </div>

              {/* Meta row */}
              <div className="flex items-center gap-4 flex-wrap text-xs text-secondary">
                <span className="flex items-center gap-1">
                  <User size={11} /> {exam.created_by_name || 'Unknown teacher'}
                </span>
                <span className="flex items-center gap-1">
                  <Calendar size={11} /> Exam date: {formatDate(exam.exam_date)}
                </span>
                <span className="flex items-center gap-1">
                  <BookOpen size={11} /> {TERM_LABELS[exam.term] ?? exam.term}
                </span>
                {exam.classrooms?.length > 0 && (
                  <span className="flex items-center gap-1">
                    {exam.classrooms.length} classroom{exam.classrooms.length !== 1 ? 's' : ''}
                  </span>
                )}
                <span>Max score: {exam.max_score}</span>
              </div>

              {/* Description if any */}
              {exam.description && (
                <p className="text-xs text-secondary border-t border-surface pt-2 mt-1 line-clamp-2">
                  {exam.description}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
