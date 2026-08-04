import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { GraduationCap, Search, Plus, Layers, X, ArrowUp, ArrowDown, ArrowUpDown, Edit2, Trash2, Copy, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';
import { studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination, Select, Modal } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useCanManage } from '../../hooks/useCanManage';
import type { StudentProfile, Classroom, Stream, GradeLevel, DuplicateGroup, DuplicateMatchField, PaginatedResponse } from '../../types';

// Column key -> backend `ordering` field. Kept in sync with
// StudentProfileViewSet.ordering_fields on the backend.
const SORT_COLUMNS: Record<string, string> = {
  name: 'user__last_name',
  id: 'student_id',
  classroom: 'classroom__name',
  status: 'is_active',
};

const DUPLICATE_MATCH_OPTIONS: { value: DuplicateMatchField; label: string }[] = [
  { value: 'name', label: 'Full Name' },
  { value: 'email', label: 'Email' },
  { value: 'index_number', label: 'Index Number' },
  { value: 'parent_phone', label: 'Parent Phone' },
  { value: 'date_of_birth', label: 'Date of Birth' },
];

export default function StudentsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [activeOnly, setActiveOnly] = useState(true);
  const [ordering, setOrdering] = useState('');
  const classroomFilter = searchParams.get('classroom') ?? '';
  const streamFilter = searchParams.get('stream') ?? '';
  const gradeLevelFilter = searchParams.get('grade_level') ?? '';
  const { getPage } = useSiteSettingsStore();
  const pageConfig = getPage('students');
  const pageSize = pageConfig.page_size;
  const canAdd = useCanManage('students', 'add');
  const canBulkAssign = useCanManage('students', 'edit');
  const canDelete = useCanManage('students', 'delete');
  const canEdit = useCanManage('students', 'edit');
  const canSelect = canBulkAssign || canDelete;

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignStreamId, setAssignStreamId] = useState('');
  const [duplicatesOpen, setDuplicatesOpen] = useState(false);
  const [duplicatesBy, setDuplicatesBy] = useState<DuplicateMatchField>('name');

  const { data: gradeLevelsData } = useQuery<GradeLevel[] | PaginatedResponse<GradeLevel>>({
    queryKey: ['grade-levels'],
    queryFn: () => studentsApi.gradeLevels().then(r => r.data),
  });
  const gradeLevels: GradeLevel[] = Array.isArray(gradeLevelsData)
    ? gradeLevelsData : (gradeLevelsData as PaginatedResponse<GradeLevel>)?.results ?? [];

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  // Streams are scoped to a single classroom, so this filter/dropdown only
  // makes sense once a classroom is selected.
  const { data: streamsData } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams-for-filter', classroomFilter],
    queryFn: () => studentsApi.streams({ classroom: classroomFilter, page_size: 200 }).then(r => r.data),
    enabled: !!classroomFilter,
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const { data, isLoading } = useQuery<PaginatedResponse<StudentProfile>>({
    queryKey: ['students', search, classroomFilter, streamFilter, gradeLevelFilter, page, pageSize, activeOnly, ordering],
    queryFn: () => studentsApi.students({
      search: search || undefined,
      classroom: classroomFilter || undefined,
      stream: streamFilter || undefined,
      classroom__grade_level: gradeLevelFilter || undefined,
      is_active: activeOnly ? true : undefined,
      ordering: ordering || undefined,
      page,
      page_size: pageSize,
    }).then(r => r.data),
  });
  const students = data?.results ?? [];

  // Duplicate finder — reuses whatever classroom/stream/grade-level/active
  // filters are already set on the list, same as the backend's duplicates()
  // action does via filter_queryset(). Only fetched while the modal is open.
  const { data: duplicatesData, isLoading: duplicatesLoading } = useQuery<{ by: string; groups: DuplicateGroup[] }>({
    queryKey: ['students-duplicates', duplicatesBy, classroomFilter, streamFilter, gradeLevelFilter, activeOnly],
    queryFn: () => studentsApi.duplicateStudents({
      by: duplicatesBy,
      classroom: classroomFilter || undefined,
      stream: streamFilter || undefined,
      classroom__grade_level: gradeLevelFilter || undefined,
      is_active: activeOnly ? true : undefined,
    }).then(r => r.data),
    enabled: duplicatesOpen,
  });
  const duplicateGroups = duplicatesData?.groups ?? [];

  // Clear selection whenever the underlying list changes, so a bulk action
  // can never accidentally target students no longer in view.
  useEffect(() => { setSelected(new Set()); }, [search, classroomFilter, streamFilter, gradeLevelFilter, page, activeOnly, ordering]);

  const handleSort = (columnKey: string) => {
    const field = SORT_COLUMNS[columnKey];
    setOrdering(prev => {
      if (prev === field) return `-${field}`;
      if (prev === `-${field}`) return '';
      return field;
    });
    setPage(1);
  };

  const sortIcon = (columnKey: string) => {
    const field = SORT_COLUMNS[columnKey];
    if (ordering === field) return <ArrowUp size={12} />;
    if (ordering === `-${field}`) return <ArrowDown size={12} />;
    return <ArrowUpDown size={12} className="opacity-30" />;
  };

  const bulkAssignMutation = useMutation({
    mutationFn: (data: { student_ids: number[]; stream_id: number | null }) => studentsApi.bulkAssignStream(data),
    onSuccess: (res) => {
      const updated = (res.data as { updated?: number })?.updated ?? selected.size;
      toast.success(`Assigned ${updated} student${updated === 1 ? '' : 's'}`);
      qc.invalidateQueries({ queryKey: ['students'] });
      qc.invalidateQueries({ queryKey: ['streams'] });
      qc.invalidateQueries({ queryKey: ['streams-for-filter'] });
      setAssignModalOpen(false);
      setAssignStreamId('');
      setSelected(new Set());
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? 'Failed to assign students to stream');
    },
  });

  const handleSearch = (val: string) => { setSearch(val); setPage(1); };
  const handleClassroomFilter = (val: string) => {
    const next: Record<string, string> = {};
    if (gradeLevelFilter) next.grade_level = gradeLevelFilter;
    if (val) next.classroom = val;
    // Changing classroom invalidates any stream filter from the old classroom.
    setSearchParams(next);
    setPage(1);
  };
  const handleStreamFilter = (val: string) => {
    const next: Record<string, string> = {};
    if (gradeLevelFilter) next.grade_level = gradeLevelFilter;
    if (classroomFilter) next.classroom = classroomFilter;
    if (val) next.stream = val;
    setSearchParams(next);
    setPage(1);
  };
  const handleGradeLevelFilter = (val: string) => {
    const next: Record<string, string> = {};
    if (val) next.grade_level = val;
    // Grade level is a coarser filter than classroom/stream — picking a
    // new one clears both, since the old classroom may not belong to it.
    setSearchParams(next);
    setPage(1);
  };

  const deleteMutation = useMutation({
    mutationFn: (studentId: number) => studentsApi.deleteStudent(studentId),
    onSuccess: () => {
      toast.success('Student deleted');
      qc.invalidateQueries({ queryKey: ['students'] });
      qc.invalidateQueries({ queryKey: ['students-duplicates'] });
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? 'Failed to delete student');
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (studentIds: number[]) => studentsApi.bulkDeleteStudents(studentIds),
    onSuccess: (res) => {
      const deletedCount = (res.data as { deleted?: number })?.deleted ?? selected.size;
      toast.success(`Deleted ${deletedCount} student${deletedCount === 1 ? '' : 's'}`);
      qc.invalidateQueries({ queryKey: ['students'] });
      qc.invalidateQueries({ queryKey: ['students-duplicates'] });
      setSelected(new Set());
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? 'Failed to delete students');
    },
  });

  const handleDeleteOne = (s: StudentProfile) => {
    if (confirm(`Delete ${s.full_name}? This cannot be undone.`)) deleteMutation.mutate(s.id);
  };
  const handleBulkDelete = () => {
    if (confirm(`Delete ${selected.size} selected student${selected.size === 1 ? '' : 's'}? This cannot be undone.`)) {
      bulkDeleteMutation.mutate(Array.from(selected));
    }
  };

  // Duplicate-group cleanup: keeps whichever record has the lowest id
  // (the earliest-created one, a reasonable proxy for "the original")
  // and deletes the rest of the group in one call.
  const handleDeleteGroupExtras = (group: DuplicateGroup) => {
    const sorted = [...group.students].sort((a, b) => a.id - b.id);
    const [keep, ...rest] = sorted;
    if (!keep || rest.length === 0) return;
    if (confirm(`Keep "${keep.full_name}" (${keep.student_id}) and delete the other ${rest.length} matching record${rest.length === 1 ? '' : 's'}? This cannot be undone.`)) {
      bulkDeleteMutation.mutate(rest.map(s => s.id));
    }
  };

  const toggleSelected = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const toggleSelectAll = () => {
    setSelected(prev => prev.size === students.length ? new Set() : new Set(students.map(s => s.id)));
  };

  const handleBulkAssign = () => {
    bulkAssignMutation.mutate({
      student_ids: Array.from(selected),
      stream_id: assignStreamId ? Number(assignStreamId) : null,
    });
  };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Students</h1>
          <p className="text-muted mt-0.5">{data?.count ?? 0} enrolled</p>
        </div>
        <div className="flex items-center gap-2">
          {(canEdit || canDelete) && (
            <Button variant="secondary" size="sm" onClick={() => setDuplicatesOpen(true)}>
              <Copy size={14} /> <span className="hidden sm:inline">Find</span> Duplicates
            </Button>
          )}
          {canAdd && (
            <Button onClick={() => navigate('/students/new')} size="sm">
              <Plus size={14} /> <span className="hidden sm:inline">Add</span> Student
            </Button>
          )}
        </div>
      </div>

      {/* Search + filters */}
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
          <input
            className="input pl-10 w-full"
            placeholder="Search by name, ID or email…"
            value={search}
            onChange={e => handleSearch(e.target.value)}
          />
        </div>
        <select
          className="input w-full sm:w-44"
          value={gradeLevelFilter}
          onChange={e => handleGradeLevelFilter(e.target.value)}
        >
          <option value="">All Grade Levels</option>
          {gradeLevels.map(g => (
            <option key={g.id} value={g.id}>{g.short_name || g.name}</option>
          ))}
        </select>
        <select
          className="input w-full sm:w-52"
          value={classroomFilter}
          onChange={e => handleClassroomFilter(e.target.value)}
        >
          <option value="">All Classrooms</option>
          {classrooms
            .filter(c => !gradeLevelFilter || String(c.grade_level) === gradeLevelFilter)
            .map(c => (
              <option key={c.id} value={c.id}>{c.name} ({c.academic_year})</option>
            ))}
        </select>
        {classroomFilter && (
          <select
            className="input w-full sm:w-44"
            value={streamFilter}
            onChange={e => handleStreamFilter(e.target.value)}
          >
            <option value="">All Streams</option>
            {streams.map(s => (
              <option key={s.id} value={s.id}>Stream {s.name}</option>
            ))}
          </select>
        )}
        <label className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-800 border border-surface cursor-pointer whitespace-nowrap text-sm text-secondary hover:text-primary transition-colors">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={e => { setActiveOnly(e.target.checked); setPage(1); }}
            className="w-3.5 h-3.5"
          />
          Active only
        </label>
      </div>

      {/* Bulk action bar. Assign-to-stream only makes sense once a classroom
          is chosen, since a stream always belongs to exactly one classroom;
          delete has no such requirement. */}
      {canSelect && selected.size > 0 && (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-3 bg-azure-500/10 border border-azure-500/25 rounded-xl px-4 py-2.5">
            <p className="text-sm text-primary">
              <span className="font-display font-semibold">{selected.size}</span> student{selected.size === 1 ? '' : 's'} selected
            </p>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="secondary" onClick={() => setSelected(new Set())}>
                <X size={13} /> Clear
              </Button>
              {canDelete && (
                <Button size="sm" variant="secondary" className="!text-rose-400" onClick={handleBulkDelete} loading={bulkDeleteMutation.isPending}>
                  <Trash2 size={13} /> Delete
                </Button>
              )}
              {canBulkAssign && (
                <Button
                  size="sm"
                  onClick={() => setAssignModalOpen(true)}
                  disabled={!classroomFilter}
                  title={!classroomFilter ? 'Filter by a classroom above to assign a stream' : undefined}
                >
                  <Layers size={13} /> Assign to Stream
                </Button>
              )}
            </div>
          </div>
          {canBulkAssign && !classroomFilter && (
            <p className="text-xs text-secondary px-1">
              Filter by a classroom above to enable "Assign to Stream" (a stream belongs to one classroom).
            </p>
          )}
        </div>
      )}

      {isLoading ? <LoadingPage /> : students.length === 0 ? (
        <EmptyState icon={<GraduationCap size={36} />} title="No students found"
          message={search ? 'Try a different search term.' : 'Add your first student to get started.'} />
      ) : (
        <>
          {/* Mobile card list */}
          <div className="flex flex-col gap-2 md:hidden">
            {students.map(s => (
              <div
                key={s.id}
                className="card-hover p-4 flex items-center gap-3"
                onClick={() => navigate(`/students/${s.id}`)}
              >
                {canSelect && (
                  <input
                    type="checkbox"
                    className="w-4 h-4 flex-shrink-0"
                    checked={selected.has(s.id)}
                    onClick={e => e.stopPropagation()}
                    onChange={() => toggleSelected(s.id)}
                  />
                )}
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-xs font-bold text-primary flex-shrink-0">
                  {s.first_name?.[0]}{s.last_name?.[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-display font-semibold text-primary text-sm truncate">{s.full_name}</p>
                  <p className="text-xs text-secondary truncate">
                    {s.student_id} · {s.classroom_name ?? 'No class'}{s.stream_name ? ` · Stream ${s.stream_name}` : ''}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  <span className={`badge text-[10px] ${s.is_active ? 'badge-green' : 'badge-rose'}`}>
                    {s.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <div className="flex items-center gap-2">
                    {canEdit && (
                      <button
                        className="text-secondary hover:text-primary transition-colors"
                        onClick={e => { e.stopPropagation(); navigate(`/students/${s.id}?edit=1`); }}
                      >
                        <Edit2 size={12} />
                      </button>
                    )}
                    {canDelete && (
                      <button
                        className="text-secondary hover:text-rose-400 transition-colors"
                        onClick={e => { e.stopPropagation(); handleDeleteOne(s); }}
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                  <button
                    className="text-[10px] text-azure-400 font-display font-medium"
                    onClick={e => { e.stopPropagation(); navigate(`/analytics/student/${s.id}`); }}
                  >
                    Analytics →
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop table */}
          <div className="hidden md:block card p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface">
                    {canSelect && (
                      <th className="py-3 px-4 w-10">
                        <input
                          type="checkbox"
                          className="w-3.5 h-3.5"
                          checked={students.length > 0 && selected.size === students.length}
                          onChange={toggleSelectAll}
                        />
                      </th>
                    )}
                    {([
                      ['name', 'Student'],
                      ['id', 'ID'],
                      ['classroom', 'Class / Level'],
                      [null, 'Stream'],
                      [null, 'Region'],
                      ['status', 'Status'],
                      [null, ''],
                    ] as [string | null, string][]).map(([sortKey, label]) => (
                      <th
                        key={label || 'actions'}
                        className={`text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap ${sortKey ? 'cursor-pointer select-none hover:text-primary transition-colors' : ''}`}
                        onClick={sortKey ? () => handleSort(sortKey) : undefined}
                      >
                        {sortKey ? (
                          <span className="inline-flex items-center gap-1">{label} {sortIcon(sortKey)}</span>
                        ) : label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {students.map(s => (
                    <tr
                      key={s.id}
                      className="border-b border-surface hover:bg-surface-800/50 transition-colors cursor-pointer"
                      onClick={() => navigate(`/students/${s.id}`)}
                    >
                      {canSelect && (
                        <td className="py-3 px-4" onClick={e => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            className="w-3.5 h-3.5"
                            checked={selected.has(s.id)}
                            onChange={() => toggleSelected(s.id)}
                          />
                        </td>
                      )}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-[10px] font-bold text-primary flex-shrink-0">
                            {s.first_name?.[0]}{s.last_name?.[0]}
                          </div>
                          <span className="font-medium text-primary">{s.full_name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-mono text-xs text-secondary bg-surface-900 px-2 py-0.5 rounded">{s.student_id}</span>
                      </td>
                      <td className="py-3 px-4">
                        <div>
                          <p className="text-primary text-xs">{s.classroom_name ?? '—'}</p>
                          {s.grade_level && <p className="text-secondary text-[11px]">{s.grade_level}</p>}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        {s.stream_name ? (
                          <span className="badge badge-violet text-[10px]">{s.stream_name}</span>
                        ) : (
                          <span className="text-secondary text-xs">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-secondary text-xs">{s.region || '—'}</td>
                      <td className="py-3 px-4">
                        <span className={`badge ${s.is_active ? 'badge-green' : 'badge-rose'}`}>
                          {s.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3 justify-end">
                          <button
                            className="text-xs text-azure-400 hover:text-azure-300 font-display font-medium transition-colors"
                            onClick={e => { e.stopPropagation(); navigate(`/analytics/student/${s.id}`); }}
                          >
                            Analytics →
                          </button>
                          {canEdit && (
                            <button
                              className="text-secondary hover:text-primary transition-colors"
                              title="Edit"
                              onClick={e => { e.stopPropagation(); navigate(`/students/${s.id}?edit=1`); }}
                            >
                              <Edit2 size={13} />
                            </button>
                          )}
                          {canDelete && (
                            <button
                              className="text-secondary hover:text-rose-400 transition-colors"
                              title="Delete"
                              onClick={e => { e.stopPropagation(); handleDeleteOne(s); }}
                            >
                              <Trash2 size={13} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-surface px-4">
              <Pagination
                page={page}
                pageSize={pageSize}
                total={data?.count ?? 0}
                onChange={setPage}
              />
            </div>
          </div>

          {/* Mobile pagination */}
          <div className="md:hidden">
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data?.count ?? 0}
              onChange={setPage}
            />
          </div>
        </>
      )}

      {/* Bulk assign-to-stream modal */}
      <Modal
        open={assignModalOpen}
        onClose={() => setAssignModalOpen(false)}
        title="Assign to Stream"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAssignModalOpen(false)}>Cancel</Button>
            <Button onClick={handleBulkAssign} loading={bulkAssignMutation.isPending}>
              <Layers size={14} /> Assign {selected.size} Student{selected.size === 1 ? '' : 's'}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Select
            label="Stream"
            value={assignStreamId}
            onChange={e => setAssignStreamId(e.target.value)}
            options={[
              { value: '', label: 'No stream (unassign)' },
              ...streams.map(s => ({ value: s.id, label: `Stream ${s.name}` })),
            ]}
          />
          <p className="text-xs text-secondary">
            Moves all {selected.size} selected student{selected.size === 1 ? '' : 's'} into this stream. Choosing
            "No stream" removes their current stream assignment instead.
          </p>
        </div>
      </Modal>

      {/* Duplicate finder */}
      <Modal
        open={duplicatesOpen}
        onClose={() => setDuplicatesOpen(false)}
        title="Find Duplicate Students"
        size="xl"
        footer={<Button variant="secondary" onClick={() => setDuplicatesOpen(false)}>Close</Button>}
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-col sm:flex-row sm:items-end gap-3">
            <Select
              label="Match by"
              value={duplicatesBy}
              onChange={e => setDuplicatesBy(e.target.value as DuplicateMatchField)}
              options={DUPLICATE_MATCH_OPTIONS}
              className="sm:w-56"
            />
            <p className="text-xs text-secondary pb-2.5">
              Uses the same Classroom / Stream / Grade Level / Active filters set on the list behind this modal.
            </p>
          </div>

          {duplicatesLoading ? (
            <LoadingPage />
          ) : duplicateGroups.length === 0 ? (
            <EmptyState
              icon={<Copy size={32} />}
              title="No duplicates found"
              message={`No students share the same ${DUPLICATE_MATCH_OPTIONS.find(o => o.value === duplicatesBy)?.label.toLowerCase()} under the current filters.`}
            />
          ) : (
            <div className="flex flex-col gap-3">
              {duplicateGroups.map(group => (
                <div key={`${duplicatesBy}-${group.key}`} className="card p-3">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <AlertTriangle size={14} className="text-amber-400" />
                      <span className="font-display font-semibold text-sm text-primary">{group.key || '—'}</span>
                      <span className="badge badge-rose text-[10px]">{group.count} matches</span>
                    </div>
                    {canDelete && (
                      <Button
                        size="sm"
                        variant="secondary"
                        className="!text-rose-400"
                        onClick={() => handleDeleteGroupExtras(group)}
                        loading={bulkDeleteMutation.isPending}
                      >
                        <Trash2 size={12} /> Keep oldest, delete rest
                      </Button>
                    )}
                  </div>
                  <div className="flex flex-col divide-y divide-surface">
                    {group.students.map(s => (
                      <div key={s.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                        <div className="min-w-0">
                          <p className="text-primary font-medium truncate">{s.full_name}</p>
                          <p className="text-secondary text-xs truncate">
                            {s.student_id} · {s.classroom_name ?? 'No class'}{s.stream_name ? ` · Stream ${s.stream_name}` : ''} · {s.email}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {canEdit && (
                            <button
                              className="text-secondary hover:text-primary transition-colors"
                              title="Edit"
                              onClick={() => { setDuplicatesOpen(false); navigate(`/students/${s.id}?edit=1`); }}
                            >
                              <Edit2 size={13} />
                            </button>
                          )}
                          {canDelete && (
                            <button
                              className="text-secondary hover:text-rose-400 transition-colors"
                              title="Delete"
                              onClick={() => handleDeleteOne(s)}
                            >
                              <Trash2 size={13} />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
