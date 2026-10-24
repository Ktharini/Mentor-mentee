from functools import wraps

from flask import abort, redirect, request, url_for
from flask_login import current_user

from app.models import User
from app.utils import active_substitute_for_mentee


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator


def can_access_mentee(user, mentee_id):
    if not user or not user.is_authenticated:
        return False
    if user.role == "admin":
        return True
    if user.role == "mentor":
        mentee = User.query.get(mentee_id)
        if not mentee:
            return False
        if mentee.mentor_id == user.id:
            return True
        active_sub = active_substitute_for_mentee(mentee_id)
        if active_sub and active_sub.substitute_mentor_id == user.id:
            return True
        return False
    if user.role == "mentee":
        return user.id == mentee_id
    return False
