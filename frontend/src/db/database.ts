/**
 * MathPlatform — Local IndexedDB via `idb`
 * Full offline database layer for PWA support.
 */
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

export interface PendingScore {
  id?: number;
  exam_id: number;
  student_id_code: string;
  score: number;
  is_absent: boolean;
  remarks: string;
  queued_at: number;
  retry_count: number;
}

export interface PendingStudent {
  id?: number;
  first_name: string;
  last_name: string;
  email: string;
  student_id: string;
  classroom_id?: number;
  queued_at: number;
}

export interface CachedStudent {
  id: number;
  student_id: string;
  full_name: string;
  first_name: string;
  last_name: string;
  email: string;
  classroom: number | null;
  classroom_name: string | null;
  grade_level: string | null;
  is_active: boolean;
  region: string;
  cached_at: number;
}

export interface CachedExam {
  id: number;
  title: string;
  exam_type: string;
  term: string;
  academic_year: string;
  exam_date: string;
  max_score: number;
  passing_score: number;
  classrooms: number[];
  is_published: boolean;
  score_count: number;
  average_score: number | null;
  pass_rate: number | null;
  cached_at: number;
}

export interface CachedClassroom {
  id: number;
  name: string;
  grade_level_name: string;
  academic_year: string;
  student_count: number;
  is_active: boolean;
  cached_at: number;
}

export interface SyncMeta {
  entity: string;
  last_synced: number;
  record_count: number;
}

interface MathDB extends DBSchema {
  pending_scores: {
    key: number;
    value: PendingScore;
    indexes: { by_exam: number };
  };
  pending_students: {
    key: number;
    value: PendingStudent;
  };
  cache_students: {
    key: number;
    value: CachedStudent;
    indexes: { by_classroom: number };
  };
  cache_exams: {
    key: number;
    value: CachedExam;
    indexes: { by_year: string };
  };
  cache_classrooms: {
    key: number;
    value: CachedClassroom;
  };
  cache_scores: {
    key: number;
    value: { exam_id: number; scores: object[]; cached_at: number };
  };
  sync_meta: {
    key: string;
    value: SyncMeta;
  };
}

let _db: IDBPDatabase<MathDB> | null = null;

async function getDB(): Promise<IDBPDatabase<MathDB>> {
  if (_db) return _db;
  _db = await openDB<MathDB>('mathplatform_v2', 1, {
    upgrade(db) {
      const ps = db.createObjectStore('pending_scores', { keyPath: 'id', autoIncrement: true });
      ps.createIndex('by_exam', 'exam_id');
      db.createObjectStore('pending_students', { keyPath: 'id', autoIncrement: true });
      const cs = db.createObjectStore('cache_students', { keyPath: 'id' });
      cs.createIndex('by_classroom', 'classroom');
      const ce = db.createObjectStore('cache_exams', { keyPath: 'id' });
      ce.createIndex('by_year', 'academic_year');
      db.createObjectStore('cache_classrooms', { keyPath: 'id' });
      db.createObjectStore('cache_scores', { keyPath: 'exam_id' });
      db.createObjectStore('sync_meta', { keyPath: 'entity' });
    },
  });
  return _db;
}

// ── Pending Scores ────────────────────────────────────────────────────────────
export async function addPendingScore(item: Omit<PendingScore, 'id' | 'queued_at' | 'retry_count'>) {
  const db = await getDB();
  return db.add('pending_scores', { ...item, queued_at: Date.now(), retry_count: 0 });
}
export async function getAllPendingScores(): Promise<PendingScore[]> {
  const db = await getDB(); return db.getAll('pending_scores');
}
export async function deletePendingScore(id: number) {
  const db = await getDB(); return db.delete('pending_scores', id);
}
export async function incrementRetry(id: number) {
  const db = await getDB();
  const item = await db.get('pending_scores', id);
  if (item) await db.put('pending_scores', { ...item, retry_count: item.retry_count + 1 });
}
export async function getPendingScoreCount(): Promise<number> {
  const db = await getDB(); return db.count('pending_scores');
}

