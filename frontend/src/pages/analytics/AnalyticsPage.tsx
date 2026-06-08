import { useNavigate } from 'react-router-dom';
import { BarChart3, User, AlertTriangle, GitCompare } from 'lucide-react';

const cards = [
  {
    icon: User,
    title: 'Student Analytics',
    description: 'Dive into individual student performance — score timelines, topic mastery radar, moving averages, and grade trends.',
    action: 'Browse Students',
    to: '/students',
    color: 'azure',
  },
  {
    icon: BarChart3,
    title: 'Class Analytics',
    description: 'Analyse a full classroom\'s performance over time including score distributions, pass rates, and exam-by-exam breakdowns.',
    action: 'Open Class View',
    to: '/analytics/class',
    color: 'violet',
  },
  {
    icon: AlertTriangle,
    title: 'At-Risk Tracker',
    description: 'Automatically identifies students with declining scores or performance below the passing threshold.',
    action: 'View At-Risk',
    to: '/at-risk',
    color: 'rose',
  },
  {
    icon: GitCompare,
    title: 'Comparative Analysis',
    description: 'Side-by-side classroom comparisons across exam periods, terms, or academic years.',
    action: 'Compare Classes',
    to: '/analytics/compare',
    color: 'green',
  },
];

const colorMap: Record<string, string> = {
  azure: 'text-azure-400 bg-azure-500/10 border-azure-500/20 hover:border-azure-500/40',
  violet: 'text-violet-400 bg-violet-500/10 border-violet-500/20 hover:border-violet-500/40',
  rose: 'text-rose-400 bg-rose-500/10 border-rose-500/20 hover:border-rose-500/40',
  green: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20 hover:border-emerald-500/40',
};

const iconBg: Record<string, string> = {
  azure: 'bg-azure-500/15 text-azure-400',
  violet: 'bg-violet-500/15 text-violet-400',
  rose: 'bg-rose-500/15 text-rose-400',
  green: 'bg-emerald-500/15 text-emerald-400',
};

export default function AnalyticsPage() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div>
        <h1 className="page-title">Analytics</h1>
        <p className="text-muted mt-1">Choose an analytics view to explore student and class performance.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cards.map(({ icon: Icon, title, description, action, to, color }) => (
          <button
            key={title}
            onClick={() => navigate(to)}
            className={`card p-6 text-left transition-all duration-200 border hover:-translate-y-0.5 hover:shadow-xl ${colorMap[color]}`}
          >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${iconBg[color]}`}>
              <Icon size={18} />
            </div>
            <h3 className="font-display font-bold text-lg text-primary mb-2">{title}</h3>
            <p className="text-muted text-sm leading-relaxed mb-4">{description}</p>
            <span className={`text-sm font-display font-semibold ${colorMap[color].split(' ')[0]}`}>
              {action} →
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
