"""
AuditMiddleware — auto-log every successful mutating HTTP request.
"""
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


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _model_name_from_path(path: str) -> str:
    parts = [p for p in path.strip('/').split('/') if p and not p.isdigit()]
    return parts[-1] if parts else path


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (
            request.method in AUDITED_METHODS
            and request.path not in SKIP_PATHS
            and hasattr(request, 'user')
            and request.user.is_authenticated
            and 200 <= response.status_code < 300
        ):
            try:
                AuditLog.objects.create(
                    user=request.user,
                    action=ACTION_MAP.get(request.method, AuditLog.Action.UPDATE),
                    model_name=_model_name_from_path(request.path),
                    object_id='',
                    description=f'{request.method} {request.path}',
                    ip_address=_get_client_ip(request),
                )
            except Exception:
                pass  # Never let audit logging break a request

        return response
