/**
 * usePWASync — Central sync engine.
 *
 * ONLY runs when isAuthenticated === true.
 * PUSH only when pendingCount > 0.
 * PULL only when cache is stale (>30 min) or forced on reconnect.
 * One pull per page-load session max (initialPullDone flag).
 */
import {
  useState, useEffect, useCallback, useRef,
  createContext, useContext, type ReactNode,
} from 'react';
import toast from 'react-hot-toast';
import { useAuthStore } from '../store/auth';
import {
  getAllPendingScores, deletePendingScore, incrementRetry, getPendingScoreCount,
  getAllPendingStudents, deletePendingStudent,
  addPendingScore, addPendingStudent,
  cacheStudents, cacheExams, cacheClassrooms,
  getAllSyncMeta,
  type PendingScore, type PendingStudent,
} from '../db';
import { examsApi, studentsApi } from '../api';

const MAX_RETRIES   = 3;
const CACHE_TTL_MS  = 30 * 60 * 1000;
const SYNC_INTERVAL = 5  * 60 * 1000;

let syncLock        = false;
let initialPullDone = false;

function isCacheStale(ts?: number) {
  return !ts || Date.now() - ts > CACHE_TTL_MS;
}

export function usePWASync() {
  const { isAuthenticated } = useAuthStore();

  const [isOnline, setIsOnline]     = useState(navigator.onLine);
  const [pendingCount, setPending]  = useState(0);
  const [isSyncing, setIsSyncing]   = useState(false);
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const [syncError, setSyncError]   = useState<string | null>(null);
  const mountedRef = useRef(true);

  const refreshCount = useCallback(async () => {
    try {
      const n = await getPendingScoreCount();
      if (mountedRef.current) setPending(n);
    } catch { /**/ }
  }, []);

  const pushPendingScores = useCallback(async (): Promise<{ synced: number; failed: number }> => {
    const items = await getAllPendingScores();
    if (!items.length) return { synced: 0, failed: 0 };
    const byExam = new Map<number, PendingScore[]>();
    items.forEach(i => {
      if (!byExam.has(i.exam_id)) byExam.set(i.exam_id, []);
      byExam.get(i.exam_id)!.push(i);
    });
    let synced = 0, failed = 0;
    for (const [examId, group] of byExam) {
      const toSend = group.filter(i => (i.retry_count ?? 0) < MAX_RETRIES);
      if (!toSend.length) { failed += group.length; continue; }
      try {
        const res  = await examsApi.bulkScores(examId, { scores: toSend.map(g => ({ student_id: g.student_id_code, score: g.score, is_absent: g.is_absent, remarks: g.remarks })) });
        const bad  = new Set(((res.data as { errors: { student_id: string }[] }).errors ?? []).map(e => e.student_id));
        for (const item of toSend) {
          if (item.id == null) continue;
          if (bad.has(item.student_id_code)) { await incrementRetry(item.id); failed++; }
          else { await deletePendingScore(item.id); synced++; }
        }
      } catch {
        for (const item of toSend) if (item.id != null) await incrementRetry(item.id);
        failed += toSend.length;
      }
    }
    return { synced, failed };
  }, []);

  const pushPendingStudents = useCallback(async (): Promise<number> => {
    const items = await getAllPendingStudents();
    if (!items.length) return 0;
    let synced = 0;
    for (const item of items) {
      try {
        await studentsApi.createStudent({ first_name: item.first_name, last_name: item.last_name, email: item.email, student_id: item.student_id, classroom: item.classroom_id });
        if (item.id != null) await deletePendingStudent(item.id);
        synced++;
      } catch { /**/ }
    }
    return synced;
  }, []);

  const pullFreshData = useCallback(async (force = false) => {
    if (!force) {
      const meta = await getAllSyncMeta();
      const sm   = meta.find(m => m.entity === 'students');
      const em   = meta.find(m => m.entity === 'exams');
      if (!isCacheStale(sm?.last_synced) && !isCacheStale(em?.last_synced)) return;
    }
    const [sRes, eRes, cRes] = await Promise.allSettled([
      studentsApi.students({ page_size: 500 }),
      examsApi.exams({ page_size: 500 }),
      studentsApi.classrooms({ page_size: 200 }),
    ]);
    const extract = (r: PromiseSettledResult<{ data: unknown }>) =>
      r.status === 'fulfilled'
        ? (Array.isArray(r.value.data) ? r.value.data : ((r.value.data as { results: object[] }).results ?? []))
        : [];
    const now = Date.now();
    await cacheStudents(extract(sRes).map((s: object) => ({ ...s, cached_at: now })) as Parameters<typeof cacheStudents>[0]);
    await cacheExams(extract(eRes).map((e: object) => ({ ...e, cached_at: now })) as Parameters<typeof cacheExams>[0]);
    await cacheClassrooms(extract(cRes).map((c: object) => ({ ...c, cached_at: now })) as Parameters<typeof cacheClassrooms>[0]);
  }, []);

  const syncNow = useCallback(async (opts: { silent?: boolean; forcePull?: boolean } = {}) => {
    if (!isAuthenticated || syncLock || !navigator.onLine) return;
    syncLock = true;
    if (mountedRef.current) { setIsSyncing(true); setSyncError(null); }
    try {
      const pending = await getPendingScoreCount();
      if (pending > 0) {
        const [sr, ss] = await Promise.all([pushPendingScores(), pushPendingStudents()]);
        const total = sr.synced + ss;
        if (total > 0 && !opts.silent) toast.success(`✓ Synced ${total} offline change${total !== 1 ? 's' : ''}`);
        if (sr.failed > 0 && !opts.silent) toast.error(`${sr.failed} item${sr.failed !== 1 ? 's' : ''} failed to sync`);
      }
      await pullFreshData(opts.forcePull ?? false);
      if (mountedRef.current) setLastSynced(new Date());
    } catch (e) {
      if (mountedRef.current) setSyncError(e instanceof Error ? e.message : 'Sync failed');
    } finally {
      syncLock = false;
      if (mountedRef.current) setIsSyncing(false);
      await refreshCount();
    }
  }, [isAuthenticated, pushPendingScores, pushPendingStudents, pullFreshData, refreshCount]);

  useEffect(() => {
    mountedRef.current = true;

    const handleOnline = () => {
      setIsOnline(true);
      if (!isAuthenticated) return;
      toast('Back online — syncing…', { icon: '🔄', duration: 2000 });
      syncNow({ silent: false, forcePull: true });
    };
    const handleOffline = () => {
      setIsOnline(false);
      if (isAuthenticated) toast('Offline — changes will sync when reconnected', { icon: '📡', duration: 4000 });
    };

    window.addEventListener('online',  handleOnline);
    window.addEventListener('offline', handleOffline);

    if (isAuthenticated) {
      refreshCount();
      if (navigator.onLine && !initialPullDone) {
        initialPullDone = true;
        syncNow({ silent: true, forcePull: false });
      }
    }

    const interval = setInterval(() => {
      if (isAuthenticated && navigator.onLine) syncNow({ silent: true, forcePull: false });
    }, SYNC_INTERVAL);

    return () => {
      mountedRef.current = false;
      window.removeEventListener('online',  handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, [isAuthenticated, syncNow, refreshCount]);

  useEffect(() => {
    if (!isAuthenticated) {
      initialPullDone = false;
      setPending(0);
      setLastSynced(null);
      setSyncError(null);
    }
  }, [isAuthenticated]);

  return {
    isOnline, pendingCount, isSyncing, lastSynced, syncError,
    syncNow: () => syncNow({ silent: false, forcePull: true }),
    queueScore: useCallback(async (item: Omit<PendingScore, 'id' | 'queued_at' | 'retry_count'>) => {
      await addPendingScore(item); await refreshCount();
    }, [refreshCount]),
    queueStudent: useCallback(async (item: Omit<PendingStudent, 'id' | 'queued_at'>) => {
      await addPendingStudent(item); await refreshCount();
    }, [refreshCount]),
    refreshCount,
  };
}

const SyncContext = createContext<ReturnType<typeof usePWASync> | null>(null);
export function SyncProvider({ children }: { children: ReactNode }) {
  const sync = usePWASync();
  return <SyncContext.Provider value={sync}>{children}</SyncContext.Provider>;
}
export function useSync() {
  const ctx = useContext(SyncContext);
  if (!ctx) throw new Error('useSync must be used inside <SyncProvider>');
  return ctx;
}
