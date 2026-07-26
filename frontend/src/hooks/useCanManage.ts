import { useAuthStore } from '../store/auth';
import { useSiteSettingsStore } from '../store/siteSettings';
import type { TeacherResource, TeacherAction } from '../store/siteSettings';

/**
 * Whether the current user may perform `action` on `resource`
 * (students / exams / classrooms / subjects — add / edit / delete).
 *
 * - super_admin: always true.
 * - teacher: follows the admin-configured toggle in Settings → Site →
 *   Teacher Permissions (defaults match the platform's original
 *   behaviour, see DEFAULT_TEACHER_PERMISSIONS).
 * - student / parent: always false — these pages aren't reachable by
 *   them anyway, but the hook stays honest either way.
 *
 * This mirrors the backend's TeacherFeatureEnabled permission class, so
 * a hidden/disabled button here matches what the API would actually
 * allow — it isn't a source of truth by itself, just keeps the UI from
 * offering actions that would 403.
 */
export function useCanManage(resource: TeacherResource, action: TeacherAction): boolean {
  const role = useAuthStore((s) => s.user?.role);
  const canTeacher = useSiteSettingsStore((s) => s.canTeacher);

  if (role === 'super_admin') return true;
  if (role === 'teacher') return canTeacher(resource, action);
  return false;
}
