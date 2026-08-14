import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import {
  BarChart3, User, AlertTriangle, GitCompare, ShieldAlert, GitBranch,
  ShieldCheck, Scale, Rows3, Users2, Search, ArrowUpDown, X, Sparkles, Brain,
} from 'lucide-react';
import { useAuthStore } from '../../store/auth';
import { TiltCard, Reveal, EmptyState, Select } from '../../components/ui';

type Category = 'Student' | 'Classroom' | 'Comparison' | 'Risk & Integrity' | 'Curriculum';

interface AnalyticsCard {
  icon: typeof User;
  title: string;
  description: string;
  action: string;
  to: string;
  color: 'azure' | 'violet' | 'rose' | 'green' | 'amber';
  category: Category;
}

const cards: AnalyticsCard[] = [
  {
    icon: User,
    title: 'Student Analytics',
    description: 'Dive into individual student performance — score timelines, topic mastery radar, moving averages, and grade trends.',
    action: 'Browse Students',
    to: '/students',
    color: 'azure',
    category: 'Student',
  },
  {
    icon: BarChart3,
    title: 'Class Analytics',
    description: "Analyse a full classroom's performance over time including score distributions, pass rates, and exam-by-exam breakdowns.",
    action: 'Open Class View',
    to: '/analytics/class',
    color: 'violet',
    category: 'Classroom',
  },
  {
    icon: Rows3,
    title: 'Stream Comparison',
    description: 'Side-by-side averages, pass rates, and at-risk counts for every stream in a classroom (e.g. Form 2 "A" vs "B" vs "C").',
    action: 'Compare Streams',
    to: '/analytics/class',
    color: 'green',
    category: 'Classroom',
  },
  {
    icon: AlertTriangle,
    title: 'At-Risk Tracker',
    description: 'Automatically identifies students with declining scores or performance below the passing threshold.',
    action: 'View At-Risk',
    to: '/at-risk',
    color: 'rose',
    category: 'Risk & Integrity',
  },
  {
    icon: GitCompare,
    title: 'Comparative Analysis',
    description: 'Side-by-side classroom comparisons across exam periods, terms, or academic years.',
    action: 'Compare Classes',
    to: '/analytics/compare',
    color: 'green',
    category: 'Classroom',
  },
  {
    icon: Users2,
    title: 'Compare Students',
    description: 'Side-by-side progress for 2 or more students — trends, topic mastery, and growth — great for a 1:1 motivational conversation, with a printable PDF to hand over.',
    action: 'Compare Students',
    to: '/analytics/compare-students',
    color: 'azure',
    category: 'Comparison',
  },
  {
    icon: Brain,
    title: 'Topic Intelligence',
    description: 'School-wide topic mastery — a difficulty ranking, a classroom × topic heatmap, and the topics trending up or down, combining exam and daily quiz data.',
    action: 'Explore Topics',
    to: '/analytics/topics',
    color: 'violet',
    category: 'Curriculum',
  },
  {
    icon: ShieldAlert,
    title: 'Composite Risk Scores',
    description: 'A weighted risk score combining trend, volatility, topic weakness, and pass margin — with the factors behind each flag.',
    action: 'View Risk Scores',
    to: '/analytics/risk',
    color: 'amber',
    category: 'Risk & Integrity',
  },
  {
    icon: GitBranch,
    title: 'Topic Dependencies',
    description: 'Detects when weakness in one topic statistically predicts weakness in another, surfacing root-cause chains.',
    action: 'Explore Dependencies',
    to: '/analytics/dependencies',
    color: 'violet',
    category: 'Curriculum',
  },
  {
    icon: ShieldCheck,
    title: 'Grade Integrity',
    description: 'Mines score-edit history for boundary crossings, large jumps, and unusual editor rates worth a human review.',
    action: 'View Integrity Flags',
    to: '/analytics/integrity',
    color: 'azure',
    category: 'Risk & Integrity',
  },
];

