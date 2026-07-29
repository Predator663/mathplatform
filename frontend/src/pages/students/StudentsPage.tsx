import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { GraduationCap, Search, Plus, Layers, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination, Select, Modal } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { useCanManage } from '../../hooks/useCanManage';
import type { StudentProfile, Classroom, Stream, PaginatedResponse } from '../../types';

export default function StudentsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [activeOnly, setActiveOnly] = useState(true);
  const classroomFilter = searchParams.get('classroom') ?? '';
  const streamFilter = searchParams.get('stream') ?? '';
  const { getPage } = useSiteSettingsStore();
  const pageConfig = getPage('students');
  const pageSize = pageConfig.page_size;
  const canAdd = useCanManage('students', 'add');
  const canBulkAssign = useCanManage('students', 'edit');

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignStreamId, setAssignStreamId] = useState('');

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
    queryKey: ['students', search, classroomFilter, streamFilter, page, pageSize, activeOnly],
    queryFn: () => studentsApi.students({
      search: search || undefined,
      classroom: classroomFilter || undefined,
      stream: streamFilter || undefined,
      is_active: activeOnly ? true : undefined,
      page,
      page_size: pageSize,
    }).then(r => r.data),
  });
  const students = data?.results ?? [];

  // Clear selection whenever the underlying list changes, so a bulk action
  // can never accidentally target students no longer in view.
  useEffect(() => { setSelected(new Set()); }, [search, classroomFilter, streamFilter, page, activeOnly]);

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
    if (val) next.classroom = val;
    // Changing classroom invalidates any stream filter from the old classroom.
    setSearchParams(next);
    setPage(1);
  };
  const handleStreamFilter = (val: string) => {
    const next: Record<string, string> = {};
    if (classroomFilter) next.classroom = classroomFilter;
    if (val) next.stream = val;
    setSearchParams(next);
    setPage(1);
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
        {canAdd && (
          <Button onClick={() => navigate('/students/new')} size="sm">
            <Plus size={14} /> <span className="hidden sm:inline">Add</span> Student
          </Button>
        )}
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
          className="input w-full sm:w-52"
          value={classroomFilter}
          onChange={e => handleClassroomFilter(e.target.value)}
        >
          <option value="">All Classrooms</option>
          {classrooms.map(c => (
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

      {/* Bulk action bar — only meaningful once a classroom is chosen, since
          a stream always belongs to exactly one classroom. */}
      {canBulkAssign && classroomFilter && selected.size > 0 && (
        <div className="flex items-center justify-between gap-3 bg-azure-500/10 border border-azure-500/25 rounded-xl px-4 py-2.5">
          <p className="text-sm text-primary">
            <span className="font-display font-semibold">{selected.size}</span> student{selected.size === 1 ? '' : 's'} selected
          </p>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={() => setSelected(new Set())}>
              <X size={13} /> Clear
            </Button>
            <Button size="sm" onClick={() => setAssignModalOpen(true)}>
              <Layers size={13} /> Assign to Stream
            </Button>
          </div>
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
                {canBulkAssign && classroomFilter && (
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
                    {canBulkAssign && classroomFilter && (
                      <th className="py-3 px-4 w-10">
                        <input
                          type="checkbox"
                          className="w-3.5 h-3.5"
                          checked={students.length > 0 && selected.size === students.length}
                          onChange={toggleSelectAll}
                        />
                      </th>
                    )}
                    {['Student', 'ID', 'Class / Level', 'Stream', 'Region', 'Status', ''].map(h => (
                      <th key={h} className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-4 whitespace-nowrap">
                        {h}
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
                      {canBulkAssign && classroomFilter && (
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
                        <button
                          className="text-xs text-azure-400 hover:text-azure-300 font-display font-medium transition-colors"
                          onClick={e => { e.stopPropagation(); navigate(`/analytics/student/${s.id}`); }}
                        >
                          Analytics →
                        </button>
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
    </div>
  );
}
