import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { LayoutGrid, Printer, ArrowLeft, AlertTriangle, Armchair } from 'lucide-react';
import { groupsApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Select } from '../../components/ui';
import type { SeatingChart, PaginatedResponse, Stream, StudentGroup } from '../../types';

const GROUP_COLORS = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#f43f5e', '#06b6d4', '#84cc16', '#ec4899'];

export default function SeatingChartPage() {
  const { classroomId } = useParams<{ classroomId: string }>();
  const navigate = useNavigate();
  const id = Number(classroomId);

  const [streamId, setStreamId] = useState('');
  const [groupId, setGroupId] = useState('');
  const [rows, setRows] = useState('');
  const [cols, setCols] = useState('');

  const { data: streamsData } = useQuery<PaginatedResponse<Stream> | Stream[]>({
    queryKey: ['streams-for-seating', id],
    queryFn: () => studentsApi.streams({ classroom: id, page_size: 200 }).then(r => r.data),
  });
  const streams: Stream[] = Array.isArray(streamsData) ? streamsData : streamsData?.results ?? [];

  const { data: groupsData } = useQuery<PaginatedResponse<StudentGroup> | StudentGroup[]>({
    queryKey: ['groups-for-seating', id],
    queryFn: () => groupsApi.list({ classroom: id, page_size: 200 }).then(r => r.data),
  });
  const groups: StudentGroup[] = Array.isArray(groupsData) ? groupsData : groupsData?.results ?? [];

  const params = {
    stream_id: streamId || undefined,
    group_id: groupId || undefined,
    rows: rows || undefined,
    cols: cols || undefined,
  };

  const { data: chart, isLoading, isError } = useQuery<SeatingChart>({
    queryKey: ['seating-chart', id, params],
    queryFn: () => groupsApi.seatingChart(id, params).then(r => r.data),
    enabled: !!id,
  });

  // Assign a stable color per group_id so groupmates read visually consistent across the grid.
  const groupColorMap = new Map<number, string>();
  let colorIdx = 0;
  chart?.seats.forEach(s => {
    const gid = s.student?.group_id;
    if (gid != null && !groupColorMap.has(gid)) {
      groupColorMap.set(gid, GROUP_COLORS[colorIdx % GROUP_COLORS.length]);
      colorIdx += 1;
    }
  });

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-secondary hover:text-primary transition-colors p-1">
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 className="text-2xl font-display font-bold text-primary flex items-center gap-2">
              <LayoutGrid className="text-azure-400" size={22} /> Seating Chart
            </h1>
            <p className="text-sm text-secondary mt-0.5">{chart?.classroom_name ?? 'Loading…'}</p>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={() => window.print()} disabled={!chart}>
          <Printer size={14} /> Print
        </Button>
      </div>

      <div className="card p-3 flex flex-wrap items-end gap-3 print:hidden">
        <div className="w-48">
          <Select
            label="Stream"
            options={[{ value: '', label: 'All students' }, ...streams.map(s => ({ value: s.id, label: `Stream ${s.name}` }))]}
            value={streamId}
            onChange={e => { setStreamId(e.target.value); setGroupId(''); }}
          />
        </div>
        <div className="w-48">
          <Select
            label="Group"
            options={[{ value: '', label: 'All students' }, ...groups.map(g => ({ value: g.id, label: g.name }))]}
            value={groupId}
            onChange={e => { setGroupId(e.target.value); setStreamId(''); }}
          />
        </div>
        <div className="w-24">
          <label className="label">Rows</label>
          <input type="number" min={1} className="input" placeholder="Auto" value={rows} onChange={e => setRows(e.target.value)} />
        </div>
        <div className="w-24">
          <label className="label">Columns</label>
          <input type="number" min={1} className="input" placeholder="Auto" value={cols} onChange={e => setCols(e.target.value)} />
        </div>
      </div>

      {isLoading ? <LoadingPage /> : isError || !chart ? (
        <EmptyState icon={<LayoutGrid size={36} />} title="Couldn't load the seating chart" message="Try adjusting the filters or refreshing the page." />
      ) : chart.seated_count === 0 ? (
        <EmptyState icon={<Armchair size={36} />} title="No students to seat" message="This classroom/stream/group has no active students." />
      ) : (
        <>
          {chart.warnings.length > 0 && (
            <div className="flex flex-col gap-1.5 print:hidden">
              {chart.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
                  <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" /> {w}
                </div>
              ))}
            </div>
          )}

          <div className="card p-5 print:shadow-none print:border-0">
            <div className="text-center mb-4 print:block hidden">
              <p className="font-display font-bold text-lg text-primary">{chart.classroom_name} — Seating Chart</p>
            </div>
            <div className="text-center mb-3 print:hidden">
              <span className="badge badge-blue text-xs">Front of Classroom</span>
            </div>
            <div
              className="grid gap-2 mx-auto"
              style={{ gridTemplateColumns: `repeat(${chart.cols}, minmax(0, 1fr))`, maxWidth: `${chart.cols * 130}px` }}
            >
              {chart.seats.map(seat => {
                const color = seat.student?.group_id != null ? groupColorMap.get(seat.student.group_id) : undefined;
                return (
                  <div
                    key={`${seat.row}-${seat.col}`}
                    className={`aspect-[4/3] rounded-xl border flex flex-col items-center justify-center text-center p-2 ${
                      seat.student ? 'border-surface bg-surface-800' : 'border-dashed border-surface/60 bg-transparent'
                    }`}
                    style={color ? { borderColor: color, borderWidth: 2 } : undefined}
                  >
                    {seat.student ? (
                      <>
                        <p className="font-display font-semibold text-xs text-primary leading-tight">{seat.student.name}</p>
                        <p className="text-[10px] text-secondary font-mono mt-0.5">{seat.student.student_id}</p>
                      </>
                    ) : (
                      <Armchair size={16} className="text-secondary/30" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {chart.unseated.length > 0 && (
            <div className="card p-4 print:hidden">
              <p className="text-sm font-display font-semibold text-primary mb-2">
                {chart.unseated.length} student{chart.unseated.length !== 1 ? 's' : ''} didn't fit in this grid
              </p>
              <p className="text-xs text-secondary mb-2">Increase rows/columns above to seat everyone.</p>
              <div className="flex flex-wrap gap-1.5">
                {chart.unseated.map(s => (
                  <span key={s.id} className="badge text-[10px]">{s.name}</span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
