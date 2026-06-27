import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { GraduationCap, Search, Plus } from 'lucide-react';
import { studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import type { StudentProfile, Classroom, PaginatedResponse } from '../../types';

export default function StudentsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [activeOnly, setActiveOnly] = useState(true);
  const classroomFilter = searchParams.get('classroom') ?? '';
  const { getPage } = useSiteSettingsStore();
  const pageConfig = getPage('students');
  const pageSize = pageConfig.page_size;

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data, isLoading } = useQuery<PaginatedResponse<StudentProfile>>({
    queryKey: ['students', search, classroomFilter, page, pageSize, activeOnly],
    queryFn: () => studentsApi.students({
      search: search || undefined,
      classroom: classroomFilter || undefined,
      is_active: activeOnly ? true : undefined,
      page,
      page_size: pageSize,
    }).then(r => r.data),
  });
  const students = data?.results ?? [];

  const handleSearch = (val: string) => { setSearch(val); setPage(1); };
  const handleClassroomFilter = (val: string) => {
    setSearchParams(val ? { classroom: val } : {});
    setPage(1);
  };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Students</h1>
          <p className="text-muted mt-0.5">{data?.count ?? 0} enrolled</p>
        </div>
        <Button onClick={() => navigate('/students/new')} size="sm">
          <Plus size={14} /> <span className="hidden sm:inline">Add</span> Student
        </Button>
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
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-xs font-bold text-primary flex-shrink-0">
                  {s.first_name?.[0]}{s.last_name?.[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-display font-semibold text-primary text-sm truncate">{s.full_name}</p>
                  <p className="text-xs text-secondary truncate">{s.student_id} · {s.classroom_name ?? 'No class'}</p>
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
                    {['Student', 'ID', 'Class / Level', 'Region', 'Status', ''].map(h => (
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
    </div>
  );
}
