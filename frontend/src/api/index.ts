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
};

// ── Exams ─────────────────────────────────────────────────────────────────
export const examsApi = {
  topics: (params?: object) => api.get('/exams/topics/', { params }),
  exams: (params?: object) => api.get('/exams/exams/', { params }),
  exam: (id: number) => api.get(`/exams/exams/${id}/`),
  pendingReview: () => api.get('/exams/exams/pending-review/'),
  trash: () => api.get('/exams/exams/trash/'),
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
  compare: (params?: object) => api.get('/analytics/compare/', { params }),
  streamComparison: (id: number, params?: object) => api.get(`/analytics/classrooms/${id}/stream-comparison/`, { params }),

  // ── Intelligence layer ──────────────────────────────────────────────────
  integrityFlags: (params?: object) => api.get('/analytics/integrity/', { params }),
  studentRisk: (id: number, params?: object) => api.get(`/analytics/students/${id}/risk/`, { params }),
  classroomRisk: (id: number, params?: object) => api.get(`/analytics/classrooms/${id}/risk/`, { params }),
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
};
