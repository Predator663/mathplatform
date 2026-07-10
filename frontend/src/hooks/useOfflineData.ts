/**
 * useOfflineData — offline-capable reads for the three entities we cache
 * locally (students, exams, classrooms).
 *
 * Caching was already wired up in usePWASync (cacheStudents / cacheExams /
 * cacheClassrooms get called on every successful pull), but nothing ever
 * read that cache back. As a result, opening a page like Mark Entry while
 * offline — or while the network request simply fails — showed a blank or
 * "not found" state instead of the data that was already on the device.
 *
 * These hooks try the network first. If that request errors out (offline,
 * timeout, etc.), they fall back to whatever was last saved in IndexedDB
 * instead of leaving the page empty.
 */
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { studentsApi, examsApi } from '../api';
import {
  getCachedStudents, getCachedExams, getCachedClassrooms,
  type CachedStudent, type CachedExam, type CachedClassroom,
} from '../db';
import type { StudentProfile, Exam, Classroom, PaginatedResponse } from '../types';

function toStudentProfile(c: CachedStudent): StudentProfile {
  return {
    id: c.id,
    student_id: c.student_id,
    full_name: c.full_name,
    first_name: c.first_name,
    last_name: c.last_name,
    email: c.email,
    classroom: c.classroom,
    classroom_name: c.classroom_name,
    grade_level: c.grade_level,
    education_level: null,
    date_of_birth: null,
    enrollment_date: '',
    is_active: c.is_active,
    notes: '',
    index_number: '',
    parent_name: '',
    parent_phone: '',
    district: '',
    region: c.region,
  };
}

function toExam(c: CachedExam): Exam {
  return {
    id: c.id,
    title: c.title,
    exam_type: c.exam_type as Exam['exam_type'],
    term: c.term as Exam['term'],
    academic_year: c.academic_year,
    exam_date: c.exam_date,
    max_score: c.max_score,
    passing_score: c.passing_score,
    passing_percentage: c.max_score ? Math.round((c.passing_score / c.max_score) * 1000) / 10 : 0,
    classrooms: c.classrooms,
    topic_weights: [],
    created_by: 0,
    created_by_name: '',
    description: '',
    is_published: c.is_published,
    created_at: '',
    updated_at: '',
    score_count: c.score_count,
    average_score: c.average_score,
    pass_rate: c.pass_rate,
    subject: 0,
    subject_name: '',
    subject_code: '',
    subject_color: '',
  };
}

function toClassroom(c: CachedClassroom): Classroom {
  return {
    id: c.id,
    name: c.name,
    grade_level: 0,
    grade_level_name: c.grade_level_name,
    grade_level_short: '',
    education_level: 'o_level',
    education_level_display: '',
    stream: 'general',
    stream_display: '',
    academic_year: c.academic_year,
    teacher_names: [],
    teacher_assignments: [],
    is_active: c.is_active,
    student_count: c.student_count,
    necta_exam: '',
    math_subject: '',
    created_at: '',
  };
}

/** Pure cache reads — no network call. Used when a caller already has its own
 * primary query and only wants the IndexedDB snapshot as a fallback. */
export function useCachedExams() {
  const [exams, setExams] = useState<Exam[]>([]);
  useEffect(() => {
    getCachedExams().then(rows => setExams(rows.map(toExam))).catch(() => {});
  }, []);
  return exams;
}

export function useCachedClassrooms() {
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  useEffect(() => {
    getCachedClassrooms().then(rows => setClassrooms(rows.map(toClassroom))).catch(() => {});
  }, []);
  return classrooms;
}

/** Cached classrooms, used whenever the network list of classrooms is unavailable. */
export function useOfflineClassrooms() {
  const [offline, setOffline] = useState<Classroom[]>([]);

  const query = useQuery<PaginatedResponse<Classroom> | Classroom[]>({
    queryKey: ['classrooms'],
    queryFn: () => studentsApi.classrooms({ page_size: 500 }).then(r => r.data),
    retry: 1,
  });

  useEffect(() => {
    if (!query.isError) return;
    getCachedClassrooms().then(rows => setOffline(rows.map(toClassroom))).catch(() => {});
  }, [query.isError]);

  const online: Classroom[] = Array.isArray(query.data)
    ? query.data
    : (query.data as PaginatedResponse<Classroom>)?.results ?? [];

  return {
    classrooms: query.isError ? offline : online,
    isOfflineFallback: query.isError && offline.length > 0,
    isLoading: query.isLoading,
  };
}

/** Cached exam list, used whenever the network list of exams is unavailable. */
export function useOfflineExams() {
  const [offline, setOffline] = useState<Exam[]>([]);

  const query = useQuery<PaginatedResponse<Exam> | Exam[]>({
    queryKey: ['exams-offline-capable'],
    queryFn: () => examsApi.exams({ page_size: 500 }).then(r => r.data),
    retry: 1,
  });

  useEffect(() => {
    if (!query.isError) return;
    getCachedExams().then(rows => setOffline(rows.map(toExam))).catch(() => {});
  }, [query.isError]);

  const online: Exam[] = Array.isArray(query.data)
    ? query.data
    : (query.data as PaginatedResponse<Exam>)?.results ?? [];

  return {
    exams: query.isError ? offline : online,
    isOfflineFallback: query.isError && offline.length > 0,
    isLoading: query.isLoading,
  };
}

/**
 * Cached roster for a set of classroom IDs — used by Mark Entry so a teacher
 * can still see (and queue scores for) their students while offline.
 * Falls back to the IndexedDB snapshot only once the live request fails.
 */
export function useOfflineStudentsByClassroom(classroomIds: number[] | undefined) {
  const [offline, setOffline] = useState<StudentProfile[]>([]);
  const enabled = !!classroomIds?.length;

  const query = useQuery<StudentProfile[]>({
    queryKey: ['exam-students-offline-capable', classroomIds],
    queryFn: async () => {
      const all: StudentProfile[] = [];
      for (const cid of classroomIds ?? []) {
        const res = await studentsApi.classroomStudents(cid);
        all.push(...(res.data as StudentProfile[]));
      }
      return all;
    },
    enabled,
    retry: 1,
  });

  useEffect(() => {
    if (!query.isError || !classroomIds?.length) return;
    getCachedStudents().then(rows => {
      const idSet = new Set(classroomIds);
      setOffline(
        rows.filter(r => r.classroom != null && idSet.has(r.classroom)).map(toStudentProfile)
      );
    }).catch(() => {});
  }, [query.isError, classroomIds]);

  return {
    students: query.isError ? offline : (query.data ?? []),
    isOfflineFallback: query.isError && offline.length > 0,
    isLoading: query.isLoading,
  };
}
