import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { School, Plus, Users, BarChart3, FileText } from 'lucide-react';
import { studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import { EDUCATION_LEVEL_LABELS } from '../../utils';
import type { Classroom, PaginatedResponse } from '../../types';

const STREAM_COLORS: Record<string, string> = {
  science:  'badge-green',
  arts:     'badge-violet',
  commerce: 'badge-amber',
  technical:'badge-blue',
  general:  '',
};

export default function ClassroomsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { getPage } = useSiteSettingsStore();
  const pageSize = getPage('classrooms').page_size;

  const { data, isLoading } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms', page, pageSize],
    queryFn: () => studentsApi.classrooms({ page, page_size: pageSize }).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(data)
    ? data : (data as PaginatedResponse<Classroom>)?.results ?? [];
  const total: number = Array.isArray(data) ? data.length : (data as PaginatedResponse<Classroom>)?.count ?? 0;

  // Group by academic year
  const byYear = classrooms.reduce((acc, c) => {
    if (!acc[c.academic_year]) acc[c.academic_year] = [];
    acc[c.academic_year].push(c);
    return acc;
  }, {} as Record<string, Classroom[]>);
  const sortedYears = Object.keys(byYear).sort().reverse();

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Classrooms</h1>
          <p className="text-muted mt-0.5">{total} class{total !== 1 ? 'es' : ''}</p>
        </div>
        <Button onClick={() => navigate('/classrooms/new')} size="sm">
          <Plus size={14} /> <span className="hidden sm:inline">New</span> Classroom
        </Button>
      </div>

      {isLoading ? <LoadingPage /> : classrooms.length === 0 ? (
        <EmptyState icon={<School size={36} />} title="No classrooms yet"
          message="Create your first classroom to start assigning students." />
      ) : (
        sortedYears.map(year => (
          <div key={year}>
            <h2 className="text-xs font-display font-semibold text-secondary uppercase tracking-widest mb-3">{year}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 md:gap-4">
              {byYear[year].map(classroom => (
                <div
                  key={classroom.id}
                  className="card-hover p-4 md:p-5 cursor-pointer"
                  onClick={() => navigate(`/classrooms/${classroom.id}`)}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-9 h-9 md:w-10 md:h-10 rounded-xl bg-azure-500/15 flex items-center justify-center flex-shrink-0">
                        <School size={16} className="text-azure-400" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-display font-bold text-primary truncate text-sm md:text-base">{classroom.name}</h3>
                        <p className="text-xs text-secondary truncate">{classroom.grade_level_name}</p>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0 ml-2">
                      <span className={`badge ${classroom.is_active ? 'badge-green' : 'badge-rose'} text-[10px]`}>
                        {classroom.is_active ? 'Active' : 'Inactive'}
                      </span>
                      {classroom.stream !== 'general' && (
                        <span className={`badge ${STREAM_COLORS[classroom.stream] ?? 'badge-blue'} text-[10px]`}>
                          {classroom.stream_display}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="text-xs text-secondary mb-3">
                    <span className="text-secondary">{EDUCATION_LEVEL_LABELS[classroom.education_level]}</span>
                    {classroom.necta_exam && <span className="ml-2 badge badge-rose text-[9px]">{classroom.necta_exam}</span>}
                  </div>

                  <div className="flex items-center justify-between text-xs text-secondary mb-3">
                    <span className="flex items-center gap-1">
                      <Users size={11} /> {classroom.student_count} student{classroom.student_count !== 1 ? 's' : ''}
                    </span>
                    {classroom.teacher_names.length > 0 && (
                      <span className="truncate max-w-[120px]">{classroom.teacher_names[0]}</span>
                    )}
                  </div>

                  <div className="flex gap-1.5 pt-3 border-t border-surface">
                    {[
                      { icon: BarChart3, label: 'Analytics', action: () => navigate(`/analytics/class?classroom=${classroom.id}`) },
                      { icon: Users,     label: 'Students',  action: () => navigate(`/students?classroom=${classroom.id}`) },
                      { icon: FileText,  label: 'Report',    action: () => navigate(`/reports?classroom=${classroom.id}`) },
                    ].map(({ icon: Icon, label, action }) => (
                      <button
                        key={label}
                        className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs text-secondary hover:text-primary hover:bg-surface-700 transition-colors"
                        onClick={e => { e.stopPropagation(); action(); }}
                      >
                        <Icon size={11} /> <span className="hidden sm:inline">{label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
      <Pagination page={page} pageSize={pageSize} total={total} onChange={setPage} />
    </div>
  );
}
