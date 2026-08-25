import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import { Crown, Trophy, Medal, TrendingUp, Download, FileSpreadsheet, ChevronLeft, AlertTriangle, RotateCcw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { leaguesApi, studentsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Select } from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import { downloadBlob, apiErrorMessage } from '../../utils';
import type { HallOfFame, Classroom, PaginatedResponse } from '../../types';

function listFrom<T>(data: PaginatedResponse<T> | T[] | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results ?? [];
}

function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center px-4">
      <AlertTriangle size={36} className="text-rose-400" />
      <p className="font-display font-semibold text-primary">Couldn't load the Hall of Fame</p>
      <p className="text-muted max-w-sm text-sm">{message}</p>
      <Button variant="secondary" size="sm" onClick={onRetry}><RotateCcw size={14} /> Try again</Button>
    </div>
  );
}



const RANK_STYLES = [
  'bg-gradient-to-r from-amber-500/20 to-amber-500/5 border-amber-500/40',
  'bg-gradient-to-r from-slate-400/20 to-slate-400/5 border-slate-400/40',
  'bg-gradient-to-r from-orange-600/20 to-orange-600/5 border-orange-600/40',
];

export default function HallOfFamePage() {
  const { user } = useAuthStore();
  const [classroomId, setClassroomId] = useState('');
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null);

  const { data: classroomsData } = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms-for-hof'],
    queryFn: () => studentsApi.classrooms({ page_size: 100 }).then(r => r.data),
  });
  const classrooms = listFrom(classroomsData);

  const { data: hof, isLoading, isError, error, refetch } = useQuery<HallOfFame>({
    queryKey: ['hall-of-fame', classroomId],
    queryFn: () => leaguesApi.hallOfFame(classroomId ? { classroom: classroomId } : {}).then(r => r.data),
    retry: 1,
  });

  if (user?.role === 'student' || user?.role === 'parent') {
    return <EmptyState icon={<Trophy size={40} />} title="Not available" message="The Hall of Fame is a teacher/admin analytics view." />;
  }

  const handleExport = async (kind: 'pdf' | 'excel') => {
    setExporting(kind);
    try {
      const params = classroomId ? { classroom: classroomId } : {};
      const res = kind === 'pdf' ? await leaguesApi.exportHallOfFamePdf(params) : await leaguesApi.exportHallOfFameExcel(params);
      downloadBlob(res.data, `hall_of_fame.${kind === 'pdf' ? 'pdf' : 'xlsx'}`);
      toast.success('Export ready.');
    } catch {
      toast.error('Export failed.');
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Link to="/leagues" className="flex items-center gap-1.5 text-sm text-secondary hover:text-primary w-fit">
        <ChevronLeft size={16} /> Back to leagues
      </Link>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold text-primary flex items-center gap-2">
            <Trophy className="text-amber-400" /> Hall of Fame
          </h1>
          <p className="text-secondary text-sm mt-1">The best of the best — top-tier standings, reigning champions, and serial climbers.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Select
            value={classroomId} onChange={e => setClassroomId(e.target.value)}
            options={[{ value: '', label: 'All classrooms' }, ...classrooms.map(c => ({ value: c.id, label: c.name }))]}
          />
          <Button variant="secondary" size="sm" onClick={() => handleExport('pdf')} loading={exporting === 'pdf'}>
            <Download size={14} /> PDF
          </Button>
          <Button variant="secondary" size="sm" onClick={() => handleExport('excel')} loading={exporting === 'excel'}>
            <FileSpreadsheet size={14} /> Excel
          </Button>
        </div>
      </div>

      {isLoading ? <LoadingPage /> : isError ? (
        <ErrorPanel message={apiErrorMessage(error)} onRetry={() => refetch()} />
      ) : !hof ? (
        <ErrorPanel message="No data came back from the server." onRetry={() => refetch()} />
      ) : (
        <div className="flex flex-col gap-8">
          {/* Reigning Champions */}
          <section>
            <h2 className="font-display font-semibold text-lg text-primary flex items-center gap-2 mb-3">
              <Crown className="text-amber-400" size={18} /> Reigning Champions
            </h2>
            {hof.season_champions.length === 0 ? (
              <p className="text-muted text-sm">No seasons yet.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {hof.season_champions.map((c, i) => (
                  <motion.div
                    key={c.season_id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.04 }}
                    className="card p-4 flex items-center gap-3 border-amber-500/30"
                  >
                    <Crown className="text-amber-400 shrink-0" size={22} />
                    <div className="min-w-0">
                      <p className="font-display font-semibold text-primary truncate">{c.student_name}</p>
                      <p className="text-xs text-secondary truncate">{c.season_title} · {c.classroom}</p>
                      <p className="text-xs text-amber-400 font-mono mt-0.5">{c.group_name}% · {c.score}%</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </section>

          {/* Top-Tier Standings */}
          <section>
            <h2 className="font-display font-semibold text-lg text-primary flex items-center gap-2 mb-3">
              <Trophy className="text-azure-400" size={18} /> Top-Tier Standings
            </h2>
            {hof.top_tier.length === 0 ? (
              <p className="text-muted text-sm">No top-tier students yet.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {hof.top_tier.map((row, i) => (
                  <motion.div
                    key={`${row.student_id}-${row.season_title}`}
                    initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
                    className={`flex items-center justify-between rounded-xl border px-4 py-2.5 ${i < 3 ? RANK_STYLES[i] : 'bg-surface-800/40 border-surface'}`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold text-secondary w-6 text-center">{i < 3 ? <Medal size={16} className="inline" /> : `#${i + 1}`}</span>
                      <div>
                        <p className="font-display font-semibold text-primary text-sm">{row.student_name}</p>
                        <p className="text-xs text-muted">{row.classroom} · {row.season_title} · {row.group_name}%</p>
                      </div>
                    </div>
                    <span className="font-mono font-bold text-primary">{row.score}%</span>
                  </motion.div>
                ))}
              </div>
            )}
          </section>

          {/* Most Promoted */}
          <section>
            <h2 className="font-display font-semibold text-lg text-primary flex items-center gap-2 mb-3">
              <TrendingUp className="text-emerald-400" size={18} /> Most Promoted
            </h2>
            {hof.most_promoted.length === 0 ? (
              <p className="text-muted text-sm">No promotions recorded yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {hof.most_promoted.map((row, i) => (
                  <motion.div
                    key={row.student_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
                    className="card p-3 flex items-center justify-between"
                  >
                    <span className="text-sm text-primary/90 truncate">{row.student_name}</span>
                    <span className="badge bg-emerald-500/15 text-emerald-400 font-mono">{row.promotion_count}×</span>
                  </motion.div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
