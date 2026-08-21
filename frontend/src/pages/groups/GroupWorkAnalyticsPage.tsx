import { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, Cell, PieChart, Pie,
} from 'recharts';
import {
  ArrowLeft, BarChart3, ArrowUp, ArrowDown, FileDown, FileSpreadsheet, FileText,
  Shuffle, ArrowRightLeft, AlertTriangle,
} from 'lucide-react';
import { groupAssignmentsApi, studentsApi, subjectsApi, groupsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Select, Input, Table, Tr, Td } from '../../components/ui';
import { downloadBlob, blobErrorMessage, TERM_LABELS, ASSIGNMENT_TYPE_LABELS, gradeColor } from '../../utils';
import type {
  Classroom, PaginatedResponse, Subject, Stream, StudentGroup,
  GroupWorkAnalytics, GroupWorkReassignmentSuggestions, GroupWorkPerGroup,
} from '../../types';

const DIST_COLORS: Record<string, string> = {
  '0-49': '#f43f5e', '50-59': '#f59e0b', '60-69': '#fbbf24',
  '70-79': '#60a5fa', '80-89': '#34d399', '90-100': '#10b981',
};

type SortField = 'group_name' | 'stream_name' | 'assignments_count' | 'average_pct' | 'best_pct' | 'worst_pct';
type SortDir = 'asc' | 'desc';