const adminCard: AnalyticsCard = {
  icon: Scale,
  title: 'Teacher Grading Consistency',
  description: "Compares each teacher's average score on shared topics against their peers to flag lenient or harsh grading.",
  action: 'View Audit',
  to: '/analytics/teacher-consistency',
  color: 'rose',
  category: 'Risk & Integrity',
};

const colorMap: Record<AnalyticsCard['color'], string> = {
  azure: 'text-azure-400 border-azure-500/20 hover:border-azure-500/40',
  violet: 'text-violet-400 border-violet-500/20 hover:border-violet-500/40',
  rose: 'text-rose-400 border-rose-500/20 hover:border-rose-500/40',
  green: 'text-emerald-400 border-emerald-500/20 hover:border-emerald-500/40',
  amber: 'text-amber-400 border-amber-500/20 hover:border-amber-500/40',
};

const glowMap: Record<AnalyticsCard['color'], string> = {
  azure: 'hover:shadow-azure-500/10',
  violet: 'hover:shadow-violet-500/10',
  rose: 'hover:shadow-rose-500/10',
  green: 'hover:shadow-emerald-500/10',
  amber: 'hover:shadow-amber-500/10',
};

const iconBg: Record<AnalyticsCard['color'], string> = {
  azure: 'bg-azure-500/15 text-azure-400',
  violet: 'bg-violet-500/15 text-violet-400',
  rose: 'bg-rose-500/15 text-rose-400',
  green: 'bg-emerald-500/15 text-emerald-400',
  amber: 'bg-amber-500/15 text-amber-400',
};

// ── "Most visited" tracking — real usage data, not decoration. Every card
// click bumps a counter in localStorage, which the "Most Visited" sort and
// the small visited-dot indicator both read from. ─────────────────────────
const VISITS_KEY = 'analytics_hub_visits';

function readVisits(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(VISITS_KEY) || '{}');
  } catch {
    return {};
  }
}

function recordVisit(to: string) {
  try {
    const visits = readVisits();
    visits[to] = (visits[to] || 0) + 1;
    localStorage.setItem(VISITS_KEY, JSON.stringify(visits));
  } catch {
    // localStorage unavailable (private browsing, etc.) — visit tracking is a nice-to-have, never worth erroring over.
  }
}

type SortMode = 'recommended' | 'az' | 'visited';

