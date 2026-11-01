from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from .errors import ApiError
from .extensions import db
from .models import User


def current_user() -> User:
    return g.user


def roles_required(*roles):
    """Login zaroori. Agar roles diye hain to sirf wahi roles allowed."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = db.session.get(User, int(get_jwt_identity()))
            if not user or not user.is_active:
                raise ApiError("User not found or disabled", 401)
            if roles and user.role not in roles:
                raise ApiError("You do not have permission for this action", 403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


login_required = roles_required()
