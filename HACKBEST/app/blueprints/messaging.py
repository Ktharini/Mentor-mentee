from datetime import date, datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.forms import MessageForm
from app.models import (
    GroupChat,
    GroupChatMember,
    GroupMessage,
    Message,
    MessageDelivery,
    Notification,
    Substitution,
    User,
    db,
)
from app.utils import add_notification, sanitize_text

messaging_bp = Blueprint("messaging", __name__)


@messaging_bp.route("/", methods=["GET", "POST"])
@login_required
def inbox():
    form = MessageForm()
    users = _allowed_recipients()
    group_chats = []
    if current_user.role == "mentor":
        group_chats = [_sync_mentor_group(current_user)]
    elif current_user.role == "mentee":
        mentor = db.session.get(User, current_user.mentor_id) if current_user.mentor_id else None
        if mentor and mentor.role == "mentor" and mentor.is_active:
            _sync_mentor_group(mentor)
        group_chats = _member_group_chats(current_user)

    if form.validate_on_submit():
        raw_recipient_id = request.form.get("recipient_id", "").strip()
        try:
            recipient_id = int(raw_recipient_id)
        except (TypeError, ValueError):
            flash("Recipient is required.", "danger")
            return redirect(url_for("messaging.inbox"))
        recipient = next((user for user in users if user.id == recipient_id), None)
        if not recipient:
            flash("This recipient is not available for your account.", "danger")
            return redirect(url_for("messaging.inbox"))
        content = sanitize_text(form.content.data, 500)
        emergency = bool(form.emergency.data)
        message = Message(sender_id=current_user.id, recipient_id=recipient.id, content=content, emergency=emergency)
        db.session.add(message)
        db.session.commit()
        add_notification(recipient.id, "message", f"New message from {current_user.full_name}", message.id)
        if emergency:
            add_notification(recipient.id, "emergency_message", f"Emergency message from {current_user.full_name}", message.id)
        flash("Message sent.", "success")
        return redirect(url_for("messaging.inbox", recipient_id=recipient.id))
    selected_kind = request.args.get("kind", "group" if current_user.role == "mentor" and group_chats else "direct")
    selected_id = request.args.get("recipient_id", type=int)
    selected_group_id = request.args.get("group_id", type=int)
    if selected_id not in {user.id for user in users}:
        selected_id = users[0].id if users else None
    allowed_group_ids = {group.id for group in group_chats}
    if selected_group_id not in allowed_group_ids:
        selected_group_id = group_chats[0].id if group_chats and selected_kind == "group" else None
    if selected_kind == "group" and selected_group_id is None:
        selected_kind = "direct"
    if selected_kind == "direct" and selected_id is None and group_chats:
        selected_kind = "group"
        selected_group_id = group_chats[0].id
    return render_template(
        "shared/messages.html",
        form=form,
        users=users,
        group_chats=group_chats,
        selected_kind=selected_kind,
        selected_recipient_id=selected_id,
        selected_group_id=selected_group_id,
    )


def _sync_mentor_group(mentor):
    group = GroupChat.query.filter_by(mentor_id=mentor.id).first()
    if group is None:
        group = GroupChat(mentor_id=mentor.id, name=f"{mentor.full_name}'s Mentee Group")
        db.session.add(group)
        db.session.flush()

    mentee_ids = {
        user_id
        for (user_id,) in db.session.query(User.id).filter(
            User.mentor_id == mentor.id,
            User.role == "mentee",
            User.is_active.is_(True),
        ).all()
    }
    member_ids = mentee_ids | {mentor.id}
    existing_members = GroupChatMember.query.filter_by(group_id=group.id).all()
    existing_ids = {member.user_id for member in existing_members}
    for member in existing_members:
        if member.user_id not in member_ids:
            db.session.delete(member)
    db.session.add_all(
        GroupChatMember(group_id=group.id, user_id=user_id)
        for user_id in member_ids - existing_ids
    )
    db.session.commit()
    return group


def _member_group_chats(user):
    return (
        GroupChat.query.join(GroupChatMember)
        .filter(GroupChatMember.user_id == user.id, GroupChat.mentor_id == user.mentor_id)
        .order_by(GroupChat.name)
        .all()
        if user.mentor_id
        else []
    )


