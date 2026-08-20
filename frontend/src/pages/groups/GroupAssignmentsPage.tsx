import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ClipboardCheck, Plus, Pencil, Trash2, BarChart3, Users2,
} from 'lucide-react';
import { groupAssignmentsApi, studentsApi, subjectsApi } from '../../api';
import {
  LoadingPage, EmptyState, Button, Select, Input, Modal, Table, Tr, Td,
} from '../../components/ui';
import { formatDate, TERM_LABELS, ASSIGNMENT_TYPE_LABELS } from '../../utils';
import type {
  Classroom, PaginatedResponse, Subject, Stream, GroupAssignment, AssignmentType,
} from '../../types';

const TODAY = new Date().toISOString().slice(0, 10);

interface AssignmentForm {
  title: string; description: string; assignment_type: AssignmentType;
  subject: string; stream: string; term: string; academic_year: string;
  date_given: string; due_date: string; max_score: string;
}

function emptyForm(academicYear: string): AssignmentForm {
  return {
    title: '', description: '', assignment_type: 'classwork',
    subject: '', stream: '', term: '', academic_year: academicYear,
    date_given: TODAY, due_date: '', max_score: '50',
  };
}

export default function GroupAssignmentsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedClass, setSelectedClass] = useState<number | null>(null);
  const [subjectFilter, setSubjectFilter] = useState('');
  const [streamFilter, setStreamFilter] = useState('');
  const [termFilter, setTermFilter] = useState('');

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<GroupAssignment | null>(null);
  const [form, setForm] = useState<AssignmentForm>(emptyForm('2026'));
  const [deleteTarget, setDeleteTarget] = useState<GroupAssignment | null>(null);

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms-all-group-assignments'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];
  const classroom = classrooms.find(c => c.id === selectedClass) || null;

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects-all-group-assignments'],
    queryFn: () => subjectsApi.list({ page_size: 100 }).then(r => r.data),
  });
  const subjects: Subject[] = Array.isArray(subjectsData)
    ? subjectsData : (subjectsData as PaginatedResponse<Subject>)?.results ?? [];

  const { data: streamsData } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams-for-group-assignments', selectedClass],
    queryFn: () => studentsApi.streams({ classroom: selectedClass, page_size: 200 }).then(r => r.data),
    enabled: !!selectedClass,
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const { data: assignmentsData, isLoading } = useQuery<PaginatedResponse<GroupAssignment> | GroupAssignment[]>({
    queryKey: ['group-assignments', selectedClass, subjectFilter, streamFilter, termFilter],
    queryFn: () => groupAssignmentsApi.list({
      classroom: selectedClass, subject: subjectFilter || undefined,
      stream: streamFilter || undefined, term: termFilter || undefined, page_size: 200,
    }).then(r => r.data),
    enabled: !!selectedClass,
  });
  const assignments: GroupAssignment[] = Array.isArray(assignmentsData)
    ? assignmentsData : (assignmentsData as PaginatedResponse<GroupAssignment>)?.results ?? [];

  const createMutation = useMutation({
    mutationFn: (data: object) => groupAssignmentsApi.create(data),
    onSuccess: () => {
      toast.success('Group assignment created.');
      queryClient.invalidateQueries({ queryKey: ['group-assignments'] });
      setFormOpen(false);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not create assignment.'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: object }) => groupAssignmentsApi.update(id, data),
    onSuccess: () => {
      toast.success('Assignment updated.');
      queryClient.invalidateQueries({ queryKey: ['group-assignments'] });
      setFormOpen(false);
      setEditing(null);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not update assignment.'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => groupAssignmentsApi.delete(id),
    onSuccess: () => {
      toast.success('Assignment deleted.');
      queryClient.invalidateQueries({ queryKey: ['group-assignments'] });
      setDeleteTarget(null);
    },
    onError: () => toast.error('Could not delete assignment.'),
  });

  const openCreate = () => {
    if (!classroom) return;
    setEditing(null);
    setForm(emptyForm(classroom.academic_year));
    setFormOpen(true);
  };

  const openEdit = (a: GroupAssignment) => {
    setEditing(a);
    setForm({
      title: a.title, description: a.description, assignment_type: a.assignment_type,
      subject: a.subject ? String(a.subject) : '', stream: a.stream ? String(a.stream) : '',
      term: a.term, academic_year: a.academic_year, date_given: a.date_given,
      due_date: a.due_date || '', max_score: String(a.max_score),
    });
    setFormOpen(true);
  };

  const submitForm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClass) return;
    if (!form.title.trim()) { toast.error('Title is required.'); return; }
    const payload = {
      classroom: selectedClass,
      subject: form.subject || null,
      stream: form.stream || null,
      title: form.title.trim(),
      description: form.description,
      assignment_type: form.assignment_type,
      term: form.term,
      academic_year: form.academic_year,
      date_given: form.date_given,
      due_date: form.due_date || null,
      max_score: Number(form.max_score) || 100,
    };
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  return (
    <div className="p-4 md:p-6 flex flex-col gap-5 max-w-6xl mx-auto page-enter">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold text-primary flex items-center gap-2">
            <ClipboardCheck className="text-azure-400" size={24} /> Group Assignments
          </h1>
          <p className="text-sm text-secondary mt-0.5">
            Give group work, then record one mark per group instead of per student.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" disabled={!selectedClass}
            onClick={() => selectedClass && navigate(`/groups/analytics/${selectedClass}`)}>
            <BarChart3 size={14} /> Group Work Analytics
          </Button>
          <Button size="sm" disabled={!selectedClass} onClick={openCreate}>
            <Plus size={14} /> New Assignment
          </Button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <div className="min-w-[220px]">
          <Select
            label="Classroom"
            options={[{ value: '', label: 'Select a classroom…' }, ...classrooms.map(c => ({
              value: c.id, label: `${c.name} (${c.academic_year})`,
            }))]}
            value={selectedClass ?? ''}
            onChange={e => setSelectedClass(e.target.value ? Number(e.target.value) : null)}
          />
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Stream" disabled={!selectedClass}
            options={[{ value: '', label: 'All streams' }, ...streams.map(s => ({ value: s.id, label: s.name }))]}
            value={streamFilter} onChange={e => setStreamFilter(e.target.value)}
          />
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Subject"
            options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
            value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)}
          />
        </div>
        <div className="min-w-[180px]">
          <Select
            label="Term"
            options={[{ value: '', label: 'All terms' }, ...Object.entries(TERM_LABELS).map(([v, l]) => ({ value: v, label: l }))]}
            value={termFilter} onChange={e => setTermFilter(e.target.value)}
          />
        </div>
      </div>

      {!selectedClass ? (
        <EmptyState icon={<ClipboardCheck size={36} />} title="Select a classroom"
          message="Choose a classroom above to see and record its group assignments." />
      ) : isLoading ? (
        <LoadingPage />
      ) : assignments.length === 0 ? (
        <EmptyState icon={<ClipboardCheck size={36} />} title="No group assignments yet"
          message="Create one to start recording marks for this classroom's peer groups." />
      ) : (
        <div className="card p-0 overflow-hidden">
          <Table headers={['Assignment', 'Type', 'Subject', 'Stream', 'Date', 'Max', 'Marked', 'Actions']}>
            {assignments.map(a => (
              <Tr key={a.id}>
                <Td>
                  <button className="font-semibold text-primary hover:text-azure-400 text-left"
                    onClick={() => navigate(`/groups/assignments/${a.id}/marks`)}>
                    {a.title}
                  </button>
                  {a.description && <p className="text-xs text-muted mt-0.5 line-clamp-1">{a.description}</p>}
                </Td>
                <Td><span className="badge badge-violet">{a.assignment_type_display}</span></Td>
                <Td>{a.subject_name || '—'}</Td>
                <Td>{a.stream_name || 'All'}</Td>
                <Td>{formatDate(a.date_given)}</Td>
                <Td>{a.max_score}</Td>
                <Td>
                  <span className={a.groups_scored >= a.groups_expected && a.groups_expected > 0
                    ? 'text-emerald-400 font-semibold' : 'text-amber-400 font-semibold'}>
                    {a.groups_scored}/{a.groups_expected}
                  </span>
                </Td>
                <Td>
                  <div className="flex gap-1.5">
                    <Button variant="secondary" size="sm" onClick={() => navigate(`/groups/assignments/${a.id}/marks`)}>
                      <Users2 size={12} /> Marks
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openEdit(a)}><Pencil size={12} /></Button>
                    <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(a)}><Trash2 size={12} className="text-rose-400" /></Button>
                  </div>
                </Td>
              </Tr>
            ))}
          </Table>
        </div>
      )}

      {/* Create / edit modal */}
      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? 'Edit Assignment' : 'New Group Assignment'} size="lg">
        <form onSubmit={submitForm} className="flex flex-col gap-4">
          <Input label="Title" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} required />
          <div>
            <label className="label">Description</label>
            <textarea className="input min-h-[70px]" value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Select label="Type" options={Object.entries(ASSIGNMENT_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }))}
              value={form.assignment_type} onChange={e => setForm(f => ({ ...f, assignment_type: e.target.value as AssignmentType }))} />
            <Select label="Subject (optional)"
              options={[{ value: '', label: 'Any subject' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
              value={form.subject} onChange={e => setForm(f => ({ ...f, subject: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Select label="Restrict to stream (optional)"
              options={[{ value: '', label: 'All streams' }, ...streams.map(s => ({ value: s.id, label: s.name }))]}
              value={form.stream} onChange={e => setForm(f => ({ ...f, stream: e.target.value }))} />
            <Select label="Term" options={[{ value: '', label: 'No term' }, ...Object.entries(TERM_LABELS).map(([v, l]) => ({ value: v, label: l }))]}
              value={form.term} onChange={e => setForm(f => ({ ...f, term: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Academic Year" value={form.academic_year}
              onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))} required />
            <Input label="Max Score" type="number" min={1} value={form.max_score}
              onChange={e => setForm(f => ({ ...f, max_score: e.target.value }))} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Date Given" type="date" value={form.date_given}
              onChange={e => setForm(f => ({ ...f, date_given: e.target.value }))} required />
            <Input label="Due Date (optional)" type="date" value={form.due_date}
              onChange={e => setForm(f => ({ ...f, due_date: e.target.value }))} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setFormOpen(false)}>Cancel</Button>
            <Button type="submit" loading={createMutation.isPending || updateMutation.isPending}>
              {editing ? 'Save Changes' : 'Create Assignment'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete confirmation */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Assignment" size="sm"
        footer={<>
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button variant="danger" loading={deleteMutation.isPending}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}>Delete</Button>
        </>}>
        <p className="text-sm text-secondary">
          Delete "<strong>{deleteTarget?.title}</strong>"? This also removes every group's recorded mark for it.
        </p>
      </Modal>
    </div>
  );
}
