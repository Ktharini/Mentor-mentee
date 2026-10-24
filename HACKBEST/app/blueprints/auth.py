from datetime import datetime
from pathlib import Path
from smtplib import SMTPException
from urllib.parse import quote

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth_security import (
    clear_login_attempts,
    consume_forgot_password_limits,
    create_reset_token,
    get_valid_reset_token,
    invalidate_user_sessions,
    login_is_locked,
    password_policy_error,
    record_failed_login,
    utc_now,
)
from app.email_service import send_password_changed_email, send_password_reset_email
from app.forms import ChangePasswordForm, LoginForm, PasswordResetRequestForm, ResetPasswordForm
from app.models import AuditLog, PasswordResetToken, User, UserAuthState, db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()
    selected_role = (request.form.get("role") or request.args.get("role") or "").strip().lower()
    roles = {
        "admin": ("Administrator access", "bi-shield-lock"),
        "mentor": ("Guide learners and manage sessions", "bi-person-workspace"),
        "mentee": ("Connect with your mentor and track goals", "bi-mortarboard"),
    }
    if request.method == "POST" and selected_role not in roles:
        flash("Please choose a role before signing in.", "danger")
        return render_template("auth/login.html", form=form, selected_role="", roles=roles)
    if selected_role not in roles:
        selected_role = ""
    form.role.data = selected_role
    if form.validate_on_submit():
        username = form.username.data.strip()
        role = selected_role
        account_key = f"account:{role or 'legacy'}:{username.casefold()}"
        ip_key = f"ip:{request.remote_addr or 'unknown'}"
        if login_is_locked(account_key, ip_key):
            flash("Too many failed attempts. Please try again in 15 minutes.", "danger")
        else:
            user = User.query.filter_by(username=username).first()
            if user and user.is_active and user.check_password(form.password.data):
                if role and user.role != role:
                    record_failed_login(account_key, ip_key)
                    flash("We couldn't sign you in with those details. Check them and try again.", "danger")
                else:
                    auth_state = db.session.get(UserAuthState, user.id)
                    if auth_state is None:
                        auth_state = UserAuthState(user_id=user.id, session_version=1)
                        db.session.add(auth_state)
                        db.session.commit()
                    clear_login_attempts(account_key, ip_key)
                    login_user(user, remember=form.remember_me.data)
                    session["auth_session_version"] = auth_state.session_version
                    if user.role == "admin":
                        seed_file = Path(current_app.instance_path) / "admin_seed.txt"
                        if seed_file.exists():
                            try:
                                seed_file.unlink()
                            except OSError:
                                current_app.logger.exception("Unable to remove the one-time administrator seed file.")
                    user.last_login_at = utc_now()
                    db.session.commit()
                    AuditLog.log(user.id, "login", "User logged in.")
                    if user.must_change_password:
                        flash("Please choose a new password before continuing.", "warning")
                        return redirect(url_for("auth.change_password"))
                    return redirect(url_for("index"))
            else:
                record_failed_login(account_key, ip_key)
                flash("We couldn't sign you in with those details. Check them and try again.", "danger")
    return render_template("auth/login.html", form=form, selected_role=selected_role, roles=roles)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = PasswordResetRequestForm()
    carried_role = (request.args.get("role") or "").strip().lower()
    if carried_role in {"admin", "mentor", "mentee"}:
        form.role.data = carried_role

    if request.method == "POST":
        username_key = (request.form.get("username") or "").strip()[:50].casefold()
        email_key = (request.form.get("email") or "").strip()[:120].casefold()
        role_key = (request.form.get("role") or "").strip().lower()[:20]
        account_key = f"{role_key}:{username_key}:{email_key}"
        ip_key = request.remote_addr or "unknown"
        allowed = consume_forgot_password_limits(account_key, ip_key)

        if form.validate_on_submit() and allowed:
            user = User.query.filter_by(
                username=form.username.data.strip(),
                role=form.role.data,
                is_active=True,
            ).first()
            email = form.email.data.strip()
            if user and user.email and user.email.casefold() == email.casefold():
                now = utc_now()
                PasswordResetToken.query.filter(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used.is_(False),
                ).update({"used": True}, synchronize_session=False)
                PasswordResetToken.query.filter(PasswordResetToken.expires_at <= now).delete(
                    synchronize_session=False
                )
                raw_token, token = create_reset_token(user.id)
                frontend_url = current_app.config["FRONTEND_URL"] or request.url_root.rstrip("/")
                reset_url = f"{frontend_url}/reset-password?token={quote(raw_token)}"
                try:
                    send_password_reset_email(user, reset_url)
                except (OSError, RuntimeError, SMTPException):
                    current_app.logger.exception("Password reset email delivery failed.")
                    token.used = True
                    db.session.commit()
            flash(
                "If the details match an account, a password reset link has been sent to the registered email.",
                "success",
            )
            return render_template("auth/forgot_password.html", form=form, carried_role=form.role.data)

        if not allowed:
            flash(
                "If the details match an account, a password reset link has been sent to the registered email.",
                "success",
            )
            return render_template("auth/forgot_password.html", form=form, carried_role=form.role.data)

    return render_template(
        "auth/forgot_password.html",
        form=form,
        carried_role=form.role.data or carried_role,
    )


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    raw_token = request.form.get("token", "") if request.method == "POST" else request.args.get("token", "")
    token = get_valid_reset_token(raw_token)
    if token is None:
        flash("This password reset link is invalid or has expired. Request a new link to continue.", "warning")
        return render_template("auth/reset_password_invalid.html"), 400

    form = ResetPasswordForm()
    form.token.data = raw_token
    if form.validate_on_submit():
        password = form.password.data
        policy_error = password_policy_error(password)
        if policy_error:
            form.password.errors.append(policy_error)
        elif token.user.check_password(password):
            form.password.errors.append("Choose a password different from your current password.")
        else:
            now = utc_now()
            changed = PasswordResetToken.query.filter_by(id=token.id, used=False).filter(
                PasswordResetToken.expires_at > now
            ).update({"used": True}, synchronize_session=False)
            if changed != 1:
                db.session.rollback()
                flash("This password reset link is invalid or has expired. Request a new link to continue.", "warning")
                return render_template("auth/reset_password_invalid.html"), 400
            user = token.user
            user.set_password(password)
            invalidate_user_sessions(user.id)
            db.session.commit()
            logout_user()
            session.pop("auth_session_version", None)
            AuditLog.log(user.id, "password_reset", "Password reset using a single-use email token.")
            try:
                send_password_changed_email(user)
            except (OSError, RuntimeError, SMTPException):
                current_app.logger.exception("Password change confirmation email delivery failed.")
            flash("Your password has been changed. Sign in with your new password.", "success")
            return render_template("auth/reset_password_success.html")
    return render_template("auth/reset_password.html", form=form)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("The current password is incorrect.")
            return render_template("auth/change_password.html", form=form), 400
        policy_error = password_policy_error(form.password.data)
        if policy_error:
            form.password.errors.append(policy_error)
            return render_template("auth/change_password.html", form=form), 400
        if current_user.check_password(form.password.data):
            form.password.errors.append("Choose a password different from your current password.")
            return render_template("auth/change_password.html", form=form), 400
        current_user.set_password(form.password.data)
        current_user.must_change_password = False
        session_version = invalidate_user_sessions(current_user.id)
        db.session.commit()
        session["auth_session_version"] = session_version
        AuditLog.log(current_user.id, "password_change", "Password changed by user.")
        flash("Password updated successfully.", "success")
        return redirect(url_for("index"))
    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")


@auth_bp.route("/logout")
@login_required
def logout():
    AuditLog.log(current_user.id, "logout", "User logged out.")
    logout_user()
    session.pop("auth_session_version", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
