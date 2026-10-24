from datetime import datetime

import bcrypt
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="mentee")
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, raw_password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(raw_password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, raw_password):
        return bcrypt.checkpw(raw_password.encode("utf-8"), self.password_hash.encode("utf-8"))

    @property
    def has_role(self):
        return self.role

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User")


class AuthAttempt(db.Model):
    __tablename__ = "auth_attempts"

    id = db.Column(db.Integer, primary_key=True)
    key_hash = db.Column(db.String(64), nullable=False, unique=True)
    count = db.Column(db.Integer, nullable=False, default=0)
    window_started_at = db.Column(db.DateTime, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)


class UserAuthState(db.Model):
    __tablename__ = "user_auth_states"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    session_version = db.Column(db.Integer, nullable=False, default=1)

    user = db.relationship("User")


class Meeting(db.Model):
    __tablename__ = "meetings"

    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(30), default="Pending")
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(10), nullable=False)
    duration = db.Column(db.Integer, default=60)
    mode = db.Column(db.String(20), default="online")
    agenda = db.Column(db.Text, nullable=False)
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    decision_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mentee = db.relationship("User", foreign_keys=[mentee_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    requester = db.relationship("User", foreign_keys=[requested_by_id])


class Concern(db.Model):
    __tablename__ = "concerns"

    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default="medium")
    status = db.Column(db.String(30), default="Open")
    comments = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mentee = db.relationship("User", foreign_keys=[mentee_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])


class Action(db.Model):
    __tablename__ = "actions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.Date, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])


class ActionAssignment(db.Model):
    __tablename__ = "action_assignments"

    id = db.Column(db.Integer, primary_key=True)
    action_id = db.Column(db.Integer, db.ForeignKey("actions.id"), nullable=False)
    mentee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(30), default="Not Started")
    progress = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text, default="")
    feedback = db.Column(db.Text, default="")
    submitted_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    action = db.relationship("Action", backref="assignments")
    mentee = db.relationship("User", foreign_keys=[mentee_id])


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    emergency = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])


class MessageDelivery(db.Model):
    __tablename__ = "message_deliveries"

    message_id = db.Column(db.Integer, db.ForeignKey("messages.id"), primary_key=True)
    delivered_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    message = db.relationship("Message")


class GroupChat(db.Model):
    __tablename__ = "group_chats"

    id = db.Column(db.Integer, primary_key=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    mentor = db.relationship("User", foreign_keys=[mentor_id])
    members = db.relationship(
        "GroupChatMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    messages = db.relationship(
        "GroupMessage",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="GroupMessage.created_at",
    )


class GroupChatMember(db.Model):
    __tablename__ = "group_chat_members"

    group_id = db.Column(db.Integer, db.ForeignKey("group_chats.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("GroupChat", back_populates="members")
    user = db.relationship("User", foreign_keys=[user_id])


class GroupMessage(db.Model):
    __tablename__ = "group_messages"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group_chats.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("GroupChat", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id])


class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    proof_filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    mentee = db.relationship("User", foreign_keys=[mentee_id])


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    related_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])

    @staticmethod
    def add(user_id, type_name, message, related_id=None):
        notification = Notification(user_id=user_id, type=type_name, message=message, related_id=related_id)
        db.session.add(notification)
        db.session.commit()
        return notification


class Substitution(db.Model):
    __tablename__ = "substitutions"

    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    substitute_mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    mentee = db.relationship("User", foreign_keys=[mentee_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    substitute = db.relationship("User", foreign_keys=[substitute_mentor_id])


class AllocationHistory(db.Model):
    __tablename__ = "allocation_history"

    id = db.Column(db.Integer, primary_key=True)
    mentee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    old_mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    new_mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])

    @staticmethod
    def log(user_id, action, details):
        log = AuditLog(user_id=user_id, action=action, details=details)
        db.session.add(log)
        db.session.commit()
        return log