def _allowed_group(group_id):
    group = db.session.get(GroupChat, group_id)
    if not group:
        return None
    if current_user.role == "mentor" and current_user.is_active:
        return group if group.mentor_id == current_user.id else None
    if (
        current_user.role == "mentee"
        and current_user.is_active
        and current_user.mentor_id == group.mentor_id
    ):
        member = GroupChatMember.query.filter_by(group_id=group.id, user_id=current_user.id).first()
        return group if member else None
    return None


@messaging_bp.route("/api/group/<int:group_id>")
@login_required
def group_messages(group_id):
    group = _allowed_group(group_id)
    if group is None:
        return jsonify({"error": "This group conversation is not available."}), 404
    messages = (
        GroupMessage.query.filter_by(group_id=group.id)
        .order_by(GroupMessage.created_at.desc(), GroupMessage.id.desc())
        .limit(100)
        .all()
    )
    messages.reverse()
    members = (
        User.query.join(GroupChatMember, GroupChatMember.user_id == User.id)
        .filter(GroupChatMember.group_id == group.id)
        .order_by(User.full_name)
        .all()
    )
    return jsonify({
        "group": {
            "id": group.id,
            "name": group.name,
            "members": [member.full_name for member in members],
        },
        "messages": [
            {
                "id": message.id,
                "sender_id": message.sender_id,
                "sender_name": message.sender.full_name,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
                "is_mine": message.sender_id == current_user.id,
            }
            for message in messages
        ],
    })


@messaging_bp.route("/api/group/<int:group_id>", methods=["POST"])
@login_required
def send_group_message(group_id):
    group = _allowed_group(group_id)
    if group is None:
        return jsonify({"error": "This group conversation is not available."}), 404
    payload = request.get_json(silent=True) or {}
    raw_content = payload.get("content", "")
    if not isinstance(raw_content, str):
        return jsonify({"error": "Message must be plain text."}), 400
    content = sanitize_text(raw_content.strip(), 500)
    if not content:
        return jsonify({"error": "Write a message before sending."}), 400

    message = GroupMessage(
        group_id=group.id,
        sender_id=current_user.id,
        content=content,
    )
    db.session.add(message)
    member_ids = [
        user_id
        for (user_id,) in db.session.query(User.id)
        .join(GroupChatMember, GroupChatMember.user_id == User.id)
        .filter(
            GroupChatMember.group_id == group.id,
            User.is_active.is_(True),
            or_(User.id == group.mentor_id, User.mentor_id == group.mentor_id),
            User.id != current_user.id,
        )
        .all()
    ]
    db.session.add_all(
        Notification(
            user_id=user_id,
            type="group_message",
            message=f"New message in {group.name} from {current_user.full_name}.",
            related_id=group.id,
        )
        for user_id in member_ids
    )
    db.session.commit()
    return jsonify({
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_name": current_user.full_name,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "is_mine": True,
    }), 201


def _allowed_recipients():
    today = date.today()
    if current_user.role == "admin":
        return User.query.filter(
            User.role.in_(("mentor", "mentee")),
            User.is_active.is_(True),
        ).order_by(User.full_name).all()

    if current_user.role == "mentor":
        substitute_mentee_ids = db.session.query(Substitution.mentee_id).filter(
            Substitution.substitute_mentor_id == current_user.id,
            Substitution.active.is_(True),
            Substitution.start_date <= today,
            Substitution.end_date >= today,
        )
        return User.query.filter(
            User.role == "mentee",
            User.is_active.is_(True),
            or_(User.mentor_id == current_user.id, User.id.in_(substitute_mentee_ids)),
        ).order_by(User.full_name).all()

    if current_user.role == "mentee":
        mentor_ids = [current_user.mentor_id] if current_user.mentor_id else []
        mentor_ids.extend(
            mentor_id
            for (mentor_id,) in db.session.query(Substitution.substitute_mentor_id).filter(
                Substitution.mentee_id == current_user.id,
                Substitution.active.is_(True),
                Substitution.start_date <= today,
                Substitution.end_date >= today,
            ).all()
        )
        return User.query.filter(
            User.id.in_(mentor_ids),
            User.role == "mentor",
            User.is_active.is_(True),
        ).order_by(User.full_name).all() if mentor_ids else []

    return []