// ── Pending Students ──────────────────────────────────────────────────────────
export async function addPendingStudent(item: Omit<PendingStudent, 'id' | 'queued_at'>) {
  const db = await getDB();
  return db.add('pending_students', { ...item, queued_at: Date.now() });
}
export async function getAllPendingStudents(): Promise<PendingStudent[]> {
  const db = await getDB(); return db.getAll('pending_students');
}
export async function deletePendingStudent(id: number) {
  const db = await getDB(); return db.delete('pending_students', id);
}

// ── Cache: Students ───────────────────────────────────────────────────────────
export async function cacheStudents(students: CachedStudent[]) {
  const db = await getDB();
  const tx = db.transaction('cache_students', 'readwrite');
  await Promise.all([...students.map(s => tx.store.put({ ...s, cached_at: Date.now() })), tx.done]);
  await updateSyncMeta('students', students.length);
}
export async function getCachedStudents(): Promise<CachedStudent[]> {
  const db = await getDB(); return db.getAll('cache_students');
}

// ── Cache: Exams ──────────────────────────────────────────────────────────────
export async function cacheExams(exams: CachedExam[]) {
  const db = await getDB();
  const tx = db.transaction('cache_exams', 'readwrite');
  await Promise.all([...exams.map(e => tx.store.put({ ...e, cached_at: Date.now() })), tx.done]);
  await updateSyncMeta('exams', exams.length);
}
export async function getCachedExams(): Promise<CachedExam[]> {
  const db = await getDB(); return db.getAll('cache_exams');
}

// ── Cache: Classrooms ─────────────────────────────────────────────────────────
export async function cacheClassrooms(classrooms: CachedClassroom[]) {
  const db = await getDB();
  const tx = db.transaction('cache_classrooms', 'readwrite');
  await Promise.all([...classrooms.map(c => tx.store.put({ ...c, cached_at: Date.now() })), tx.done]);
  await updateSyncMeta('classrooms', classrooms.length);
}
export async function getCachedClassrooms(): Promise<CachedClassroom[]> {
  const db = await getDB(); return db.getAll('cache_classrooms');
}

// ── Cache: Scores ─────────────────────────────────────────────────────────────
export async function cacheExamScores(examId: number, scores: object[]) {
  const db = await getDB();
  await db.put('cache_scores', { exam_id: examId, scores, cached_at: Date.now() });
}
export async function getCachedExamScores(examId: number): Promise<object[] | null> {
  const db = await getDB();
  const entry = await db.get('cache_scores', examId);
  return entry?.scores ?? null;
}

// ── Sync Meta ─────────────────────────────────────────────────────────────────
export async function updateSyncMeta(entity: string, count: number) {
  const db = await getDB();
  await db.put('sync_meta', { entity, last_synced: Date.now(), record_count: count });
}
export async function getAllSyncMeta(): Promise<SyncMeta[]> {
  const db = await getDB(); return db.getAll('sync_meta');
}

// ── Clear ─────────────────────────────────────────────────────────────────────
export async function clearAllCaches() {
  const db = await getDB();
  const tx = db.transaction(
    ['cache_students','cache_exams','cache_classrooms','cache_scores','sync_meta'], 'readwrite'
  );
  await Promise.all([
    tx.objectStore('cache_students').clear(),
    tx.objectStore('cache_exams').clear(),
    tx.objectStore('cache_classrooms').clear(),
    tx.objectStore('cache_scores').clear(),
    tx.objectStore('sync_meta').clear(),
    tx.done,
  ]);
}
export async function clearPendingQueue() {
  const db = await getDB();
  const tx = db.transaction(['pending_scores','pending_students'], 'readwrite');
  await Promise.all([
    tx.objectStore('pending_scores').clear(),
    tx.objectStore('pending_students').clear(),
    tx.done,
  ]);
}
