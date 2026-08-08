import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Trash2, RotateCcw, Calendar, User, BookOpen, AlertTriangle, Eye } from 'lucide-react';
import toast from 'react-hot-toast';
import { examsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Modal, Pagination } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { formatDate, EXAM_TYPE_LABELS, TERM_LABELS } from '../../utils';
import type { Exam } from '../../types';

interface TrashResponse { results: Exam[]; count: number }

export default function TrashPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [page, setPage] = useState(1);
  const { getPage } = useSiteSettingsStore();
  const pageSize = getPage('exams').page_size;

  const { data, isLoading } = useQuery<TrashResponse>({
    queryKey: ['exams-trash', page, pageSize],
    queryFn: () => examsApi.trash({ page, page_size: pageSize }).then(r => r.data),
  });

  const restoreMutation = useMutation({
    mutationFn: (id: number) => examsApi.restoreExam(id),
    onSuccess: () => {
      toast.success('Exam restored.');
      qc.invalidateQueries({ queryKey: ['exams-trash'] });
      qc.invalidateQueries({ queryKey: ['exams'] });
    },
    onError: () => toast.error('Failed to restore exam.'),
  });

  const emptyTrashMutation = useMutation({
    mutationFn: () => examsApi.emptyTrash(),
    onSuccess: (res) => {
      const count = res.data?.deleted_count ?? 0;
      toast.success(
        count > 0
          ? `Permanently deleted ${count} exam${count !== 1 ? 's' : ''}.`
          : 'Trash was already empty.'
      );
      qc.invalidateQueries({ queryKey: ['exams-trash'] });
      setConfirmOpen(false);
      setPage(1);
    },
    onError: () => {
      toast.error('Failed to empty trash.');
      setConfirmOpen(false);
    },
  });

  const exams = data?.results ?? [];
  const total = data?.count ?? 0;

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Trash2 size={22} className="text-azure-400" />
            Trash
          </h1>
          <p className="text-muted text-sm mt-1">
            Deleted exams end up here first. Restore one, or permanently clear everything at once.
          </p>
        </div>
        {total > 0 && (
          <Button variant="danger" onClick={() => setConfirmOpen(true)}>
            <Trash2 size={14} /> Empty Trash ({total})
          </Button>
        )}
      </div>

      {isLoading ? (
        <LoadingPage />
      ) : exams.length === 0 ? (
        <EmptyState
          icon={<Trash2 size={40} />}
          title="Trash is empty"
          message="Soft-deleted exams will show up here so nothing disappears without a trace."
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
                    <span className="badge badge-rose text-[10px]">Deleted</span>
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
                    <Eye size={13} /> View
                  </Button>
                  <Button
                    size="sm"
                    loading={restoreMutation.isPending && restoreMutation.variables === exam.id}
                    onClick={() => restoreMutation.mutate(exam.id)}
                  >
                    <RotateCcw size={13} /> Restore
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
            </div>
          ))}
          <Pagination page={page} pageSize={pageSize} total={total} onChange={setPage} />
        </div>
      )}

      {/* Empty-trash confirmation */}
      <Modal
        open={confirmOpen}
        onClose={() => (emptyTrashMutation.isPending ? undefined : setConfirmOpen(false))}
        title="Permanently delete all trashed exams?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)} disabled={emptyTrashMutation.isPending}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={emptyTrashMutation.isPending}
              onClick={() => emptyTrashMutation.mutate()}
            >
              <Trash2 size={14} /> Permanently Delete {total} Exam{total !== 1 ? 's' : ''}
            </Button>
          </>
        }
      >
        <div className="flex items-start gap-3">
          <AlertTriangle size={20} className="text-rose-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-secondary">
            This permanently deletes every exam currently in the trash, along with all of their
            scores and score-history. This cannot be undone — exams removed this way can no
            longer be restored.
          </p>
        </div>
      </Modal>
    </div>
  );
}
