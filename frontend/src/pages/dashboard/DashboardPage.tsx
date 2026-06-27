import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Users, BookOpen, AlertTriangle, TrendingUp, ArrowRight,
  Award, School, Target, Zap, Activity, BarChart2, Shield,
} from 'lucide-react';
import { analyticsApi } from '../../api';
import { LoadingPage } from '../../components/ui';
import { formatDate, EXAM_TYPE_LABELS, TERM_LABELS } from '../../utils';
import { useAuthStore } from '../../store/auth';
import { useSubjectStore } from '../../store/subject';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, BarChart, Bar, Cell, LabelList,
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  LineChart, Line, ReferenceLine,
} from 'recharts';
import type { TooltipProps } from 'recharts';
import type { DashboardSummary } from '../../types';

/* ── Theme-aware chart tokens ─────────────────────────────────────── */
function cssVar(n: string) {
  if (typeof document === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(n).trim();
}

const GRADE_COLORS: Record<string, string> = {
  A: '#10b981', B: '#3b82f6', C: '#f59e0b', D: '#fb923c', F: '#f43f5e',
};

function getGreeting() {
  const h = new Date().getHours();
  return h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
}

/* ── Animated counter ─────────────────────────────────────────────── */
function AnimatedNumber({ value, suffix = '', decimals = 0 }: { value: number; suffix?: string; decimals?: number }) {
  const [display, setDisplay] = useState(0);
  const raf = useRef<number>(0);
  useEffect(() => {
    const start = performance.now();
    const duration = 900;
    const from = 0;
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (value - from) * eased);
      if (t < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [value]);
  return <>{display.toFixed(decimals)}{suffix}</>;
}

/* ── Radial gauge ─────────────────────────────────────────────────── */
function RadialGauge({ value, color, size = 80 }: { value: number; color: string; size?: number }) {
  const r = (size / 2) - 8;
  const circ = 2 * Math.PI * r;
  const [dash, setDash] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setDash((value / 100) * circ), 80);
    return () => clearTimeout(t);
  }, [value, circ]);
  return (
    <svg width={size} height={size} className="flex-shrink-0">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--bg-700)" strokeWidth={7} />
      <circle
        cx={size/2} cy={size/2} r={r} fill="none"
        stroke={color} strokeWidth={7}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: 'stroke-dasharray 1s cubic-bezier(0.34,1.56,0.64,1)' }}
      />
      <text x={size/2} y={size/2 + 1} textAnchor="middle" dominantBaseline="middle"
        fontSize={size < 70 ? 11 : 13} fontWeight="700" fill={color} fontFamily="DM Mono, monospace">
        {value}%
      </text>
    </svg>
  );
}

/* ── Heat strip (mini bar of colour intensity) ────────────────────── */
function HeatStrip({ value }: { value: number }) {
  const color = value >= 75 ? '#10b981' : value >= 50 ? '#3b82f6' : value >= 30 ? '#f59e0b' : '#f43f5e';
  return (
    <div className="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full"
        style={{
          width: `${value}%`, backgroundColor: color,
          transition: 'width 1s cubic-bezier(0.34,1.56,0.64,1)',
        }}
      />
    </div>
  );
}

/* ── Custom tooltips ──────────────────────────────────────────────── */
const TT = ({ active, payload, label }: TooltipProps<number, string> & { payload?: { value: number; payload?: { passRate: number } }[] }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-2xl border border-azure-500/20">
      <p className="font-display font-semibold text-primary mb-1">{label}</p>
      <p className="text-azure-400">Avg: <b>{payload[0].value}%</b></p>
      {payload[0].payload?.passRate != null && <p className="text-emerald-400">Pass: <b>{payload[0].payload.passRate}%</b></p>}
    </div>
  );
};
const BarTT = ({ active, payload, label }: TooltipProps<number, string> & { payload?: { value: number; payload?: { student_count?: number } }[] }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-2xl border border-azure-500/20">
      <p className="font-display font-semibold text-primary mb-1">{label}</p>
      <p className="text-azure-400">Avg: <b>{payload[0].value}%</b></p>
      {payload[0].payload?.student_count != null && <p className="text-secondary">{payload[0].payload.student_count} students</p>}
    </div>
  );
};

