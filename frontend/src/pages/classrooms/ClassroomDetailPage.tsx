import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { School, Users, BarChart3, FileText, Plus, Trash2, UserPlus, Edit2, Save, X, Layers } from 'lucide-react';
import toast from 'react-hot-toast';
import { studentsApi, authApi, subjectsApi, assignmentsApi } from '../../api';
import { LoadingPage, Button, Select, Modal, Input } from '../../components/ui';
import { EDUCATION_LEVEL_LABELS } from '../../utils';
import { useAuthStore } from '../../store/auth';
import { useCanManage } from '../../hooks/useCanManage';
import type { Classroom, User, Subject, TeacherAssignment, Stream, PaginatedResponse } from '../../types';

interface EditClassroomForm {
  name: string;
  academic_year: string;
}

interface StreamFormState {
  id: number | null;
  name: string;
  capacity: string;
}

export default function ClassroomDetailPage() {
  const { id } = useParams<{ id: string }>();
  const classroomId = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin';
  const canEdit = useCanManage('classrooms', 'edit');
  const canDelete = useCanManage('classrooms', 'delete');
  const canAddStream = useCanManage('classrooms', 'add');
  const canEditStream = useCanManage('classrooms', 'edit');
  const canDeleteStream = useCanManage('classrooms', 'delete');

  const [modalOpen, setModalOpen] = useState(false);
  const [teacherId, setTeacherId] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editYear, setEditYear] = useState('');
  const [streamModalOpen, setStreamModalOpen] = useState(false);
  const [streamForm, setStreamForm] = useState<StreamFormState>({ id: null, name: '', capacity: '' });

  const { data: classroom, isLoading } = useQuery<Classroom>({
    queryKey: ['classroom', classroomId],
    queryFn: () => studentsApi.classroom(classroomId).then(r => r.data),
  });

  const { data: teachersData } = useQuery<User[]>({
    queryKey: ['assignable-teachers'],
    queryFn: () => authApi.assignableTeachers().then(r => r.data),
    enabled: isAdmin,
  });
  const teachers: User[] = teachersData ?? [];

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects', 'active'],
    queryFn: () => subjectsApi.list({ is_active: true }).then(r => r.data),
    enabled: isAdmin,
  });
  const subjects: Subject[] = Array.isArray(subjectsData)
    ? subjectsData : (subjectsData as PaginatedResponse<Subject>)?.results ?? [];

  const { data: assignmentsData, isLoading: assignmentsLoading } = useQuery<PaginatedResponse<TeacherAssignment> | TeacherAssignment[]>({
    queryKey: ['assignments'],
    queryFn: () => assignmentsApi.list().then(r => r.data),
  });
  const allAssignments: TeacherAssignment[] = Array.isArray(assignmentsData)
    ? assignmentsData : (assignmentsData as PaginatedResponse<TeacherAssignment>)?.results ?? [];
  const assignments = allAssignments.filter(a => a.classroom === classroomId);

  const { data: streamsData, isLoading: streamsLoading } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams', classroomId],
    queryFn: () => studentsApi.streams({ classroom: classroomId, page_size: 200 }).then(r => r.data),
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const createStreamMutation = useMutation({
    mutationFn: (data: { classroom: number; name: string; capacity: number | null }) =>
      studentsApi.createStream(data),
    onSuccess: () => {
      toast.success('Stream created');
      qc.invalidateQueries({ queryKey: ['streams', classroomId] });
      qc.invalidateQueries({ queryKey: ['classroom', classroomId] });
      setStreamModalOpen(false);
      setStreamForm({ id: null, name: '', capacity: '' });
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[]> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to create stream');
    },
  });

  const updateStreamMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { name: string; capacity: number | null } }) =>
      studentsApi.updateStream(id, data),
    onSuccess: () => {
      toast.success('Stream updated');
      qc.invalidateQueries({ queryKey: ['streams', classroomId] });
      qc.invalidateQueries({ queryKey: ['classroom', classroomId] });
      setStreamModalOpen(false);
      setStreamForm({ id: null, name: '', capacity: '' });
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[]> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to update stream');
    },
  });

  const deleteStreamMutation = useMutation({
    mutationFn: (id: number) => studentsApi.deleteStream(id),
    onSuccess: () => {
      toast.success('Stream deleted');
      qc.invalidateQueries({ queryKey: ['streams', classroomId] });
      qc.invalidateQueries({ queryKey: ['classroom', classroomId] });
    },
    onError: () => toast.error('Failed to delete stream — students assigned to it will be unassigned instead if you retry.'),
  });

  const openCreateStream = () => {
    setStreamForm({ id: null, name: '', capacity: '' });
    setStreamModalOpen(true);
  };

  const openEditStream = (s: Stream) => {
    setStreamForm({ id: s.id, name: s.name, capacity: s.capacity != null ? String(s.capacity) : '' });
    setStreamModalOpen(true);
  };

  const handleSaveStream = () => {
    if (!streamForm.name.trim()) {
      toast.error('Stream name is required');
      return;
    }
    const capacity = streamForm.capacity.trim() ? Number(streamForm.capacity) : null;
    if (streamForm.id) {
      updateStreamMutation.mutate({ id: streamForm.id, data: { name: streamForm.name.trim(), capacity } });
    } else {
      createStreamMutation.mutate({ classroom: classroomId, name: streamForm.name.trim(), capacity });
    }
  };

  const updateMutation = useMutation({
    mutationFn: (data: EditClassroomForm) => studentsApi.updateClassroom(classroomId, data),
    onSuccess: () => {
      toast.success('Classroom updated');
      qc.invalidateQueries({ queryKey: ['classroom', classroomId] });
      qc.invalidateQueries({ queryKey: ['classrooms'] });
      setEditing(false);
    },
    onError: () => toast.error('Failed to update classroom'),
  });

  const deleteMutationClassroom = useMutation({
    mutationFn: () => studentsApi.deleteClassroom(classroomId),
    onSuccess: () => {
      toast.success('Classroom deleted');
      qc.invalidateQueries({ queryKey: ['classrooms'] });
      navigate('/classrooms');
    },
    onError: () => toast.error('Failed to delete classroom — it may still have students enrolled'),
  });

  const createMutation = useMutation({
    mutationFn: (data: { teacher: number; classroom: number; subject: number }) =>
      assignmentsApi.create(data),
    onSuccess: () => {
      toast.success('Teacher assigned');
      qc.invalidateQueries({ queryKey: ['assignments'] });
      qc.invalidateQueries({ queryKey: ['classroom', classroomId] });
      qc.invalidateQueries({ queryKey: ['classrooms'] });
      setModalOpen(false);
      setTeacherId('');
      setSubjectId('');
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[]> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to assign teacher — they may already be assigned to this subject here.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (assignmentId: number) => assignmentsApi.delete(assignmentId),
    onSuccess: () => {
      toast.success('Assignment removed');
      qc.invalidateQueries({ queryKey: ['assignments'] });
      qc.invalidateQueries({ queryKey: ['classroom', classroomId] });
      qc.invalidateQueries({ queryKey: ['classrooms'] });
    },
    onError: () => toast.error('Failed to remove assignment'),
  });

  const handleAssign = () => {
    if (!teacherId || !subjectId) {
      toast.error('Select both a teacher and a subject');
      return;
    }
    createMutation.mutate({
      teacher: Number(teacherId),
      classroom: classroomId,
      subject: Number(subjectId),
    });
  };

  const startEdit = () => {
    if (!classroom) return;
    setEditName(classroom.name);
    setEditYear(classroom.academic_year);
    setEditing(true);
  };

  if (isLoading) return <LoadingPage />;
  if (!classroom) return <div className="text-muted">Classroom not found.</div>;

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div>
        <button onClick={() => navigate('/classrooms')} className="text-secondary hover:text-primary text-sm transition-colors mb-2">
          ← Back to Classrooms
        </button>
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-azure-500/15 flex items-center justify-center flex-shrink-0">
            <School size={20} className="text-azure-400" />
          </div>
          {editing ? (
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="flex flex-col sm:flex-row gap-2 flex-1">
                <input
                  className="input flex-1"
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  placeholder="Classroom name"
                />
                <input
                  className="input w-28"
                  value={editYear}
                  onChange={e => setEditYear(e.target.value)}
                  placeholder="Year e.g. 2024"
                />
              </div>
              <Button size="sm" loading={updateMutation.isPending}
                onClick={() => updateMutation.mutate({ name: editName, academic_year: editYear })}>
                <Save size={13} /> Save
              </Button>
              <button onClick={() => setEditing(false)} className="text-secondary hover:text-primary transition-colors p-1">
                <X size={16} />
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between flex-1 min-w-0 gap-3">
              <div>
                <h1 className="page-title">{classroom.name}</h1>
                <p className="text-muted text-sm">
                  {classroom.grade_level_name} · {EDUCATION_LEVEL_LABELS[classroom.education_level]} · {classroom.academic_year}
                </p>
              </div>
              {(canEdit || canDelete) && (
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {canEdit && (
                    <button onClick={startEdit}
                      className="p-2 rounded-xl text-secondary hover:text-azure-400 hover:bg-azure-500/10 transition-colors" title="Edit classroom">
                      <Edit2 size={14} />
                    </button>
                  )}
                  {canDelete && (
                    <button
                      onClick={() => {
                        if (confirm(`Delete "${classroom.name}"? This cannot be undone. All teacher assignments for this classroom will be removed.`))
                          deleteMutationClassroom.mutate();
                      }}
                      className="p-2 rounded-xl text-secondary hover:text-rose-400 hover:bg-rose-500/10 transition-colors" title="Delete classroom">
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-3 gap-3">
        <button onClick={() => navigate(`/analytics/class?classroom=${classroom.id}`)}
          className="card-hover p-4 flex flex-col items-center gap-1.5 text-center">
          <BarChart3 size={18} className="text-azure-400" />
          <span className="text-xs font-medium text-primary">Analytics</span>
        </button>
        <button onClick={() => navigate(`/students?classroom=${classroom.id}`)}
          className="card-hover p-4 flex flex-col items-center gap-1.5 text-center">
          <Users size={18} className="text-azure-400" />
          <span className="text-xs font-medium text-primary">{classroom.student_count} Students</span>
        </button>
        <button onClick={() => navigate(`/reports?classroom=${classroom.id}`)}
          className="card-hover p-4 flex flex-col items-center gap-1.5 text-center">
          <FileText size={18} className="text-azure-400" />
          <span className="text-xs font-medium text-primary">Report</span>
        </button>
      </div>

      {/* Teacher assignments */}
      <div className="card p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="section-title">Teacher Assignments</h2>
            <p className="text-muted text-xs mt-0.5">Which teacher teaches which subject in this classroom</p>
          </div>
          {isAdmin && (
            <Button size="sm" onClick={() => setModalOpen(true)}>
              <UserPlus size={13} /> Assign Teacher
            </Button>
          )}
        </div>

        {assignmentsLoading ? (
          <LoadingPage />
        ) : assignments.length === 0 ? (
          <div className="text-center py-8 text-secondary">
            <p className="text-sm">No teachers assigned yet.</p>
            <p className="text-xs mt-1">Students in this classroom won't show up for any teacher until you assign one.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {assignments.map(a => (
              <div key={a.id} className="flex items-center justify-between gap-3 bg-surface-900 rounded-xl p-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
                    style={{ backgroundColor: a.subject_color + '25', color: a.subject_color }}
                  >
                    {a.subject_code.slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-primary truncate">{a.teacher_name}</p>
                    <p className="text-xs text-secondary truncate">{a.subject_name} · {a.teacher_email}</p>
                  </div>
                </div>
                {isAdmin && (
                  <button
                    onClick={() => deleteMutation.mutate(a.id)}
                    className="text-secondary hover:text-rose-400 transition-colors p-1.5 flex-shrink-0"
                    title="Remove assignment"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Streams (sections within this classroom, e.g. A / B) */}
      <div className="card p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="section-title">Streams</h2>
            <p className="text-muted text-xs mt-0.5">Sections within this classroom (e.g. "A", "B") — used to group and bulk-assign students</p>
          </div>
          {canAddStream && (
            <Button size="sm" onClick={openCreateStream}>
              <Plus size={13} /> Add Stream
            </Button>
          )}
        </div>

        {streamsLoading ? (
          <LoadingPage />
        ) : streams.length === 0 ? (
          <div className="text-center py-8 text-secondary">
            <p className="text-sm">No streams yet.</p>
            <p className="text-xs mt-1">Add streams like "A" or "B" to organize students within this classroom.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {streams.map(s => (
              <div key={s.id} className="flex items-center justify-between gap-3 bg-surface-900 rounded-xl p-3">
                <button
                  onClick={() => navigate(`/students?classroom=${classroomId}&stream=${s.id}`)}
                  className="flex items-center gap-3 min-w-0 text-left flex-1"
                >
                  <div className="w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center flex-shrink-0">
                    <Layers size={14} className="text-violet-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-primary truncate">Stream {s.name}</p>
                    <p className="text-xs text-secondary truncate">
                      {s.student_count} student{s.student_count === 1 ? '' : 's'}
                      {s.capacity != null ? ` · capacity ${s.capacity}` : ''}
                      {!s.is_active ? ' · inactive' : ''}
                    </p>
                  </div>
                </button>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {canEditStream && (
                    <button
                      onClick={() => openEditStream(s)}
                      className="text-secondary hover:text-azure-400 transition-colors p-1.5"
                      title="Edit stream"
                    >
                      <Edit2 size={13} />
                    </button>
                  )}
                  {canDeleteStream && (
                    <button
                      onClick={() => {
                        if (confirm(`Delete stream "${s.name}"? Students in it will become unassigned (not deleted).`))
                          deleteStreamMutation.mutate(s.id);
                      }}
                      className="text-secondary hover:text-rose-400 transition-colors p-1.5"
                      title="Delete stream"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Assign teacher modal */}
      {isAdmin && (
        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Assign Teacher"
          footer={
            <>
              <Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
              <Button onClick={handleAssign} loading={createMutation.isPending}>
                <Plus size={14} /> Assign
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <Select
              label="Teacher"
              value={teacherId}
              onChange={e => setTeacherId(e.target.value)}
              options={[
                { value: '', label: 'Select teacher…' },
                ...teachers.map(t => ({
                  value: t.id,
                  label: t.role === 'super_admin'
                    ? `${t.full_name} (Admin)`
                    : t.full_name,
                })),
              ]}
            />
            <Select
              label="Subject"
              value={subjectId}
              onChange={e => setSubjectId(e.target.value)}
              options={[
                { value: '', label: 'Select subject…' },
                ...subjects.map(s => ({ value: s.id, label: `${s.name} (${s.code})` })),
              ]}
            />
            <p className="text-xs text-secondary">
              Assigns a teacher or admin to this classroom for the selected subject. They will gain visibility into this classroom's students and exams for that subject.
            </p>
          </div>
        </Modal>
      )}

      {/* Create/edit stream modal */}
      <Modal
        open={streamModalOpen}
        onClose={() => setStreamModalOpen(false)}
        title={streamForm.id ? 'Edit Stream' : 'Add Stream'}
        footer={
          <>
            <Button variant="secondary" onClick={() => setStreamModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveStream} loading={createStreamMutation.isPending || updateStreamMutation.isPending}>
              <Save size={14} /> {streamForm.id ? 'Save' : 'Create'}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Input
            label="Stream Name"
            placeholder="e.g. A, B, Blue"
            value={streamForm.name}
            onChange={e => setStreamForm(f => ({ ...f, name: e.target.value }))}
          />
          <Input
            label="Capacity (optional)"
            type="number"
            placeholder="e.g. 40"
            value={streamForm.capacity}
            onChange={e => setStreamForm(f => ({ ...f, capacity: e.target.value }))}
          />
        </div>
      </Modal>
    </div>
  );
}

