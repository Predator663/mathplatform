import { useQuery } from '@tanstack/react-query';
import { Users, BookOpen, AlertTriangle, TrendingUp, ArrowRight } from 'lucide-react';
import { analyticsApi } from '../../api';
import { LoadingPage, StatCard } from '../../components/ui';
import { formatDate, EXAM_TYPE_LABELS, TERM_LABELS } from '../../utils';
import { useAuthStore } from '../../store/auth';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip,
} from 'recharts';
import type { DashboardSummary } from '../../types';

const ChartTooltip = ({ active, payload, label }: { active?: boolean; payload?: { value: number; payload?: { date: string } }[]; label?: string }) => {
  if (active && payload?.length) {
    return (
      <div className="card px-3 py-2 text-xs shadow-xl">
        <p className="font-display font-semibold text-primary">{label}</p>
        <p className="text-secondary">{payload[0].payload?.date}</p>
      </div>
    );
  }
  return null;
};

function getGreeting() {
  const h = new Date().getHours();
  return h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
}

export default function DashboardPage() {
  const { user } = useAuthStore();
  const { data, isLoading } = useQuery<DashboardSummary>({
    queryKey: ['dashboard'],
    queryFn: () => analyticsApi.dashboard().then(r => r.data),
  });

  if (isLoading) return <LoadingPage />;

  const chartData = (data?.recent_exams ?? []).map((e, i) => ({
    name: e.title.length > 12 ? e.title.slice(0, 12) + '…' : e.title,
    date: formatDate(e.exam_date),
    seq: i + 1,            // numeric — used as the Area dataKey
  }));

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      {/* Header */}
      <div>
        <h1 className="page-title">
          Good {getGreeting()},{' '}
          <span className="text-gradient">{user?.first_name}</span>
        </h1>
        <p className="text-muted mt-1 text-sm">Tanzania Curriculum · Mathematics Analytics Platform</p>
      </div>

      {/* Stats — 2 cols mobile, 4 cols desktop */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 md:gap-4">
        <StatCard label="Students" value={data?.total_students ?? 0}
          sub={`${data?.total_classrooms ?? 0} classrooms`} color="blue" icon={<Users size={14} />} />
        <StatCard label="Exams" value={data?.total_exams ?? 0}
          sub="All terms" color="violet" icon={<BookOpen size={14} />} />
        <StatCard
          label="Class Average"
          value={data?.overall_average != null ? `${data.overall_average}%` : '—'}
          sub="All exams" color="green" icon={<TrendingUp size={14} />} />
        <StatCard label="At Risk" value={data?.at_risk_count ?? 0}
          sub="Need attention" color="rose" icon={<AlertTriangle size={14} />} />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 card p-4 md:p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title">Recent Exams</h2>
            <Link to="/exams" className="text-xs text-azure-400 hover:text-azure-300 flex items-center gap-1 transition-colors">
              View all <ArrowRight size={12} />
            </Link>
          </div>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                <XAxis dataKey="name" tick={{ fill: '#3d3d55', fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={false} width={0} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="seq" stroke="#3b82f6" fill="url(#grad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-40 flex items-center justify-center text-muted text-sm">No exam data yet</div>
          )}
        </div>

        {/* Recent exams list */}
        <div className="card p-4 md:p-6">
          <h2 className="section-title mb-4">Latest Exams</h2>
          <div className="flex flex-col gap-2">
            {data?.recent_exams?.length ? data.recent_exams.map(exam => (
              <Link
                key={exam.id} to={`/exams/${exam.id}`}
                className="flex items-start justify-between gap-2 p-3 rounded-xl bg-surface-900 hover:bg-surface-700 transition-colors group"
              >
                <div className="min-w-0">
                  <p className="text-sm font-display font-medium text-primary truncate group-hover:text-azure-400 transition-colors">
                    {exam.title}
                  </p>
                  <p className="text-xs text-secondary mt-0.5">
                    {EXAM_TYPE_LABELS[exam.exam_type] ?? exam.exam_type} · {TERM_LABELS[exam.term] ?? exam.term}
                  </p>
                </div>
                <p className="text-xs text-secondary whitespace-nowrap flex-shrink-0">{formatDate(exam.exam_date)}</p>
              </Link>
            )) : (
              <p className="text-muted text-sm text-center py-6">No exams yet</p>
            )}
          </div>
        </div>
      </div>

      {/* At-risk alert */}
      {(data?.at_risk_count ?? 0) > 0 && (
        <div className="card p-4 md:p-5 border-rose-500/20">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <AlertTriangle size={16} className="text-rose-400 flex-shrink-0" />
              <div>
                <p className="font-display font-semibold text-rose-400 text-sm">
                  {data?.at_risk_count} student{data?.at_risk_count !== 1 ? 's' : ''} at risk
                </p>
                <p className="text-muted text-xs mt-0.5 hidden sm:block">Review performance and consider early intervention</p>
              </div>
            </div>
            <Link to="/at-risk" className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1 transition-colors whitespace-nowrap flex-shrink-0">
              View <ArrowRight size={12} />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
