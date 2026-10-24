from datetime import date

from flask import Blueprint, jsonify, request, url_for
from flask_login import current_user, login_required
from flask_limiter.util import get_remote_address
from sqlalchemy import or_

from app.extensions import limiter
from app.models import Achievement, Notification, Substitution, User, db

api_bp = Blueprint("api", __name__)


def notification_limit_key():
    if current_user.is_authenticated:
        return f"user:{current_user.get_id()}"
    return get_remote_address()


@api_bp.route("/notifications")
@limiter.limit("120 per minute", key_func=notification_limit_key, override_defaults=True)
@login_required
def notifications_json():
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False)
    unread_count = unread.count()
    notifications = unread.order_by(Notification.created_at.desc()).limit(50).all()
    items = []
    for item in notifications:
        target_url = None
        if current_user.role == "mentor" and item.type == "achievement" and item.related_id:
            achievement = Achievement.query.join(User, Achievement.mentee_id == User.id).filter(
                Achievement.id == item.related_id,
                User.role == "mentee",
                User.mentor_id == current_user.id,
                User.is_active.is_(True),
            ).first()
            if achievement:
                target_url = url_for("mentor.mentee_achievements", mentee_id=achievement.mentee_id)
        items.append({
            "id": item.id,
            "type": item.type,
            "message": item.message,
            "is_read": item.is_read,
            "created_at": item.created_at.isoformat(),
            "url": target_url,
        })
    response = jsonify(items)
    response.headers["X-Unread-Count"] = str(unread_count)
    return response


@api_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    if notification:
        notification.is_read = True
        db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/search")
@login_required
def search_people():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])

    if current_user.role == "admin":
        people = User.query.filter(User.role.in_(["mentor", "mentee"]))
        target_url = url_for("admin.users")
    elif current_user.role == "mentor":
        substitute_mentee_ids = db.session.query(Substitution.mentee_id).filter(
            Substitution.substitute_mentor_id == current_user.id,
            Substitution.active.is_(True),
            Substitution.start_date <= date.today(),
            Substitution.end_date >= date.today(),
        )
        people = User.query.filter(
            User.role == "mentee",
            or_(User.mentor_id == current_user.id, User.id.in_(substitute_mentee_ids)),
        )
        target_url = url_for("mentor.mentees")
    elif current_user.role == "mentee":
        mentor_ids = [current_user.mentor_id] if current_user.mentor_id else []
        active_substitution = Substitution.query.filter(
            Substitution.mentee_id == current_user.id,
            Substitution.active.is_(True),
            Substitution.start_date <= date.today(),
            Substitution.end_date >= date.today(),
        ).first()
        if active_substitution:
            mentor_ids.append(active_substitution.substitute_mentor_id)
        people = User.query.filter(User.role == "mentor", User.id.in_(mentor_ids))
        target_url = url_for("mentee.messages")
    else:
        return jsonify([])

    matches = people.filter(
        User.is_active.is_(True),
        User.full_name.ilike(f"%{query}%"),
    ).order_by(User.full_name).limit(8).all()
    return jsonify([
        {"name": person.full_name, "role": person.role, "url": target_url}
        for person in matches
    ])
