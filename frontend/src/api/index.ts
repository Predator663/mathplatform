import axios from 'axios';
import { useAuthStore } from '../store/auth';

const BASE_URL = (import.meta.env.VITE_API_URL ?? '') + '/api';

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach access token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401 — use React Router navigate instead of window.location
// to avoid full page reload (which restarts the sync loop)
let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;

      // If already refreshing, queue this request
      if (isRefreshing) {
        return new Promise((resolve) => {
          refreshQueue.push((token: string) => {
            original.headers.Authorization = `Bearer ${token}`;
            resolve(api(original));
          });
        });
      }

      isRefreshing = true;

      try {
        const refresh = localStorage.getItem('refresh_token');
        if (!refresh) throw new Error('No refresh token');

        const { data } = await axios.post(`${BASE_URL}/auth/token/refresh/`, { refresh });
        const newToken = data.access;
        localStorage.setItem('access_token', newToken);

        // Flush queued requests
        refreshQueue.forEach(cb => cb(newToken));
        refreshQueue = [];

        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch {
        // Refresh failed — clear auth via store (no page reload)
        refreshQueue = [];
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');

        // Use store directly to trigger React state change → router redirects
        // This avoids window.location.href which causes a full reload + sync loop
        try {
          const { clearAuth } = useAuthStore.getState();
          clearAuth();
        } catch { /**/ }

        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;

// ── Auth ──────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) => api.post('/auth/login/', { email, password }),
  logout: (refresh: string) => api.post('/auth/logout/', { refresh }),
  me: () => api.get('/auth/me/'),
  updateMe: (data: object) => api.patch('/auth/me/', data),
  register: (data: object) => api.post('/auth/register/', data),
  changePassword: (data: object) => api.post('/auth/change-password/', data),
  users: (params?: object) => api.get('/auth/users/', { params }),
  updateUser: (id: number, data: object) => api.patch(`/auth/users/${id}/`, data),
  deleteUser: (id: number) => api.delete(`/auth/users/${id}/`),
  assignableTeachers: () => api.get('/auth/users/assignable-teachers/'),
};

// ── Students ──────────────────────────────────────────────────────────────
export const studentsApi = {
  gradeLevels: () => api.get('/students/grade-levels/'),
  createGradeLevel: (data: object) => api.post('/students/grade-levels/', data),
  updateGradeLevel: (id: number, data: object) => api.patch(`/students/grade-levels/${id}/`, data),
  deleteGradeLevel: (id: number) => api.delete(`/students/grade-levels/${id}/`),
  classrooms: (params?: object) => api.get('/students/classrooms/', { params }),
  classroom: (id: number) => api.get(`/students/classrooms/${id}/`),
  classroomStudents: (id: number) => api.get(`/students/classrooms/${id}/students/`),
  createClassroom: (data: object) => api.post('/students/classrooms/', data),
  updateClassroom: (id: number, data: object) => api.patch(`/students/classrooms/${id}/`, data),
  deleteClassroom: (id: number) => api.delete(`/students/classrooms/${id}/`),
  streams: (params?: object) => api.get('/students/streams/', { params }),
  createStream: (data: object) => api.post('/students/streams/', data),
  updateStream: (id: number, data: object) => api.patch(`/students/streams/${id}/`, data),
  deleteStream: (id: number) => api.delete(`/students/streams/${id}/`),
  bulkAssignStream: (data: { student_ids: number[]; stream_id: number | null }) =>
    api.post('/students/streams/bulk_assign/', data),
  students: (params?: object) => api.get('/students/profiles/', { params }),
  student: (id: number) => api.get(`/students/profiles/${id}/`),
  createStudent: (data: object) => api.post('/students/profiles/', data),
  updateStudent: (id: number, data: object) => api.patch(`/students/profiles/${id}/`, data),
  deleteStudent: (id: number) => api.delete(`/students/profiles/${id}/`),
  bulkDeleteStudents: (student_ids: number[]) => api.post('/students/profiles/bulk_delete/', { student_ids }),
  duplicateStudents: (params?: object) => api.get('/students/profiles/duplicates/', { params }),
  studentPerformance: (id: number) => api.get(`/students/profiles/${id}/performance_summary/`),
  // Parent-role: the children linked to *me*, scoped server-side (see
  // ParentStudentLinkViewSet.get_queryset) — a parent only ever sees their
  // own links, never the full table.
  myLinkedChildren: () => api.get('/students/parent-links/'),
  // Student-role only: set MY OWN target_percentage. Deliberately separate
  // from updateStudent() above, which is teacher/admin-only server-side —
  // see StudentProfileViewSet.set_my_target for why.
  setMyTarget: (target_percentage: number | null) =>
    api.patch('/students/profiles/me/target/', { target_percentage }),
};

// ── Exams ─────────────────────────────────────────────────────────────────
export const examsApi = {
  topics: (params?: object) => api.get('/exams/topics/', { params }),
  topic: (id: number) => api.get(`/exams/topics/${id}/`),
  createTopic: (data: object) => api.post('/exams/topics/', data),
  updateTopic: (id: number, data: object) => api.patch(`/exams/topics/${id}/`, data),
  deleteTopic: (id: number) => api.delete(`/exams/topics/${id}/`),
  restoreTopic: (id: number) => api.post(`/exams/topics/${id}/restore/`),
  reorderTopics: (order: { id: number; order: number }[]) => api.post('/exams/topics/reorder/', { order }),
  exams: (params?: object) => api.get('/exams/exams/', { params }),
  exam: (id: number) => api.get(`/exams/exams/${id}/`),
  academicYears: () => api.get('/exams/exams/academic-years/'),
  exportCsv: (params?: object) =>
    api.get('/exams/exams/export-csv/', { params, responseType: 'blob' }),
  pendingReview: (params?: object) => api.get('/exams/exams/pending-review/', { params }),
  trash: (params?: object) => api.get('/exams/exams/trash/', { params }),
  restoreExam: (id: number) => api.post(`/exams/exams/${id}/restore/`),
  emptyTrash: () => api.post('/exams/exams/trash/empty/', { confirm: true }),
  createExam: (data: object) => api.post('/exams/exams/', data),
  updateExam: (id: number, data: object) => api.patch(`/exams/exams/${id}/`, data),
  deleteExam: (id: number) => api.delete(`/exams/exams/${id}/`),
  publishExam: (id: number) => api.post(`/exams/exams/${id}/publish/`),
  unpublishExam: (id: number) => api.post(`/exams/exams/${id}/unpublish/`),
  examScores: (examId: number) => api.get(`/exams/exams/${examId}/scores/`),
  examStats: (examId: number) => api.get(`/exams/exams/${examId}/statistics/`),
  bulkScores: (examId: number, data: object) => api.post(`/exams/exams/${examId}/bulk_scores/`, data),
  updateScore: (scoreId: number, data: object) => api.patch(`/exams/scores/${scoreId}/`, data),
  scoreHistory: (scoreId: number) => api.get(`/exams/scores/${scoreId}/history/`),
  scoresTemplate: (examId: number) =>
    api.get(`/exams/exams/${examId}/scores_template/`, { responseType: 'blob' }),
};

// ── Analytics ─────────────────────────────────────────────────────────────
export const notificationsApi = {
  preferences: () => api.get('/notifications/preferences/'),
  updatePreferences: (updates: { category: string; frequency: string }[]) =>
    api.patch('/notifications/preferences/', updates),
  history: (params?: object) => api.get('/notifications/history/', { params }),
  unreadCount: () => api.get('/notifications/unread-count/'),
  markRead: (id?: number) => api.post('/notifications/mark-read/', id ? { id } : {}),
  testEmail: () => api.post('/notifications/test-email/'),
  sendAnalyticsReport: (data: { recipients: string[]; report_type: string; classroom_id?: number; student_id?: number }) =>
    api.post('/notifications/send-analytics-report/', data),
  sendWhatsappResult: (data: { student_id: number; exam_id: number }) =>
    api.post('/notifications/send-whatsapp-result/', data),
  ping: () => api.get('/notifications/ping/'),
  systemStatus: () => api.get('/notifications/system-status/'),
  failures: () => api.get('/notifications/failures/'),
};

export const analyticsApi = {
  dashboard: (params?: object) => api.get('/analytics/dashboard/', { params }),
  classAnalytics: (id: number, params?: object) => api.get(`/analytics/classrooms/${id}/`, { params }),
  heatmap: (id: number, params?: object) => api.get(`/analytics/classrooms/${id}/heatmap/`, { params }),
  studentSummary: (id: number, params?: object) => api.get(`/analytics/students/${id}/summary/`, { params }),
  studentTrend: (id: number, params?: object) => api.get(`/analytics/students/${id}/trend/`, { params }),
  studentTopics: (id: number, params?: object) => api.get(`/analytics/students/${id}/topics/`, { params }),
  studentClassroomComparison: (id: number, params?: object) => api.get(`/analytics/students/${id}/classroom-comparison/`, { params }),
  atRisk: (params?: object) => api.get('/analytics/at-risk/', { params }),
  mostImproved: (params?: object) => api.get('/analytics/most-improved/', { params }),
  compare: (params?: object) => api.get('/analytics/compare/', { params }),
  streamComparison: (id: number, params?: object) => api.get(`/analytics/classrooms/${id}/stream-comparison/`, { params }),
  compareStudents: (params?: object) => api.get('/analytics/students/compare/', { params }),
  compareStudentsPdf: (params?: object) =>
    api.get('/analytics/students/compare/pdf/', { params, responseType: 'blob' }),
  topicIntelligenceOverview: (params?: object) => api.get('/analytics/topics/overview/', { params }),
  topicDistribution: (topicId: number, params?: object) =>
    api.get(`/analytics/topics/${topicId}/distribution/`, { params }),

  // ── Intelligence layer ──────────────────────────────────────────────────
  integrityFlags: (params?: object) => api.get('/analytics/integrity/', { params }),
  studentRisk: (id: number, params?: object) => api.get(`/analytics/students/${id}/risk/`, { params }),
  classroomRisk: (id: number, params?: object) => api.get(`/analytics/classrooms/${id}/risk/`, { params }),
  classroomTrends: (id: number, params?: object) => api.get(`/analytics/classrooms/${id}/trends/`, { params }),
  topicDependencies: (id: number, params?: object) => api.get(`/analytics/classrooms/${id}/topic-dependencies/`, { params }),
  teacherConsistency: (params?: object) => api.get('/analytics/teacher-consistency/', { params }),
  gradeBoundaryWhatIf: (id: number, params?: object) => api.get(`/analytics/students/${id}/boundary-whatif/`, { params }),
};

// ── Reports ───────────────────────────────────────────────────────────────
export const reportsApi = {
  studentReport: (id: number) => api.get(`/reports/student/${id}/`),
  classReport: (id: number, params?: object) => api.get(`/reports/classroom/${id}/`, { params }),
  exportExamCsv: (examId: number) =>
    api.get(`/reports/export/exam/${examId}/csv/`, { responseType: 'blob' }),
  exportClassCsv: (classId: number) =>
    api.get(`/reports/export/classroom/${classId}/csv/`, { responseType: 'blob' }),
  exportAtRiskPdf: (params?: object) =>
    api.get('/reports/export/at-risk/pdf/', { params, responseType: 'blob' }),
};

// ── Peer Groups ───────────────────────────────────────────────────────────
export const groupsApi = {
  overview: (classroomId: number, params?: object) =>
    api.get(`/groups/classroom/${classroomId}/overview/`, { params }),
  transfers: (classroomId: number) => api.get(`/groups/classroom/${classroomId}/transfers/`),
  effectiveness: (classroomId: number, params?: object) =>
    api.get(`/groups/classroom/${classroomId}/effectiveness/`, { params }),
  rebalanceSuggestions: (classroomId: number, params?: object) =>
    api.get(`/groups/classroom/${classroomId}/rebalance-suggestions/`, { params }),
  seatingChart: (classroomId: number, params?: object) =>
    api.get(`/groups/classroom/${classroomId}/seating-chart/`, { params }),
  constraints: (classroomId: number) => api.get('/groups/constraints/', { params: { classroom: classroomId } }),
  createConstraint: (data: object) => api.post('/groups/constraints/', data),
  deleteConstraint: (id: number) => api.delete(`/groups/constraints/${id}/`),
  list: (params?: object) => api.get('/groups/groups/', { params }),
  create: (data: object) => api.post('/groups/groups/', data),
  update: (id: number, data: object) => api.patch(`/groups/groups/${id}/`, data),
  delete: (id: number) => api.delete(`/groups/groups/${id}/`),
  uploadBadge: (id: number, file: File) => {
    const fd = new FormData();
    fd.append('badge_image', file);
    return api.post(`/groups/groups/${id}/upload-badge/`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  addMember: (groupId: number, studentId: number, reason?: string) =>
    api.post(`/groups/groups/${groupId}/add-member/`, { student_id: studentId, reason }),
  removeMember: (groupId: number, studentId: number, reason?: string) =>
    api.post(`/groups/groups/${groupId}/remove-member/`, { student_id: studentId, reason }),
  transferMember: (studentId: number, toGroupId: number, reason?: string) =>
    api.post('/groups/groups/transfer-member/', { student_id: studentId, to_group_id: toGroupId, reason }),
  autoGenerate: (data: object) => api.post('/groups/groups/auto-generate/', data),
  exportSummary: (classroomId: number, format: 'pdf' | 'excel', params?: object) =>
    api.get(`/groups/export/classroom/${classroomId}/summary/${format}/`, { params, responseType: 'blob' }),
  exportRoster: (classroomId: number, format: 'pdf' | 'excel', params?: object) =>
    api.get(`/groups/export/classroom/${classroomId}/roster/${format}/`, { params, responseType: 'blob' }),
};

// ── Group Assignments (marks + analytics) ────────────────────────────────
export const groupAssignmentsApi = {
  list: (params?: object) => api.get('/groups/assignments/', { params }),
  get: (id: number) => api.get(`/groups/assignments/${id}/`),
  create: (data: object) => api.post('/groups/assignments/', data),
  update: (id: number, data: object) => api.patch(`/groups/assignments/${id}/`, data),
  delete: (id: number) => api.delete(`/groups/assignments/${id}/`),
  roster: (id: number) => api.get(`/groups/assignments/${id}/roster/`),
  recordScores: (id: number, entries: object[]) =>
    api.post(`/groups/assignments/${id}/record-scores/`, { entries }),
  analytics: (classroomId: number, params?: object) =>
    api.get(`/groups/assignments/classroom/${classroomId}/analytics/`, { params }),
  reassignmentSuggestions: (classroomId: number, params?: object) =>
    api.get(`/groups/assignments/classroom/${classroomId}/reassignment-suggestions/`, { params }),
  exportAnalytics: (classroomId: number, format: 'pdf' | 'excel', params?: object) =>
    api.get(`/groups/export/classroom/${classroomId}/assignments/analytics/${format}/`, { params, responseType: 'blob' }),
  exportMarksCsv: (classroomId: number, params?: object) =>
    api.get(`/groups/export/classroom/${classroomId}/assignments/marks/csv/`, { params, responseType: 'blob' }),
};

export const gamificationApi = {
  badges: () => api.get('/gamification/badges/'),
  myProgress: () => api.get('/gamification/my-progress/'),
  studentProgress: (studentId: number) => api.get(`/gamification/students/${studentId}/progress/`),
};

export const quizzesApi = {
  quizzes: (params?: object) => api.get('/quizzes/quizzes/', { params }),
  quiz: (id: number) => api.get(`/quizzes/quizzes/${id}/`),
  createQuiz: (data: object) => api.post('/quizzes/quizzes/', data),
  updateQuiz: (id: number, data: object) => api.patch(`/quizzes/quizzes/${id}/`, data),
  deleteQuiz: (id: number) => api.delete(`/quizzes/quizzes/${id}/`),
  bulkScores: (quizId: number, scores: object[]) =>
    api.post(`/quizzes/quizzes/${quizId}/bulk_scores/`, { scores }),
  scores: (params?: object) => api.get('/quizzes/scores/', { params }),
  academicYears: () => api.get('/quizzes/quizzes/academic-years/'),
  exportCsv: (params?: object) =>
    api.get('/quizzes/quizzes/export-csv/', { params, responseType: 'blob' }),
  classroomAnalytics: (classroomId: number, params?: object) =>
    api.get(`/quizzes/classroom/${classroomId}/analytics/`, { params }),
  myProgress: (params?: object) => api.get('/quizzes/my-progress/', { params }),
  studentProgress: (studentId: number, params?: object) =>
    api.get(`/quizzes/students/${studentId}/progress/`, { params }),
  progressReportPdf: (studentId: number, params?: object) =>
    api.get(`/quizzes/students/${studentId}/progress-report.pdf/`, { params, responseType: 'blob' }),
};

export const tournamentsApi = {
  list: (params?: object) => api.get('/tournaments/tournaments/', { params }),
  get: (id: number) => api.get(`/tournaments/tournaments/${id}/`),
  create: (data: object) => api.post('/tournaments/tournaments/', data),
  update: (id: number, data: object) => api.patch(`/tournaments/tournaments/${id}/`, data),
  delete: (id: number) => api.delete(`/tournaments/tournaments/${id}/`),
  openRegistration: (id: number) => api.post(`/tournaments/tournaments/${id}/open-registration/`),
  closeRegistration: (id: number) => api.post(`/tournaments/tournaments/${id}/close-registration/`),
  cancel: (id: number) => api.post(`/tournaments/tournaments/${id}/cancel/`),
  finalize: (id: number) => api.post(`/tournaments/tournaments/${id}/finalize/`),
  register: (id: number, data: { student_id?: number; stream_id?: number }) =>
    api.post(`/tournaments/tournaments/${id}/register/`, data),
  withdraw: (id: number, entry_id: number) =>
    api.post(`/tournaments/tournaments/${id}/withdraw/`, { entry_id }),
  challenges: (id: number) => api.get(`/tournaments/tournaments/${id}/challenges/`),
  createChallenge: (id: number, data: { label?: string; entry_ids: number[] }) =>
    api.post(`/tournaments/tournaments/${id}/challenges/`, data),
  dossier: (id: number) => api.get(`/tournaments/tournaments/${id}/dossier/`),
  analytics: (id: number) => api.get(`/tournaments/tournaments/${id}/analytics/`),
  headToHead: (studentA: number, studentB: number) =>
    api.get('/tournaments/head-to-head/', { params: { student_a: studentA, student_b: studentB } }),
  myEntries: () => api.get('/tournaments/my-entries/'),
  intel: (params?: object) => api.get('/tournaments/intel/', { params }),
  exportPdf: (id: number) => api.get(`/reports/export/tournament/${id}/pdf/`, { responseType: 'blob' }),
  exportExcel: (id: number) => api.get(`/reports/export/tournament/${id}/excel/`, { responseType: 'blob' }),
};

export const leaguesApi = {
  seasons: (params?: object) => api.get('/leagues/seasons/', { params }),
  season: (id: number) => api.get(`/leagues/seasons/${id}/`),
  createSeason: (data: object) => api.post('/leagues/seasons/', data),
  updateSeason: (id: number, data: object) => api.patch(`/leagues/seasons/${id}/`, data),
  archiveSeason: (id: number) => api.post(`/leagues/seasons/${id}/archive/`),
  reactivateSeason: (id: number) => api.post(`/leagues/seasons/${id}/reactivate/`),
  evaluatePromotions: (id: number, triggerExamId: number) =>
    api.post(`/leagues/seasons/${id}/evaluate-promotions/`, { trigger_exam_id: triggerExamId }),
  seasonAnalytics: (id: number) => api.get(`/leagues/seasons/${id}/analytics/`),
  placeStudent: (id: number, data: { student_id: number; group_id: number; score?: number }) =>
    api.post(`/leagues/seasons/${id}/place-student/`, data),
  groups: (params?: object) => api.get('/leagues/groups/', { params }),
  createGroup: (data: object) => api.post('/leagues/groups/', data),
  updateGroup: (id: number, data: object) => api.patch(`/leagues/groups/${id}/`, data),
  deleteGroup: (id: number) => api.delete(`/leagues/groups/${id}/`),
  promotions: (params?: object) => api.get('/leagues/promotions/', { params }),
  approvePromotion: (id: number) => api.post(`/leagues/promotions/${id}/approve/`),
  rejectPromotion: (id: number) => api.post(`/leagues/promotions/${id}/reject/`),
  hallOfFame: (params?: object) => api.get('/leagues/hall-of-fame/', { params }),
  studentSummary: (studentId: number) => api.get(`/leagues/student-summary/${studentId}/`),
  exportHallOfFamePdf: (params?: object) =>
    api.get('/reports/export/hall-of-fame/pdf/', { params, responseType: 'blob' }),
  exportHallOfFameExcel: (params?: object) =>
    api.get('/reports/export/hall-of-fame/excel/', { params, responseType: 'blob' }),
};

export const interventionsApi = {
  programs: (params?: object) => api.get('/interventions/programs/', { params }),
  program: (id: number) => api.get(`/interventions/programs/${id}/`),
  create: (data: object) => api.post('/interventions/programs/', data),
  discontinue: (id: number, notes?: string) =>
    api.post(`/interventions/programs/${id}/discontinue/`, { notes }),
  progress: (id: number) => api.get(`/interventions/programs/${id}/progress/`),
  startStage: (id: number) => api.post(`/interventions/stages/${id}/start/`),
  completeStage: (id: number, notes?: string) =>
    api.post(`/interventions/stages/${id}/complete/`, { notes }),
  candidates: (classroomId: number) => api.get('/interventions/candidates/', { params: { classroom: classroomId } }),
  analytics: (params?: object) => api.get('/interventions/analytics/', { params }),
  defaultTemplate: () => api.get('/interventions/default-template/'),
};

export const settingsApi = {
  get: () => api.get('/auth/settings/'),
  patch: (data: object) => api.patch('/auth/settings/', data),
};

export const subjectsApi = {
  list: (params?: object) => api.get('/auth/subjects/', { params }),
  get: (id: number) => api.get(`/auth/subjects/${id}/`),
  create: (data: object) => api.post('/auth/subjects/', data),
  update: (id: number, data: object) => api.patch(`/auth/subjects/${id}/`, data),
  delete: (id: number) => api.delete(`/auth/subjects/${id}/`),
};

export const assignmentsApi = {
  list: (params?: object) => api.get('/auth/assignments/', { params }),
  create: (data: object) => api.post('/auth/assignments/', data),
  delete: (id: number) => api.delete(`/auth/assignments/${id}/`),
};

export const auditApi = {
  list: (params?: object) => api.get('/auth/audit-log/', { params }),
  facets: () => api.get('/auth/audit-log/facets/'),
  stats: (params?: object) => api.get('/auth/audit-log/stats/', { params }),
  downloadCard: (id: number) =>
    api.get(`/auth/audit-log/${id}/card/pdf/`, { responseType: 'blob' }),
  downloadCardsBatch: (params?: object) =>
    api.get('/auth/audit-log/export/cards/pdf/', { params, responseType: 'blob' }),
  exportCsv: (params?: object) =>
    api.get('/auth/audit-log/export/csv/', { params, responseType: 'blob' }),
};
