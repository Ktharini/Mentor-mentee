import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.models import AuthAttempt, PasswordResetToken, UserAuthState, db


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def password_policy_error(password):
    if len(password) < 8:
        return "Use at least 8 characters, including uppercase, lowercase, a number, and a special character."
    if len(password.encode("utf-8")) > 72:
        return "For account security, passwords must be at most 72 UTF-8 bytes."
    if not (
        re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"\d", password)
        and re.search(r"[^A-Za-z0-9]", password)
    ):
        return "Use at least 8 characters, including uppercase, lowercase, a number, and a special character."
    return None


def _key_hash(value):
    secret = current_app.secret_key
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _attempt_row(scope, value, window_seconds):
    key_hash = _key_hash(f"{scope}:{value}")
    row = AuthAttempt.query.filter_by(key_hash=key_hash).first()
    now = utc_now()
    if row is None:
        row = AuthAttempt(key_hash=key_hash, count=0, window_started_at=now)
        db.session.add(row)
        db.session.flush()
    elif now - row.window_started_at >= timedelta(seconds=window_seconds):
        row.count = 0
        row.window_started_at = now
        row.locked_until = None
    return row


def login_is_locked(account_key, ip_key):
    now = utc_now()
    for key in (account_key, ip_key):
        row = AuthAttempt.query.filter_by(key_hash=_key_hash(f"login:{key}")).first()
        if row and row.locked_until and row.locked_until > now:
            return True
    return False


def record_failed_login(account_key, ip_key):
    now = utc_now()
    for key in (account_key, ip_key):
        row = _attempt_row("login", key, 900)
        row.count += 1
        if row.count >= 5:
            row.locked_until = now + timedelta(minutes=15)
    db.session.commit()


def clear_login_attempts(account_key, ip_key):
    hashes = [_key_hash(f"login:{key}") for key in (account_key, ip_key)]
    AuthAttempt.query.filter(AuthAttempt.key_hash.in_(hashes)).delete(synchronize_session=False)
    db.session.commit()


def consume_forgot_password_limits(account_key, ip_key):
    allowed = True
    for key in (f"forgot-account:{account_key}", f"forgot-ip:{ip_key}"):
        row = _attempt_row("forgot", key, 3600)
        if row.count >= 5:
            allowed = False
        else:
            row.count += 1
    db.session.commit()
    return allowed


def create_reset_token(user_id):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expiry_seconds = current_app.config["RESET_TOKEN_EXPIRY_SECONDS"]
    created_at = utc_now()
    token = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        created_at=created_at,
        expires_at=created_at + timedelta(seconds=expiry_seconds),
    )
    db.session.add(token)
    db.session.commit()
    return raw_token, token


def get_valid_reset_token(raw_token):
    if not raw_token or len(raw_token) > 256:
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if (
        token is None
        or token.used
        or token.expires_at <= utc_now()
        or not hmac.compare_digest(token.token_hash, token_hash)
    ):
        return None
    return token


def invalidate_user_sessions(user_id):
    state = db.session.get(UserAuthState, user_id)
    if state is None:
        state = UserAuthState(user_id=user_id, session_version=1)
        db.session.add(state)
    else:
        state.session_version += 1
    db.session.flush()
    return state.session_version
