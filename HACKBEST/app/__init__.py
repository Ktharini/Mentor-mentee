import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from flask import Flask, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect

from app.models import AuthAttempt, AuditLog, Meeting, Notification, PasswordResetToken, User, UserAuthState, db

from .extensions import limiter
from .blueprints.admin import admin_bp
from .blueprints.api import api_bp
from .blueprints.auth import auth_bp
from .blueprints.mentee import mentee_bp
from .blueprints.mentor import mentor_bp
from .blueprints.messaging import messaging_bp
from .utils import generate_strong_password

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
csrf = CSRFProtect()
talisman = Talisman()


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user is None or not user.is_active:
        return None
    auth_state = db.session.get(UserAuthState, user.id)
    session_version = session.get("auth_session_version")
    if auth_state and session_version is not None and session_version != auth_state.session_version:
        return None
    if auth_state and auth_state.session_version > 1 and session_version is None:
        return None
    return user


def seed_default_admin(app):
    seed_file = Path(app.instance_path) / "admin_seed.txt"
    configured_password = os.environ.get("SEED_ADMIN_PASSWORD")
    admin = User.query.filter_by(username="admin").first()
    if admin:
        app.config["SEED_ADMIN_USERNAME"] = "admin"
        app.config["SEED_ADMIN_PASSWORD"] = (
            configured_password or (seed_file.read_text().strip() if seed_file.exists() else "")
        )
        configured_email = app.config.get("SEED_ADMIN_EMAIL")
        if configured_email and admin.email == "admin@proguide.local":
            admin.email = configured_email
            db.session.commit()
        return

    if configured_password:
        password = configured_password
    elif seed_file.exists():
        password = seed_file.read_text().strip()
    else:
        password = generate_strong_password(14)
    app.config["SEED_ADMIN_USERNAME"] = "admin"
    app.config["SEED_ADMIN_PASSWORD"] = password
    seed_file.parent.mkdir(parents=True, exist_ok=True)
    if not configured_password and not seed_file.exists():
        seed_file.write_text(password)

    admin = User(
        username="admin",
        full_name="System Administrator",
        email=app.config.get("SEED_ADMIN_EMAIL") or "admin@proguide.local",
        role="admin",
        is_active=True,
        must_change_password=True,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    AuditLog.log(user_id=admin.id, action="seed_admin", details="Default administrator seed created.")


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object("config.Config")
    if app.config["RESET_TOKEN_EXPIRY_SECONDS"] <= 0:
        raise RuntimeError("RESET_TOKEN_EXPIRY_SECONDS must be greater than zero.")
    if app.config["APP_ENV"] == "production":
        if not os.environ.get("SECRET_KEY") or len(app.config["SECRET_KEY"]) < 32:
            raise RuntimeError("Production requires a SECRET_KEY of at least 32 characters.")
        if not app.config["FRONTEND_URL"].startswith("https://"):
            raise RuntimeError("Production requires FRONTEND_URL to use HTTPS.")
        if not all(app.config[key] for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_SENDER")):
            raise RuntimeError("Production requires SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_SENDER.")
        if not app.config["SMTP_USE_TLS"]:
            raise RuntimeError("Production SMTP connections must use TLS.")
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    talisman.init_app(
        app,
        content_security_policy={
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
            "style-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
            "img-src": ["'self'", "data:", "https://cdn.jsdelivr.net"],
            "font-src": ["'self'", "https://fonts.gstatic.com", "https://cdn.jsdelivr.net"],
        },
        force_https=app.config["APP_ENV"] == "production",
    )

    with app.app_context():
        db.create_all()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        PasswordResetToken.query.filter(PasswordResetToken.expires_at <= now).delete(
            synchronize_session=False
        )
        AuthAttempt.query.filter(AuthAttempt.window_started_at <= now - timedelta(days=1)).delete(
            synchronize_session=False
        )
        db.session.commit()
        seed_default_admin(app)

    class RedactResetTokenFilter(logging.Filter):
        def filter(self, record):
            message = re.sub(
                r"([?&]token=)[^&\s]+",
                r"\1[REDACTED]",
                record.getMessage(),
                flags=re.IGNORECASE,
            )
            record.msg = message
            record.args = ()
            return True

    RedactResetTokenFilter._proguide_filter = True
    werkzeug_logger = logging.getLogger("werkzeug")
    if not any(getattr(item, "_proguide_filter", False) for item in werkzeug_logger.filters):
        werkzeug_logger.addFilter(RedactResetTokenFilter())
    app.extensions["auth_cleanup_last_run"] = time.monotonic()
    app.extensions["auth_cleanup_lock"] = Lock()

    @app.before_request
    def cleanup_expired_auth_records():
        now_monotonic = time.monotonic()
        lock = app.extensions["auth_cleanup_lock"]
        if now_monotonic - app.extensions["auth_cleanup_last_run"] < 3600 or not lock.acquire(blocking=False):
            return
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            cutoff = now - timedelta(days=1)
            PasswordResetToken.query.filter(PasswordResetToken.expires_at <= now).delete(
                synchronize_session=False
            )
            AuthAttempt.query.filter(AuthAttempt.window_started_at <= cutoff).delete(synchronize_session=False)
            db.session.commit()
            app.extensions["auth_cleanup_last_run"] = now_monotonic
        finally:
            lock.release()

    @app.before_request
    def enforce_temporary_password_change():
        if (
            current_user.is_authenticated
            and current_user.must_change_password
            and request.endpoint not in {"auth.change_password", "auth.logout", "static"}
        ):
            return redirect(url_for("auth.change_password"))

    @app.context_processor
    def inject_globals():
        unread_count = 0
        pending_meeting_count = 0
        if current_user.is_authenticated:
            unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            if current_user.role == "mentor":
                pending_meeting_count = Meeting.query.filter_by(
                    mentor_id=current_user.id,
                    status="Pending",
                ).count()
        menu_sections = []
        if current_user.is_authenticated:
            if current_user.role == "admin":
                menu_sections = [
                    {"title": "Overview", "items": [
                        {"label": "Dashboard", "icon": "bi-grid-1x2", "endpoint": "admin.dashboard"},
                        {"label": "User management", "icon": "bi-people", "endpoint": "admin.users"},
                        {"label": "Mentor matching", "icon": "bi-diagram-3", "endpoint": "admin.allocations"},
                        {"label": "Substitutions", "icon": "bi-arrow-left-right", "endpoint": "admin.substitutions"},
                    ]},
                    {"title": "Platform", "items": [
                        {"label": "Concerns", "icon": "bi-chat-square-text", "endpoint": "admin.concerns"},
                        {"label": "Reports & analytics", "icon": "bi-bar-chart", "endpoint": "admin.stats"},
                        {"label": "Audit log", "icon": "bi-shield-check", "endpoint": "admin.audit"},
                    ]},
                ]
            elif current_user.role == "mentor":
                menu_sections = [
                    {"title": "Workspace", "items": [
                        {"label": "Dashboard", "icon": "bi-grid-1x2", "endpoint": "mentor.dashboard"},
                        {"label": "My mentees", "icon": "bi-people", "endpoint": "mentor.mentees"},
                        {"label": "Students Achievements", "icon": "bi-trophy", "endpoint": "mentor.student_achievements"},
                        {"label": "Meetings", "icon": "bi-calendar3", "endpoint": "mentor.meetings"},
                        {"label": "Substitutions", "icon": "bi-arrow-left-right", "endpoint": "mentor.substitutions"},
                    ]},
                    {"title": "Mentoring", "items": [
                        {"label": "Actions & assignments", "icon": "bi-check2-square", "endpoint": "mentor.actions"},
                        {"label": "Concerns", "icon": "bi-chat-square-text", "endpoint": "mentor.concerns"},
                        {"label": "Messages", "icon": "bi-chat-dots", "endpoint": "messaging.inbox"},
                    ]},
                ]
            elif current_user.role == "mentee":
                menu_sections = [
                    {"title": "My learning", "items": [
                        {"label": "Dashboard", "icon": "bi-grid-1x2", "endpoint": "mentee.dashboard"},
                        {"label": "Book a session", "icon": "bi-calendar-plus", "endpoint": "mentee.create_meeting"},
                        {"label": "My sessions", "icon": "bi-calendar3", "endpoint": "mentee.meetings"},
                        {"label": "Tasks & progress", "icon": "bi-check2-square", "endpoint": "mentee.actions"},
                        {"label": "My achievements", "icon": "bi-trophy", "endpoint": "mentee.achievements"},
                    ]},
                    {"title": "Stay connected", "items": [
                        {"label": "My concerns", "icon": "bi-chat-square-text", "endpoint": "mentee.concerns"},
                        {"label": "Messages", "icon": "bi-chat-dots", "endpoint": "messaging.inbox"},
                    ]},
                ]
        page_titles = {
            "admin.dashboard": "Admin dashboard", "admin.users": "User management",
            "admin.create_user": "Add a user", "admin.allocations": "Mentor matching",
            "admin.substitutions": "Substitutions", "admin.stats": "Reports & analytics",
            "admin.concerns": "Concerns", "admin.audit": "Audit log",
            "mentor.dashboard": "Mentor dashboard", "mentor.mentees": "My mentees",
            "mentor.student_achievements": "Students Achievements",
            "mentor.mentee_achievements": "Student achievements",
            "mentor.meetings": "Meetings", "mentor.substitutions": "Mentor substitutions",
            "mentor.update_substitution": "Mentor substitutions",
            "mentor.meeting_detail": "Meeting details",
            "mentor.actions": "Actions & assignments", "mentor.create_action": "Create an action",
            "mentor.concerns": "Concerns", "mentor.messages": "Messages",
            "mentee.dashboard": "Mentee dashboard", "mentee.meetings": "My sessions",
            "mentee.create_meeting": "Book a session", "mentee.actions": "Tasks & progress",
            "mentee.achievements": "My achievements", "mentee.achievement_proof": "Achievement proof",
            "mentee.concerns": "My concerns", "mentee.messages": "Messages",
            "messaging.inbox": "Inbox", "auth.profile": "My profile",
            "auth.change_password": "Change password", "auth.login": "Sign in to ProGuide",
            "auth.forgot_password": "Recover your account", "auth.reset_password": "Set a new password",
        }
        endpoint = request.endpoint
        return {
            "unread_count": unread_count,
            "pending_meeting_count": pending_meeting_count,
            "current_user_role": current_user.role if current_user.is_authenticated else None,
            "menu_sections": menu_sections,
            "page_title": page_titles.get(endpoint, "Welcome to ProGuide"),
        }

    @app.route("/")
    @login_required
    def index():
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "mentor":
            return redirect(url_for("mentor.dashboard"))
        return redirect(url_for("mentee.dashboard"))

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(mentor_bp, url_prefix="/mentor")
    app.register_blueprint(mentee_bp, url_prefix="/mentee")
    app.register_blueprint(messaging_bp, url_prefix="/messages")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    return app
