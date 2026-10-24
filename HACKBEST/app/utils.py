import secrets
import string
from datetime import date, datetime

from app.models import Notification, Substitution, User, db


def generate_strong_password(length=14):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-+=?"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def add_notification(user_id, type_name, message, related_id=None):
    notification = Notification(user_id=user_id, type=type_name, message=message, related_id=related_id)
    db.session.add(notification)
    db.session.commit()
    return notification


def active_substitute_for_mentee(mentee_id):
    today = date.today()
    substitution = (
        Substitution.query.filter_by(mentee_id=mentee_id, active=True)
        .filter(Substitution.start_date <= today, Substitution.end_date >= today)
        .order_by(Substitution.start_date.desc())
        .first()
    )
    return substitution


def user_is_mentor_for_mentee(user, mentee_id):
    if user.role == "admin":
        return True
    mentee = User.query.get(mentee_id)
    if not mentee:
        return False
    if mentee.mentor_id == user.id:
        return True
    active = active_substitute_for_mentee(mentee_id)
    if active and active.substitute_mentor_id == user.id:
        return True
    return False


def get_overdue_assignments():
    today = date.today()
    return [assignment for assignment in []]


def sanitize_text(value, max_length=500):
    if value is None:
        return ""
    cleaned = value.replace("<", "&lt;").replace(">", "&gt;")
    cleaned = cleaned[:max_length]
    return cleaned


def append_concern_response(concern, response, author, role):
    entry = (
        f"{datetime.utcnow():%Y-%m-%d %H:%M} - {author} ({role.title()}): "
        f"{sanitize_text(response.strip(), 2000)}"
    )
    concern.comments = "\n".join(part for part in (concern.comments, entry) if part)[-10000:]
