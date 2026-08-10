"""
AuditMiddleware — auto-log every successful mutating HTTP request, with a
field-level diff of what actually changed wherever the model behind the
request is resolvable (see MODEL_REGISTRY).

For UPDATE (PUT/PATCH): snapshots the row before the view runs, snapshots
it again after, and stores only the fields that differ.
For CREATE (POST): the created row's id is read back from the response
body, then every concrete field is recorded as a `{old: null, new: value}`
change.
For DELETE: the pre-deletion snapshot is recorded as `{old: value, new: null}`
for every field, since there's nothing left to re-fetch afterwards.

Endpoints whose model isn't in MODEL_REGISTRY (cron triggers, bulk actions,
etc.) still get an audit row — just without a `changes` payload.
"""
import json

from .models import AuditLog

AUDITED_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
SKIP_PATHS = {
    '/api/auth/token/refresh/',
    '/api/auth/login/',
    '/api/auth/logout/',
}

ACTION_MAP = {
    'POST': AuditLog.Action.CREATE,
    'PUT': AuditLog.Action.UPDATE,
    'PATCH': AuditLog.Action.UPDATE,
    'DELETE': AuditLog.Action.DELETE,
}

# Fields never worth showing in a diff — secrets, or noise that changes on
# every single save regardless of what the user actually edited.
EXCLUDED_FIELD_NAMES = {'password', 'last_login', 'updated_at', 'created_at'}

# URL path segment (the DRF router basename) -> (app_label, model_name).
# Deliberately a small, explicit allowlist rather than something clever and
# automatic — an unmapped path just means no `changes` payload, never a
# crash, so it's safe to leave new endpoints out until it's worth adding them.
_MODEL_REGISTRY_SPEC = {
    'grade-levels': ('students', 'GradeLevel'),
    'classrooms': ('students', 'Classroom'),
    'streams': ('students', 'Stream'),
    'profiles': ('students', 'StudentProfile'),
    'parent-links': ('students', 'ParentStudentLink'),
    'topics': ('exams', 'MathTopic'),
    'exams': ('exams', 'Exam'),
    'scores': ('exams', 'ExamScore'),
    'groups': ('groups', 'StudentGroup'),
    'constraints': ('groups', 'PeerConstraint'),
    'subjects': ('accounts', 'Subject'),
    'assignments': ('accounts', 'TeacherAssignment'),
    'users': ('accounts', 'User'),
}


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _path_segments(path: str):
    return [p for p in path.strip('/').split('/') if p]


def _model_name_from_path(path: str) -> str:
    parts = [p for p in _path_segments(path) if not p.isdigit()]
    return parts[-1] if parts else path


def _object_id_from_path(path: str) -> str:
    for part in reversed(_path_segments(path)):
        if part.isdigit():
            return part
    return ''


def _resolve_model(path: str):
    from django.apps import apps
    key = _model_name_from_path(path)
    spec = _MODEL_REGISTRY_SPEC.get(key)
    if not spec:
        return None
    try:
        return apps.get_model(*spec)
    except LookupError:
        return None


def _json_safe(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _snapshot(instance) -> dict:
    """Plain-dict snapshot of an instance's concrete scalar fields, skipping
    secrets and anything that can't be made JSON-safe cheaply."""
    if instance is None:
        return {}
    data = {}
    for field in instance._meta.concrete_fields:
        name = field.name
        if name in EXCLUDED_FIELD_NAMES or name.endswith('password'):
            continue
        try:
            value = field.value_from_object(instance)
        except Exception:
            continue
        if isinstance(value, (bytes, bytearray)):
            continue
        data[name] = _json_safe(value)
    return data


def _diff(before: dict, after: dict):
    changes = {}
    for key in set(before) | set(after):
        old, new = before.get(key), after.get(key)
        if old != new:
            changes[key] = {'old': old, 'new': new}
    return changes or None


def _created_payload(after: dict):
    changes = {k: {'old': None, 'new': v} for k, v in after.items()}
    return changes or None


def _deleted_payload(before: dict):
    changes = {k: {'old': v, 'new': None} for k, v in before.items()}
    return changes or None


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        should_audit = (
            request.method in AUDITED_METHODS
            and request.path not in SKIP_PATHS
        )

        model = None
        object_id = ''
        before_snapshot = None

        if should_audit:
            object_id = _object_id_from_path(request.path)
            model = _resolve_model(request.path)
            # For UPDATE/DELETE we need the "before" state captured before
            # the view mutates or removes the row.
            if model is not None and object_id and request.method in ('PUT', 'PATCH', 'DELETE'):
                try:
                    instance = model.objects.filter(pk=object_id).first()
                    if instance is not None:
                        before_snapshot = _snapshot(instance)
                except Exception:
                    before_snapshot = None

        response = self.get_response(request)

        if (
            should_audit
            and hasattr(request, 'user')
            and request.user.is_authenticated
            and 200 <= response.status_code < 300
        ):
            try:
                changes = None
                final_object_id = object_id
                action = ACTION_MAP.get(request.method, AuditLog.Action.UPDATE)

                if model is not None:
                    if action == AuditLog.Action.DELETE:
                        changes = _deleted_payload(before_snapshot or {})
                    elif action == AuditLog.Action.UPDATE and object_id:
                        instance = model.objects.filter(pk=object_id).first()
                        if instance is not None:
                            changes = _diff(before_snapshot or {}, _snapshot(instance))
                    elif action == AuditLog.Action.CREATE:
                        new_id = None
                        try:
                            body = json.loads(response.content.decode('utf-8'))
                            new_id = body.get('id') if isinstance(body, dict) else None
                        except Exception:
                            new_id = None
                        if new_id is not None:
                            final_object_id = str(new_id)
                            instance = model.objects.filter(pk=new_id).first()
                            if instance is not None:
                                changes = _created_payload(_snapshot(instance))

                AuditLog.objects.create(
                    user=request.user,
                    action=action,
                    model_name=model._meta.model_name if model is not None else _model_name_from_path(request.path),
                    object_id=final_object_id,
                    description=f'{request.method} {request.path}',
                    changes=changes,
                    ip_address=_get_client_ip(request),
                )
            except Exception:
                pass  # Never let audit logging break a request

        return response