export default function AnalyticsPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin';
  const allCards = useMemo(() => (isAdmin ? [...cards, adminCard] : cards), [isAdmin]);
  const categories = useMemo(() => {
    const set = new Set<Category>(allCards.map(c => c.category));
    return Array.from(set);
  }, [allCards]);

  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<Category | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>('recommended');
  const [visits, setVisits] = useState<Record<string, number>>({});

  useEffect(() => { setVisits(readVisits()); }, []);

  const handleOpen = (to: string) => {
    recordVisit(to);
    navigate(to);
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let result = allCards.filter(c => {
      const matchesCategory = !activeCategory || c.category === activeCategory;
      const matchesSearch = !q || c.title.toLowerCase().includes(q) || c.description.toLowerCase().includes(q);
      return matchesCategory && matchesSearch;
    });
    if (sortMode === 'az') {
      result = [...result].sort((a, b) => a.title.localeCompare(b.title));
    } else if (sortMode === 'visited') {
      result = [...result].sort((a, b) => (visits[b.to] || 0) - (visits[a.to] || 0));
    }
    return result;
  }, [allCards, search, activeCategory, sortMode, visits]);

  const hasActiveFilters = !!search || !!activeCategory || sortMode !== 'recommended';
  const clearAll = () => { setSearch(''); setActiveCategory(null); setSortMode('recommended'); };

  return (
    <div className="flex flex-col gap-6 page-enter">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3"
      >
        <div>
          <h1 className="page-title flex items-center gap-2">
            <span className="text-gradient">Analytics</span>
            <Sparkles size={18} className="text-violet-400" />
          </h1>
          <p className="text-muted mt-1">Choose an analytics view to explore student and class performance.</p>
        </div>
        <div className="text-xs text-secondary font-display">
          {filtered.length} of {allCards.length} tool{allCards.length !== 1 ? 's' : ''}
        </div>
      </motion.div>

      {/* ── Search + sort ─────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary" />
          <input
            className="input pl-10 w-full"
            placeholder="Search analytics tools…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="w-full sm:w-56 flex items-center gap-2">
          <ArrowUpDown size={14} className="text-secondary flex-shrink-0" />
          <Select
            value={sortMode}
            onChange={e => setSortMode(e.target.value as SortMode)}
            options={[
              { value: 'recommended', label: 'Recommended order' },
              { value: 'az', label: 'A–Z' },
              { value: 'visited', label: 'Most visited' },
            ]}
            className="w-full"
          />
        </div>
      </div>

      {/* ── Category filter pills, with a sliding indicator ─────────────── */}
      <LayoutGroup id="analytics-category-pills">
        <div className="flex items-center gap-2 flex-wrap">
          {[{ label: 'All', value: null as Category | null }, ...categories.map(c => ({ label: c, value: c }))].map(({ label, value }) => {
            const active = activeCategory === value;
            return (
              <button
                key={label}
                onClick={() => setActiveCategory(value)}
                className={`relative px-3.5 py-1.5 rounded-full text-xs font-display font-semibold transition-colors ${
                  active ? 'text-white' : 'text-secondary hover:text-primary'
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="active-category-pill"
                    className="absolute inset-0 rounded-full bg-gradient-to-r from-azure-500 to-violet-500"
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
                <span className="relative z-10">{label}</span>
              </button>
            );
          })}
          {hasActiveFilters && (
            <button
              onClick={clearAll}
              className="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-display font-medium text-secondary hover:text-primary transition-colors"
            >
              <X size={12} /> Clear
            </button>
          )}
        </div>
      </LayoutGroup>

      {/* ── Card grid ─────────────────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={<Search size={32} />}
          title="No matching analytics tools"
          message="Try a different search term or clear your filters."
        />
      ) : (
        <motion.div layout className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <AnimatePresence mode="popLayout">
            {filtered.map(({ icon: Icon, title, description, action, to, color, category }, i) => {
              const visited = (visits[to] || 0) > 0;
              return (
                <motion.div
                  key={title}
                  layout
                  initial={{ opacity: 0, scale: 0.94 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.94 }}
                  transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                >
                  <Reveal index={i}>
                    <TiltCard
                      onClick={() => handleOpen(to)}
                      aria-label={`${title} — ${action}`}
                      className={`p-6 text-left cursor-pointer border transition-shadow duration-200 hover:shadow-xl h-full ${colorMap[color]} ${glowMap[color]}`}
                      maxTilt={6}
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${iconBg[color]}`}>
                          <Icon size={18} />
                        </div>
                        <div className="flex items-center gap-1.5">
                          {visited && (
                            <span className={`w-1.5 h-1.5 rounded-full ${iconBg[color].split(' ')[0]}`} title="You've visited this before" />
                          )}
                          <span className="text-[10px] text-secondary uppercase tracking-widest font-display">{category}</span>
                        </div>
                      </div>
                      <h3 className="font-display font-bold text-lg text-primary mb-2">{title}</h3>
                      <p className="text-muted text-sm leading-relaxed mb-4">{description}</p>
                      <span className={`inline-flex items-center gap-1 text-sm font-display font-semibold group ${colorMap[color].split(' ')[0]}`}>
                        {action}
                        <motion.span initial={{ x: 0 }} whileHover={{ x: 3 }} className="inline-block">→</motion.span>
                      </span>
                    </TiltCard>
                  </Reveal>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}