def _allowed_recipient(recipient_id):
    return next((user for user in _allowed_recipients() if user.id == recipient_id), None)


@messaging_bp.route("/api/thread/<int:recipient_id>")
@login_required
def thread_messages(recipient_id):
    recipient = _allowed_recipient(recipient_id)
    if recipient is None:
        return jsonify({"error": "This conversation is not available."}), 404

    messages = (
        Message.query.filter(
            or_(
                (Message.sender_id == current_user.id) & (Message.recipient_id == recipient.id),
                (Message.sender_id == recipient.id) & (Message.recipient_id == current_user.id),
            )
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(100)
        .all()
    )
    incoming_ids = [message.id for message in messages if message.recipient_id == current_user.id]
    outgoing_ids = [message.id for message in messages if message.sender_id == current_user.id]
    delivered_ids = set()
    if incoming_ids:
        existing_deliveries = {
            delivery.message_id: delivery
            for delivery in MessageDelivery.query.filter(MessageDelivery.message_id.in_(incoming_ids)).all()
        }
        for message_id in incoming_ids:
            delivery = existing_deliveries.get(message_id)
            if delivery is None:
                delivery = MessageDelivery(
                    message_id=message_id,
                    delivered_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                db.session.add(delivery)
            delivered_ids.add(message_id)
        db.session.commit()
    if outgoing_ids:
        delivered_ids = {
            delivery.message_id
            for delivery in MessageDelivery.query.filter(MessageDelivery.message_id.in_(outgoing_ids)).all()
        }

    messages.reverse()
    return jsonify({
        "recipient": {"id": recipient.id, "name": recipient.full_name, "role": recipient.role},
        "messages": [
            {
                "id": message.id,
                "sender_id": message.sender_id,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
                "is_mine": message.sender_id == current_user.id,
                "is_read": message.is_read,
                "delivered": message.id in delivered_ids
                if message.sender_id == current_user.id
                else True,
                "emergency": message.emergency,
            }
            for message in messages
        ],
    })


@messaging_bp.route("/api/thread/<int:recipient_id>", methods=["POST"])
@login_required
def send_thread_message(recipient_id):
    recipient = _allowed_recipient(recipient_id)
    if recipient is None:
        return jsonify({"error": "This recipient is not available for your account."}), 404

    payload = request.get_json(silent=True) or {}
    raw_content = payload.get("content", "")
    if not isinstance(raw_content, str):
        return jsonify({"error": "Message must be plain text."}), 400
    content = sanitize_text(raw_content.strip(), 500)
    if not content:
        return jsonify({"error": "Write a message before sending."}), 400

    message = Message(
        sender_id=current_user.id,
        recipient_id=recipient.id,
        content=content,
        emergency=payload.get("emergency") is True,
    )
    db.session.add(message)
    db.session.commit()
    add_notification(recipient.id, "message", f"New message from {current_user.full_name}", message.id)
    if message.emergency:
        add_notification(recipient.id, "emergency_message", f"Emergency message from {current_user.full_name}", message.id)
    return jsonify({
        "id": message.id,
        "sender_id": message.sender_id,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "is_mine": True,
        "is_read": False,
        "delivered": False,
        "emergency": message.emergency,
    }), 201


@messaging_bp.route("/api/thread/<int:recipient_id>/seen", methods=["POST"])
@login_required
def mark_thread_seen(recipient_id):
    recipient = _allowed_recipient(recipient_id)
    if recipient is None:
        return jsonify({"error": "This conversation is not available."}), 404
    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("message_ids", [])
    if not isinstance(raw_ids, list) or len(raw_ids) > 100:
        return jsonify({"error": "Invalid message selection."}), 400
    try:
        message_ids = [int(message_id) for message_id in raw_ids]
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid message selection."}), 400
    if message_ids:
        Message.query.filter(
            Message.id.in_(message_ids),
            Message.sender_id == recipient.id,
            Message.recipient_id == current_user.id,
        ).update({"is_read": True}, synchronize_session=False)
        db.session.commit()
    return jsonify({"ok": True})
