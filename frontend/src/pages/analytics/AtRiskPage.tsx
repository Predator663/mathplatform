import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { analyticsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Select, Pagination } from '../../components/ui';
import { useSiteSettingsStore } from '../../store/siteSettings';
import type { AtRiskStudent, Classroom, PaginatedResponse } from '../../types';

export default function AtRiskPage() {
  const navigate = useNavigate();
  const [classroomId, setClassroomId] = useState('');
  const [threshold, setThreshold] = useState<number>(30);
  const [page, setPage] = useState(1);
  const { getPage } = useSiteSettingsStore();
  const pageSize = getPage('at_risk').page_size;

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms().then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data, isLoading } = useQuery<{ at_risk: AtRiskStudent[]; count: number }>({
    queryKey: ['at-risk', classroomId, threshold],
    queryFn: () => analyticsApi.atRisk({ classroom_id: classroomId || undefined, threshold }).then(r => r.data),
  });
  const students = data?.at_risk ?? [];

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div>
        <h1 className="page-title">At-Risk Students</h1>
        <p className="text-muted mt-1 text-sm">Students with declining performance or below the pass threshold.</p>
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap items-end gap-3 md:gap-4">
        <div className="flex-1 min-w-44">
          <Select label="Classroom" options={[
            { value: '', label: 'All Classrooms' },
            ...classrooms.map(c => ({ value: c.id, label: `${c.name} — ${c.grade_level_name}` })),
          ]} value={classroomId} onChange={e => setClassroomId(e.target.value)} />
        </div>
        <div className="w-44">
          <Select label="Pass Threshold" options={[
            { value: 30, label: '30% (O-Level)' },
            { value: 40, label: '40% (Primary D)' },
            { value: 50, label: '50% (Custom)' },
          ]} value={threshold} onChange={e => setThreshold(Number(e.target.value))} />
        </div>
        {data && (
          <div className="pb-1">
            <span className={`badge text-sm px-3 py-1 ${data.count > 0 ? 'badge-rose' : 'badge-green'}`}>
              {data.count} student{data.count !== 1 ? 's' : ''} flagged
            </span>
          </div>
        )}
      </div>

      {isLoading ? <LoadingPage /> : students.length === 0 ? (
        <EmptyState icon={<AlertTriangle size={36} className="text-emerald-400" />}
          title="No at-risk students" message="All students are performing above the threshold 🎉" />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 md:gap-4">
            {students.slice((page - 1) * pageSize, page * pageSize).map(s => (
              <div
                key={s.student_id}
                className="card p-4 border-rose-500/20 cursor-pointer hover:border-rose-500/40 transition-all active:scale-[0.99]"
                onClick={() => navigate(`/analytics/student/${s.student_id}`)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="min-w-0">
                    <p className="font-display font-semibold text-primary text-sm truncate">{s.student_name}</p>
                    <p className="text-xs text-secondary mt-0.5 truncate">{s.student_code} · {s.classroom ?? 'No class'}</p>
                  </div>
                  <span className="font-display font-bold text-lg text-rose-400 flex-shrink-0 ml-2">{s.recent_average}%</span>
                </div>
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {s.flags.below_threshold && <span className="badge badge-rose text-[10px]">Below {threshold}%</span>}
                  {s.flags.declining && <span className="badge badge-amber text-[10px]">Declining</span>}
                </div>
                {/* Mini sparkline */}
                <div className="flex items-end gap-1 h-8">
                  {s.recent_scores.map((score, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                      <div className="w-full rounded-sm"
                        style={{ height: `${Math.max(3, (score / 100) * 32)}px`,
                          backgroundColor: score >= threshold ? '#10b981' : '#f43f5e',
                          opacity: 0.6 + i * 0.15 }} />
                      <span className="text-[8px] font-mono text-secondary">{score}%</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-azure-400 mt-3 font-display font-medium">View analytics →</p>
              </div>
            ))}
          </div>
          <Pagination page={page} pageSize={pageSize} total={students.length} onChange={setPage} />
        </>
      )}
    </div>
  );
}