/* ── Tab button ───────────────────────────────────────────────────── */
function Tab({ label, icon, active, onClick }: { label: string; icon: React.ReactNode; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-display font-semibold transition-all ${
        active ? 'bg-azure-500/20 text-azure-400 border border-azure-500/30' : 'text-secondary hover:text-primary hover:bg-surface-700'
      }`}
    >
      {icon}{label}
    </button>
  );
}

/* ════════════════════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const { user } = useAuthStore();
  const { activeSubjectId } = useSubjectStore();
  const isAdmin = user?.role === 'super_admin';
  const [analyticsTab, setAnalyticsTab] = useState<'classrooms' | 'subjects' | 'teachers'>('classrooms');

  const { data, isLoading } = useQuery<DashboardSummary>({
    queryKey: ['dashboard', activeSubjectId],
    queryFn: () => analyticsApi.dashboard({
      ...(activeSubjectId ? { subject_id: activeSubjectId } : {}),
    }).then(r => r.data),
  });

  if (isLoading) return <LoadingPage />;

  /* ── Derived chart data ─────────────────────────────────────────── */
  const chartData = (data?.recent_exam_stats ?? [])
    .filter(e => e.average != null)
    .slice().reverse()
    .map(e => ({
      name: e.title.length > 11 ? e.title.slice(0, 11) + '…' : e.title,
      average: e.average,
      passRate: e.pass_rate,
    }));

  const gradeData = data?.grade_distribution
    ? (['A', 'B', 'C', 'D', 'F'] as const).map(g => ({ grade: g, count: data.grade_distribution![g] }))
    : [];
  const totalGraded = gradeData.reduce((s, g) => s + g.count, 0);

  const classroomData = (data?.classroom_averages ?? []).map(c => ({
    classroom: c.classroom.length > 9 ? c.classroom.slice(0, 9) + '…' : c.classroom,
    average: c.average,
    student_count: c.student_count,
  }));

  const subjectData = (data?.subject_averages ?? []).sort((a, b) => b.average - a.average);
  const teacherData = (data?.teacher_stats ?? []).sort((a, b) => b.average - a.average);

  const radarData = classroomData.map(c => ({ classroom: c.classroom, average: c.average, fullMark: 100 }));

  const grid   = cssVar('--chart-grid')   || '#2e2e42';
  const axis   = cssVar('--chart-axis')   || '#3d3d55';
  const avg    = data?.overall_average ?? 0;

  return (
    <div className="flex flex-col gap-5">

      {/* ── Header ────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
        <div>
          <h1 className="page-title">
            Good {getGreeting()},{' '}
            <span className="text-gradient">{user?.first_name}</span>
          </h1>
          <p className="text-muted mt-0.5 text-sm">Tanzania Curriculum · Mathematics Command Center</p>
        </div>
        {data?.overall_average != null && (
          <div className="flex items-center gap-3 bg-surface-800 border border-azure-500/20 rounded-2xl px-4 py-2.5">
            <RadialGauge value={avg} color={avg >= 50 ? '#10b981' : avg >= 30 ? '#f59e0b' : '#f43f5e'} size={56} />
            <div>
              <p className="text-[10px] text-secondary uppercase tracking-widest font-display">Overall Avg</p>
              <p className="font-display font-bold text-2xl text-primary leading-tight">
                <AnimatedNumber value={avg} decimals={1} suffix="%" />
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ── Stat tiles ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {[
          { label: 'Students', value: data?.total_students ?? 0, sub: `${data?.total_classrooms ?? 0} classrooms`, color: '#3b82f6', icon: <Users size={16} />, glow: 'shadow-blue-500/10' },
          { label: 'Exams', value: data?.total_exams ?? 0, sub: 'All terms', color: '#8b5cf6', icon: <BookOpen size={16} />, glow: 'shadow-violet-500/10' },
          { label: 'Pass Rate', value: null, pct: avg, sub: 'Overall', color: avg >= 50 ? '#10b981' : '#f59e0b', icon: <Target size={16} />, glow: 'shadow-emerald-500/10' },
          { label: 'At Risk', value: data?.at_risk_count ?? 0, sub: 'Need attention', color: '#f43f5e', icon: <AlertTriangle size={16} />, glow: 'shadow-rose-500/10' },
        ].map(({ label, value, pct, sub, color, icon, glow }) => (
          <div key={label} className={`card p-4 border transition-all hover:shadow-lg ${glow} group`}
            style={{ borderColor: `${color}22` }}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-secondary font-display font-semibold uppercase tracking-wider">{label}</p>
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}20`, color }}>
                {icon}
              </div>
            </div>
            <p className="font-display font-black text-2xl sm:text-3xl text-primary leading-none" style={{ color }}>
              {pct != null
                ? <AnimatedNumber value={pct} decimals={1} suffix="%" />
                : <AnimatedNumber value={value ?? 0} />}
            </p>
            <p className="text-xs text-secondary mt-1">{sub}</p>
          </div>
        ))}
      </div>

      {/* ── Area chart: exam performance timeline ─────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity size={15} className="text-azure-400" />
              <h2 className="section-title">Exam Performance Timeline</h2>
            </div>
            <Link to="/exams" className="text-xs text-azure-400 hover:text-azure-300 flex items-center gap-1 transition-colors">
              View all <ArrowRight size={12} />
            </Link>
          </div>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={190}>
              <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="avgGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="passGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={grid} />
                <XAxis dataKey="name" tick={{ fill: axis, fontSize: 10, fontFamily: 'DM Sans' }} />
                <YAxis domain={[0, 100]} tick={{ fill: axis, fontSize: 10, fontFamily: 'DM Sans' }} width={26} />
                <Tooltip content={<TT />} />
                <ReferenceLine y={30} stroke="#f43f5e" strokeDasharray="4 4" strokeOpacity={0.4}
                  label={{ value: 'Pass', fill: '#f43f5e', fontSize: 9 }} />
                <Area type="monotone" dataKey="average" stroke="#3b82f6" fill="url(#avgGrad)"
                  strokeWidth={2.5} dot={{ fill: '#3b82f6', r: 3, strokeWidth: 0 }} name="Average %" isAnimationActive animationDuration={1200} />
                <Area type="monotone" dataKey="passRate" stroke="#10b981" fill="url(#passGrad)"
                  strokeWidth={1.5} dot={false} strokeDasharray="5 3" name="Pass Rate %" isAnimationActive animationDuration={1400} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex flex-col items-center justify-center gap-2 text-muted text-sm">
              <Activity size={28} className="opacity-20" />
              No scored exams yet
            </div>
          )}
          {chartData.length > 0 && (
            <div className="flex items-center gap-4 mt-3 pl-1">
              <div className="flex items-center gap-1.5"><div className="w-4 h-0.5 bg-azure-500 rounded" /><span className="text-[10px] text-secondary">Average</span></div>
              <div className="flex items-center gap-1.5"><div className="w-4 h-px border-t-2 border-dashed border-emerald-400" /><span className="text-[10px] text-secondary">Pass Rate</span></div>
              <div className="flex items-center gap-1.5"><div className="w-4 h-px border-t-2 border-dashed border-rose-400 opacity-50" /><span className="text-[10px] text-secondary">Pass line 30%</span></div>
            </div>
          )}
        </div>

        {/* Latest exams list */}
        <div className="card p-5">
          <h2 className="section-title mb-3 flex items-center gap-2"><Zap size={14} className="text-amber-400" /> Latest Exams</h2>
          <div className="flex flex-col gap-1.5">
            {data?.recent_exams?.length ? data.recent_exams.map(exam => (
              <Link key={exam.id} to={`/exams/${exam.id}`}
                className="flex items-start justify-between gap-2 p-2.5 rounded-xl bg-surface-900 hover:bg-surface-700 transition-colors group">
                <div className="min-w-0">
                  <p className="text-xs font-display font-medium text-primary truncate group-hover:text-azure-400 transition-colors">{exam.title}</p>
                  <p className="text-[10px] text-secondary mt-0.5">{EXAM_TYPE_LABELS[exam.exam_type] ?? exam.exam_type} · {TERM_LABELS[exam.term] ?? exam.term}</p>
                </div>
                <p className="text-[10px] text-secondary whitespace-nowrap flex-shrink-0 mt-0.5">{formatDate(exam.exam_date)}</p>
              </Link>
            )) : <p className="text-muted text-sm text-center py-8">No exams yet</p>}
          </div>
        </div>
      </div>

      {/* ── Grade distribution + radar ─────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <div className="card p-5">
          <h2 className="section-title mb-4 flex items-center gap-2"><Award size={14} className="text-azure-400" /> Grade Distribution</h2>
          {totalGraded > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={gradeData} margin={{ top: 20, right: 8, bottom: 0, left: -22 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
                <XAxis dataKey="grade" tick={{ fill: axis, fontSize: 11, fontFamily: 'DM Sans' }} />
                <YAxis tick={{ fill: axis, fontSize: 10, fontFamily: 'DM Sans' }} width={26} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: cssVar('--chart-tooltip-bg') || '#1a1a26', border: `1px solid ${grid}`, borderRadius: 12, fontSize: 11 }}
                  labelStyle={{ color: cssVar('--text-primary') || '#fff', fontWeight: 700 }}
                  formatter={(v: any) => [`${v} student${v !== 1 ? 's' : ''}`, 'Count'] as [string, string]}
                  labelFormatter={(l: any) => `Grade ${l}`}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} isAnimationActive animationDuration={900} animationEasing="ease-out">
                  <LabelList dataKey="count" position="top" fill={axis} fontSize={11} />
                  {gradeData.map(g => <Cell key={g.grade} fill={GRADE_COLORS[g.grade]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex items-center justify-center text-muted text-sm">No scored exams yet</div>
          )}
        </div>

        <div className="card p-5">
          <h2 className="section-title mb-3 flex items-center gap-2"><BarChart2 size={14} className="text-violet-400" /> Classroom Radar</h2>
          {radarData.length > 1 ? (
            <ResponsiveContainer width="100%" height={180}>
              <RadarChart data={radarData} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
                <PolarGrid stroke={grid} />
                <PolarAngleAxis dataKey="classroom" tick={{ fill: axis, fontSize: 9, fontFamily: 'DM Sans' }} />
                <Radar name="Avg" dataKey="average" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.25} strokeWidth={2}
                  isAnimationActive animationDuration={1100} />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex items-center justify-center text-muted text-sm">Need 2+ classrooms</div>
          )}
        </div>

        {/* Pass/fail gauge summary */}
        <div className="card p-5 flex flex-col gap-3">
          <h2 className="section-title flex items-center gap-2"><Shield size={14} className="text-emerald-400" /> Performance Health</h2>
          {gradeData.some(g => g.count > 0) ? (
            <div className="flex flex-col gap-3 mt-1">
              {gradeData.map(g => (
                <div key={g.grade} className="flex items-center gap-3">
                  <div className="w-6 h-6 rounded-lg flex items-center justify-center text-[11px] font-mono font-bold flex-shrink-0"
                    style={{ backgroundColor: `${GRADE_COLORS[g.grade]}22`, color: GRADE_COLORS[g.grade] }}>
                    {g.grade}
                  </div>
                  <HeatStrip value={totalGraded > 0 ? Math.round((g.count / totalGraded) * 100) : 0} />
                  <span className="text-xs font-mono text-secondary w-8 text-right flex-shrink-0">{g.count}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted text-sm">No data yet</div>
          )}
        </div>
      </div>

      {/* ── Multi-tab analytics: Classrooms / Subjects / Teachers ──── */}
      <div className="card p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
          <h2 className="section-title flex items-center gap-2"><TrendingUp size={15} className="text-azure-400" /> Comparative Analytics</h2>
          <div className="flex items-center gap-1.5 flex-wrap">
            <Tab label="Classrooms" icon={<School size={12} />} active={analyticsTab === 'classrooms'} onClick={() => setAnalyticsTab('classrooms')} />
            {isAdmin && (data?.subject_averages?.length ?? 0) > 0 && (
              <Tab label="Subjects" icon={<BookOpen size={12} />} active={analyticsTab === 'subjects'} onClick={() => setAnalyticsTab('subjects')} />
            )}
            {isAdmin && (data?.teacher_stats?.length ?? 0) > 0 && (
              <Tab label="Teachers" icon={<Users size={12} />} active={analyticsTab === 'teachers'} onClick={() => setAnalyticsTab('teachers')} />
            )}
          </div>
        </div>

        {/* Classrooms tab */}
        {analyticsTab === 'classrooms' && (
          classroomData.length > 0 ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={classroomData} margin={{ top: 5, right: 8, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
                  <XAxis dataKey="classroom" tick={{ fill: axis, fontSize: 10, fontFamily: 'DM Sans' }} />
                  <YAxis domain={[0, 100]} tick={{ fill: axis, fontSize: 10, fontFamily: 'DM Sans' }} width={26} />
                  <ReferenceLine y={30} stroke="#f43f5e" strokeDasharray="4 4" strokeOpacity={0.5} />
                  <Tooltip content={<BarTT />} />
                  <Bar dataKey="average" radius={[6, 6, 0, 0]} isAnimationActive animationDuration={1000} animationEasing="ease-out">
                    {classroomData.map(c => (
                      <Cell key={c.classroom}
                        fill={c.average >= 50 ? '#10b981' : c.average >= 30 ? '#3b82f6' : '#f43f5e'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-2">
                {classroomData.map(c => (
                  <div key={c.classroom} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface-900">
                    <p className="text-xs font-display font-medium text-primary w-20 flex-shrink-0">{c.classroom}</p>
                    <HeatStrip value={c.average} />
                    <span className="text-xs font-mono font-bold w-10 text-right flex-shrink-0"
                      style={{ color: c.average >= 50 ? '#10b981' : c.average >= 30 ? '#3b82f6' : '#f43f5e' }}>
                      {c.average}%
                    </span>
                    <span className="text-[10px] text-secondary w-14 flex-shrink-0">{c.student_count} stu.</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-muted text-sm">No classroom data yet</div>
          )
        )}

        {/* Subjects tab */}
        {analyticsTab === 'subjects' && (
          subjectData.length > 0 ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <ResponsiveContainer width="100%" height={Math.max(200, subjectData.length * 42)}>
                <BarChart data={subjectData} layout="vertical" margin={{ top: 4, right: 36, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={grid} horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: axis, fontSize: 10 }} />
                  <YAxis type="category" dataKey="code" width={44} tick={{ fill: axis, fontSize: 11, fontFamily: 'DM Mono, monospace' }} />
                  <ReferenceLine x={30} stroke="#f43f5e" strokeDasharray="4 4" strokeOpacity={0.5} />
                  <Tooltip
                    contentStyle={{ background: cssVar('--chart-tooltip-bg') || '#1a1a26', border: `1px solid ${grid}`, borderRadius: 12, fontSize: 11 }}
                    labelStyle={{ color: cssVar('--text-primary') || '#fff' }}
                    formatter={(v: any, n: any) => [`${v}%`, (n === 'average' ? 'Average' : 'Pass Rate')] as [string, string]}
                  />
                  <Bar dataKey="average" radius={[0, 6, 6, 0]} barSize={18} isAnimationActive animationDuration={1000}>
                    {subjectData.map(s => <Cell key={s.code} fill={s.color || '#6366f1'} />)}
                  </Bar>
                  <Bar dataKey="pass_rate" radius={[0, 6, 6, 0]} barSize={8} fill="#10b981" fillOpacity={0.5} isAnimationActive animationDuration={1200} />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-2">
                {subjectData.map(s => (
                  <div key={s.code} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface-900">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: s.color }} />
                    <p className="text-xs font-display font-medium text-primary flex-1 min-w-0 truncate">{s.subject}</p>
                    <RadialGauge value={s.average} color={s.color} size={44} />
                    <div className="text-right flex-shrink-0">
                      <p className="text-[10px] text-emerald-400 font-mono">{s.pass_rate}% pass</p>
                      <p className="text-[10px] text-secondary">{s.exam_count} exams</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-muted text-sm">No subject data yet</div>
          )
        )}

        {/* Teachers tab */}
        {analyticsTab === 'teachers' && (
          teacherData.length > 0 ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <ResponsiveContainer width="100%" height={Math.max(200, teacherData.length * 44)}>
                <BarChart data={teacherData} layout="vertical" margin={{ top: 4, right: 36, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={grid} horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: axis, fontSize: 10 }} />
                  <YAxis type="category" dataKey="teacher" width={90}
                    tick={{ fill: axis, fontSize: 9, fontFamily: 'DM Sans' }}
                    tickFormatter={(v: any) => v.split(' ')[0]} />
                  <ReferenceLine x={30} stroke="#f43f5e" strokeDasharray="4 4" strokeOpacity={0.5} />
                  <Tooltip
                    contentStyle={{ background: cssVar('--chart-tooltip-bg') || '#1a1a26', border: `1px solid ${grid}`, borderRadius: 12, fontSize: 11 }}
                    labelStyle={{ color: cssVar('--text-primary') || '#fff' }}
                    formatter={(v: any, n: any) => [`${v}%`, (n === 'average' ? 'Avg Score' : 'Pass Rate')] as [string, string]}
                  />
                  <Bar dataKey="average" radius={[0, 6, 6, 0]} barSize={16} isAnimationActive animationDuration={1000}>
                    {teacherData.map((t, i) => (
                      <Cell key={t.teacher}
                        fill={['#3b82f6','#8b5cf6','#10b981','#f59e0b','#f43f5e','#06b6d4'][i % 6]} />
                    ))}
                  </Bar>
                  <Bar dataKey="pass_rate" radius={[0, 6, 6, 0]} barSize={6} fill="#10b981" fillOpacity={0.45} isAnimationActive animationDuration={1200} />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-2">
                {teacherData.map((t, i) => {
                  const color = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#f43f5e','#06b6d4'][i % 6];
                  return (
                    <div key={t.email} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface-900">
                      <div className="w-7 h-7 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                        style={{ backgroundColor: `${color}22`, color }}>
                        {t.teacher.split(' ').map(w => w[0]).join('').slice(0, 2)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-display font-medium text-primary truncate">{t.teacher}</p>
                        <p className="text-[10px] text-secondary">{t.exam_count} exams · {t.student_count} students</p>
                      </div>
                      <RadialGauge value={t.average} color={color} size={44} />
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-muted text-sm">No teacher data yet</div>
          )
        )}
      </div>

      {/* ── At-risk alert banner ───────────────────────────────────── */}
      {(data?.at_risk_count ?? 0) > 0 && (
        <div className="card p-4 border-rose-500/30" style={{ background: 'linear-gradient(135deg, rgba(244,63,94,0.05) 0%, transparent 60%)' }}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-xl bg-rose-500/15 flex items-center justify-center flex-shrink-0">
                <AlertTriangle size={16} className="text-rose-400" />
              </div>
              <div>
                <p className="font-display font-semibold text-rose-400 text-sm">
                  {data?.at_risk_count} student{data?.at_risk_count !== 1 ? 's' : ''} at risk
                </p>
                <p className="text-muted text-xs mt-0.5 hidden sm:block">Below 30% threshold — consider early intervention</p>
              </div>
            </div>
            <Link to="/at-risk" className="flex items-center gap-1.5 text-xs font-display font-semibold text-rose-400 hover:text-rose-300 transition-colors whitespace-nowrap flex-shrink-0 bg-rose-500/10 hover:bg-rose-500/20 px-3 py-2 rounded-xl">
              Review <ArrowRight size={12} />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
