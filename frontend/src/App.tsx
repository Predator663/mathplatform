import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/auth';
import { SyncProvider } from './hooks/usePWASync';
import { useSiteSettings } from './hooks/useSiteSettings';
import AppLayout from './components/layout/AppLayout';
import OfflineIndicator from './components/offline/OfflineIndicator';

// Pages
import LoginPage from './pages/auth/LoginPage';
import DashboardPage from './pages/dashboard/DashboardPage';
import StudentsPage from './pages/students/StudentsPage';
import StudentDetailPage from './pages/students/StudentDetailPage';
import CreateStudentPage from './pages/students/CreateStudentPage';
import ClassroomsPage from './pages/classrooms/ClassroomsPage';
import CreateClassroomPage from './pages/classrooms/CreateClassroomPage';
import ExamsPage from './pages/exams/ExamsPage';
import ExamDetailPage from './pages/exams/ExamDetailPage';
import CreateExamPage from './pages/exams/CreateExamPage';
import EditExamPage from './pages/exams/EditExamPage';
import MarkEntryPage from './pages/marks/MarkEntryPage';
import BulkImportPage from './pages/marks/BulkImportPage';
import AnalyticsPage from './pages/analytics/AnalyticsPage';
import StudentAnalyticsPage from './pages/analytics/StudentAnalyticsPage';
import ClassAnalyticsPage from './pages/analytics/ClassAnalyticsPage';
import CompareAnalyticsPage from './pages/analytics/CompareAnalyticsPage';
import AtRiskPage from './pages/analytics/AtRiskPage';
import ReportsPage from './pages/reports/ReportsPage';
import UsersPage from './pages/users/UsersPage';
import SettingsPage from './pages/settings/SettingsPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  // Bootstrap site settings globally on first load (public endpoint, no auth needed)
  useSiteSettings();

  return (
    <BrowserRouter>
      {/* SyncProvider wraps the whole app so any page can call useSync() */}
      <SyncProvider>
        <OfflineIndicator />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard"          element={<DashboardPage />} />
            <Route path="students"           element={<StudentsPage />} />
            <Route path="students/new"       element={<CreateStudentPage />} />
            <Route path="students/:id"       element={<StudentDetailPage />} />
            <Route path="classrooms"         element={<ClassroomsPage />} />
            <Route path="classrooms/new"     element={<CreateClassroomPage />} />
            <Route path="exams"              element={<ExamsPage />} />
            <Route path="exams/new"          element={<CreateExamPage />} />
            <Route path="exams/:id"          element={<ExamDetailPage />} />
            <Route path="exams/:id/edit"     element={<EditExamPage />} />
            <Route path="exams/:id/marks"    element={<MarkEntryPage />} />
            <Route path="import"             element={<BulkImportPage />} />
            <Route path="analytics"          element={<AnalyticsPage />} />
            <Route path="analytics/student/:id" element={<StudentAnalyticsPage />} />
            <Route path="analytics/class"    element={<ClassAnalyticsPage />} />
            <Route path="analytics/compare" element={<CompareAnalyticsPage />} />
            <Route path="at-risk"            element={<AtRiskPage />} />
            <Route path="reports"            element={<ReportsPage />} />
            <Route path="users"              element={<UsersPage />} />
            <Route path="settings"           element={<SettingsPage />} />
            <Route path="*"                  element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </SyncProvider>
    </BrowserRouter>
  );
}
