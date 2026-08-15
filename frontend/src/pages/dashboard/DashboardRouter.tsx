import { useAuthStore } from '../../store/auth';
import DashboardPage from './DashboardPage';
import StudentHomeDashboard from './StudentHomeDashboard';
import ParentDashboard from './ParentDashboard';

/**
 * The single "/dashboard" route resolves to three very different experiences:
 *  - students get their own personal mission-control view (own trend, own
 *    weak topics, own rank) — /analytics/dashboard/ on the backend already
 *    branches for role=='student' and returns get_student_summary, but the
 *    admin/teacher DashboardPage expects the aggregate-classroom shape, so
 *    a student hitting it previously just saw broken/empty admin widgets.
 *  - parents get the same view for each of their linked children (backend
 *    already scopes parent access via ParentStudentLink + _check_student_access;
 *    previously parents had literally no dashboard at all).
 *  - everyone else keeps the existing admin/teacher DashboardPage untouched.
 *
 * Splitting this out as a router (rather than branching inside
 * DashboardPage itself) keeps the existing 600+ line admin dashboard
 * completely unmodified.
 */
export default function DashboardRouter() {
  const { user } = useAuthStore();

  if (user?.role === 'student') {
    if (!user.student_profile_id) {
      return (
        <div className="card p-6 text-center text-sm text-secondary">
          Your account isn't linked to a student profile yet — ask your teacher or admin to link it.
        </div>
      );
    }
    return <StudentHomeDashboard studentId={user.student_profile_id} />;
  }

  if (user?.role === 'parent') {
    return <ParentDashboard />;
  }

  return <DashboardPage />;
}
