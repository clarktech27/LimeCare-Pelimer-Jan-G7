from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(role):
    """Login required AND the user must have the given role, else 403."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.profile.role != role:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