export default function GroupWorkAnalyticsPage() {
  const params = useParams<{ classroomId?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedClass, setSelectedClass] = useState<number | null>(
    params.classroomId ? Number(params.classroomId) : null
  );
  const [streamFilter, setStreamFilter] = useState('');
  const [groupFilter, setGroupFilter] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [termFilter, setTermFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sortField, setSortField] = useState<SortField>('average_pct');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [showReassign, setShowReassign] = useState(false);

  const filterParams = {
    stream_id: streamFilter || undefined,
    group_id: groupFilter || undefined,
    subject_id: subjectFilter || undefined,
    term: termFilter || undefined,
    assignment_type: typeFilter || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  };

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms-all-group-work-analytics'],
    queryFn: () => studentsApi.classrooms({ page_size: 200 }).then(r => r.data),
  });
  const classrooms: Classroom[] = Array.isArray(classroomsData)
    ? classroomsData : (classroomsData as PaginatedResponse<Classroom>)?.results ?? [];

  const { data: streamsData } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams-for-group-work-analytics', selectedClass],
    queryFn: () => studentsApi.streams({ classroom: selectedClass, page_size: 200 }).then(r => r.data),
    enabled: !!selectedClass,
  });
  const streams: Stream[] = Array.isArray(streamsData)
    ? streamsData : (streamsData as PaginatedResponse<Stream>)?.results ?? [];

  const { data: groupsData } = useQuery<PaginatedResponse<StudentGroup> | StudentGroup[]>({
    queryKey: ['groups-for-group-work-analytics', selectedClass],
    queryFn: () => groupsApi.list({ classroom: selectedClass, page_size: 200 }).then(r => r.data),
    enabled: !!selectedClass,
  });
  const groupsList: StudentGroup[] = Array.isArray(groupsData)
    ? groupsData : (groupsData as PaginatedResponse<StudentGroup>)?.results ?? [];

  const { data: subjectsData } = useQuery<PaginatedResponse<Subject> | Subject[]>({
    queryKey: ['subjects-all-group-work-analytics'],
    queryFn: () => subjectsApi.list({ page_size: 100 }).then(r => r.data),
  });
  const subjects: Subject[] = Array.isArray(subjectsData)
    ? subjectsData : (subjectsData as PaginatedResponse<Subject>)?.results ?? [];

  const { data: analytics, isLoading } = useQuery<GroupWorkAnalytics>({
    queryKey: ['group-work-analytics', selectedClass, filterParams],
    queryFn: () => groupAssignmentsApi.analytics(selectedClass!, filterParams).then(r => r.data),
    enabled: !!selectedClass,
  });

  const { data: suggestions, isLoading: suggestionsLoading } = useQuery<GroupWorkReassignmentSuggestions>({
    queryKey: ['group-work-reassignment', selectedClass, streamFilter, subjectFilter, termFilter, typeFilter],
    queryFn: () => groupAssignmentsApi.reassignmentSuggestions(selectedClass!, {
      stream_id: streamFilter || undefined, subject_id: subjectFilter || undefined,
      term: termFilter || undefined, assignment_type: typeFilter || undefined,
    }).then(r => r.data),
    enabled: !!selectedClass && showReassign,
  });

  const transferMutation = useMutation({
    mutationFn: ({ studentId, toGroupId }: { studentId: number; toGroupId: number }) =>
      groupsApi.transferMember(studentId, toGroupId, 'Reassigned from Group Work Analytics — performance-based suggestion'),
    onSuccess: () => {
      toast.success('Student reassigned.');
      queryClient.invalidateQueries({ queryKey: ['group-work-reassignment'] });
      queryClient.invalidateQueries({ queryKey: ['group-work-analytics'] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not reassign student.'),
  });

  const toggleSort = (field: SortField) => {
    if (field === sortField) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const sortedGroups: GroupWorkPerGroup[] = useMemo(() => {
    const list = [...(analytics?.per_group ?? [])];
    list.sort((a, b) => {
      const av = a[sortField] ?? (typeof a[sortField] === 'string' ? '' : 0);
      const bv = b[sortField] ?? (typeof b[sortField] === 'string' ? '' : 0);
      if (typeof av === 'string' || typeof bv === 'string') {
        return sortDir === 'asc'
          ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
      }
      return sortDir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return list;
  }, [analytics, sortField, sortDir]);

  const distData = analytics?.distribution
    ? Object.entries(analytics.distribution).map(([range, count]) => ({ range, count }))
    : [];

  const groupBarData = sortedGroups.map(g => ({
    name: g.group_name.length > 12 ? g.group_name.slice(0, 12) + '…' : g.group_name,
    average: g.average_pct,
  }));

  const trendData = (analytics?.trend ?? []).map(t => ({
    name: t.title.length > 14 ? t.title.slice(0, 14) + '…' : t.title,
    date: t.date, average: t.average_pct,
  }));

  async function handleExport(format: 'pdf' | 'excel' | 'csv') {
    if (!selectedClass) return;
    try {
      if (format === 'csv') {
        const res = await groupAssignmentsApi.exportMarksCsv(selectedClass, filterParams);
        downloadBlob(res.data, 'group_assignment_marks.csv');
      } else {
        const res = await groupAssignmentsApi.exportAnalytics(selectedClass, format, filterParams);
        downloadBlob(res.data, `group_work_analytics.${format === 'pdf' ? 'pdf' : 'xlsx'}`);
      }
      toast.success('Export downloaded.');
    } catch (e) {
      toast.error(await blobErrorMessage(e, 'Export failed — make sure marks are recorded for this selection.'));
    }
  }

  const SortHeader = ({ field, label }: { field: SortField; label: string }) => (
    <button className="flex items-center gap-1 hover:text-primary" onClick={() => toggleSort(field)}>
      {label} {sortField === field && (sortDir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
    </button>
  );

  return (
    <div className="p-4 md:p-6 flex flex-col gap-5 max-w-6xl mx-auto page-enter">
      <button onClick={() => navigate('/groups/assignments')}
        className="flex items-center gap-1.5 text-sm text-secondary hover:text-primary w-fit">
        <ArrowLeft size={14} /> Back to Group Assignments
      </button>

      <div>
        <h1 className="text-2xl font-display font-bold text-primary flex items-center gap-2">
          <BarChart3 className="text-azure-400" size={24} /> Group Work Analytics
        </h1>
        <p className="text-sm text-secondary mt-0.5">
          Performance across groups, streams, and assignments — with a performance-based reassignment tool.
        </p>
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <div className="min-w-[220px]">
          <Select
            label="Classroom"
            options={[{ value: '', label: 'Select a classroom…' }, ...classrooms.map(c => ({
              value: c.id, label: `${c.name} (${c.academic_year})`,
            }))]}
            value={selectedClass ?? ''}
            onChange={e => {
              setSelectedClass(e.target.value ? Number(e.target.value) : null);
              setStreamFilter(''); setGroupFilter('');
            }}
          />
        </div>
        <div className="min-w-[150px]">
          <Select label="Stream" disabled={!selectedClass}
            options={[{ value: '', label: 'All streams' }, ...streams.map(s => ({ value: s.id, label: s.name }))]}
            value={streamFilter} onChange={e => { setStreamFilter(e.target.value); setGroupFilter(''); }} />
        </div>
        <div className="min-w-[150px]">
          <Select label="Group" disabled={!selectedClass}
            options={[{ value: '', label: 'All groups' }, ...groupsList
              .filter(g => !streamFilter || String(g.stream) === streamFilter)
              .map(g => ({ value: g.id, label: g.name }))]}
            value={groupFilter} onChange={e => setGroupFilter(e.target.value)} />
        </div>
        <div className="min-w-[170px]">
          <Select label="Subject"
            options={[{ value: '', label: 'All subjects' }, ...subjects.map(s => ({ value: s.id, label: s.name }))]}
            value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)} />
        </div>
        <div className="min-w-[150px]">
          <Select label="Term"
            options={[{ value: '', label: 'All terms' }, ...Object.entries(TERM_LABELS).map(([v, l]) => ({ value: v, label: l }))]}
            value={termFilter} onChange={e => setTermFilter(e.target.value)} />
        </div>
        <div className="min-w-[160px]">
          <Select label="Type"
            options={[{ value: '', label: 'All types' }, ...Object.entries(ASSIGNMENT_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }))]}
            value={typeFilter} onChange={e => setTypeFilter(e.target.value)} />
        </div>
        <Input label="From" type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-36" />
        <Input label="To" type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="w-36" />
      </div>

      {!selectedClass ? (
        <EmptyState icon={<BarChart3 size={36} />} title="Select a classroom"
          message="Choose a classroom above to see its group work analytics." />
      ) : isLoading ? (
        <LoadingPage />
      ) : !analytics || analytics.classroom_average_pct === null ? (
        <EmptyState icon={<BarChart3 size={36} />} title="No group-assignment marks yet"
          message="Record marks for at least one group assignment to see analytics here." />
      ) : (
        <>
          {/* Headline stats + export */}
          <div className="card p-4 flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap gap-6">
              <div>
                <p className="label">Classroom Average</p>
                <p className={`text-2xl font-display font-bold ${gradeColor(analytics.classroom_average_pct)}`}>
                  {analytics.classroom_average_pct}%
                </p>
              </div>
              <div>
                <p className="label">Assignments</p>
                <p className="text-2xl font-display font-bold text-primary">{analytics.assignments_count}</p>
              </div>
              <div>
                <p className="label">Groups Scored</p>
                <p className="text-2xl font-display font-bold text-primary">{analytics.groups_scored_count}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" onClick={() => handleExport('pdf')}>
                <FileText size={14} /> PDF
              </Button>
              <Button variant="secondary" size="sm" onClick={() => handleExport('excel')}>
                <FileSpreadsheet size={14} /> Excel
              </Button>
              <Button variant="secondary" size="sm" onClick={() => handleExport('csv')}>
                <FileDown size={14} /> Raw CSV
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setShowReassign(v => !v)}>
                <Shuffle size={14} /> {showReassign ? 'Hide' : 'Reassignment'} Suggestions
              </Button>
            </div>
          </div>

          {/* Charts */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="card p-4">
              <p className="section-title mb-3">Average by Group</p>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={groupBarData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="average" radius={[4, 4, 0, 0]}>
                    {groupBarData.map((d, i) => (
                      <Cell key={i} fill={d.average >= 65 ? '#10b981' : d.average >= 45 ? '#f59e0b' : '#f43f5e'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card p-4">
              <p className="section-title mb-3">Score Distribution</p>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={distData} dataKey="count" nameKey="range" cx="50%" cy="50%"
                    outerRadius={90} label={({ range, count }) => count > 0 ? `${range}: ${count}` : ''}>
                    {distData.map((d, i) => <Cell key={i} fill={DIST_COLORS[d.range] || '#94a3b8'} />)}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="card p-4 md:col-span-2">
              <p className="section-title mb-3">Trend Across Assignments</p>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="average" name="Class average %" stroke="#60a5fa" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Per-stream rollup */}
          {analytics.per_stream.length > 0 && (
            <div className="card p-0 overflow-hidden">
              <p className="section-title px-4 pt-4">By Stream</p>
              <Table headers={['Stream', 'Groups', 'Assignments Scored', 'Average %']}>
                {analytics.per_stream.map(s => (
                  <Tr key={String(s.stream_id)}>
                    <Td className="font-semibold text-primary">{s.stream_name}</Td>
                    <Td>{s.group_count}</Td>
                    <Td>{s.assignments_scored}</Td>
                    <Td><span className={`font-mono font-semibold ${gradeColor(s.average_pct)}`}>{s.average_pct}%</span></Td>
                  </Tr>
                ))}
              </Table>
            </div>
          )}

          {/* Sortable per-group table */}
          <div className="card p-0 overflow-hidden">
            <p className="section-title px-4 pt-4">By Group</p>
            <Table headers={['Group', 'Stream', 'Assignments', 'Best %', 'Worst %', 'Average %']}>
              {sortedGroups.map(g => (
                <Tr key={g.group_id}>
                  <Td className="font-semibold text-primary">{g.group_name}</Td>
                  <Td>{g.stream_name || '—'}</Td>
                  <Td>{g.assignments_count}</Td>
                  <Td>{g.best_pct}%</Td>
                  <Td>{g.worst_pct}%</Td>
                  <Td><span className={`font-mono font-semibold ${gradeColor(g.average_pct)}`}>{g.average_pct}%</span></Td>
                </Tr>
              ))}
            </Table>
            <div className="flex gap-4 px-4 py-2 text-xs text-muted border-t border-surface">
              <SortHeader field="group_name" label="Name" />
              <SortHeader field="assignments_count" label="Assignments" />
              <SortHeader field="average_pct" label="Average" />
            </div>
          </div>

          {/* Reassignment suggestions panel */}
          {showReassign && (
            <div className="card p-4">
              <div className="flex items-center gap-2 mb-3">
                <ArrowRightLeft size={16} className="text-azure-400" />
                <p className="section-title">Performance-Based Reassignment Suggestions</p>
              </div>
              {suggestionsLoading ? (
                <LoadingPage />
              ) : !suggestions || suggestions.underperforming.length === 0 ? (
                <EmptyState icon={<Shuffle size={30} />} title="No groups flagged"
                  message="No group is lagging far enough below the classroom average to warrant a suggestion right now." />
              ) : (
                <div className="flex flex-col gap-4">
                  {suggestions.underperforming.map(u => (
                    <div key={u.group_id} className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-3">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                          <AlertTriangle size={15} className="text-rose-400" />
                          <span className="font-display font-semibold text-primary">{u.group_name}</span>
                          <span className="text-xs text-muted">{u.stream_name || 'No stream'}</span>
                        </div>
                        <span className="text-xs text-rose-400 font-mono">
                          {u.average_pct}% · {u.gap_from_classroom_average} pts below average
                        </span>
                      </div>
                      {u.candidates.length === 0 ? (
                        <p className="text-xs text-muted mt-2">
                          No strong-performing candidate found in the same stream to move in yet.
                        </p>
                      ) : (
                        <div className="flex flex-col gap-1.5 mt-2">
                          {u.candidates.map(c => (
                            <div key={c.student_id}
                              className="flex items-center justify-between gap-2 bg-surface-700/40 rounded-lg px-3 py-1.5 text-sm">
                              <span className="text-primary/90">
                                {c.student_name}
                                <span className="text-xs text-muted ml-1.5">
                                  from {c.from_group_name} · {c.individual_average}% individually
                                </span>
                              </span>
                              <Button size="sm" variant="secondary"
                                loading={transferMutation.isPending}
                                onClick={() => transferMutation.mutate({ studentId: c.student_id, toGroupId: u.group_id })}>
                                Move to {u.group_name}
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
