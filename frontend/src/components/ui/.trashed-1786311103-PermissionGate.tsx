import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ShieldOff } from 'lucide-react';
import { useCanManage } from '../../hooks/useCanManage';
import type { TeacherResource, TeacherAction } from '../../store/siteSettings';
import { EmptyState, Button } from './index';

/**
 * Wraps a create/edit page. If the current user isn't allowed to perform
 * `action` on `resource` (see useCanManage — admin toggle in Settings, or
 * role), shows an explanatory empty state with a way back instead of a
 * form that would just 403 on submit.
 *
 * This is a UX guard only, not a security boundary — the API enforces the
 * real check independently (TeacherFeatureEnabled on the backend).
 */
export function PermissionGate({
  resource, action, backTo, backLabel = 'Go back', children,
}: {
  resource: TeacherResource;
  action: TeacherAction;
  backTo: string;
  backLabel?: string;
  children: ReactNode;
}) {
  const allowed = useCanManage(resource, action);
  if (allowed) return <>{children}</>;

  return (
    <div className="flex flex-col gap-6 max-w-2xl page-enter">
      <div className="card">
        <EmptyState
          icon={<ShieldOff size={32} />}
          title="This feature is disabled"
          message="An administrator has turned this off for teacher accounts. Contact your school admin if you believe this is a mistake."
        />
      </div>
      <div className="flex justify-center">
        <Link to={backTo}>
          <Button variant="secondary">{backLabel}</Button>
        </Link>
      </div>
    </div>
  );
}
