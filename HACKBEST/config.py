import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    APP_ENV = os.environ.get("APP_ENV", "development").lower()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'proguide.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    JSON_SORT_KEYS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_SECURE = APP_ENV == "production"
    SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@proguide.local").strip()
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    RATELIMIT_STORAGE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'ratelimit.db'}"
    RATELIMIT_DEFAULT = "200/day;50/hour"
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
    RESET_TOKEN_EXPIRY_SECONDS = int(os.environ.get("RESET_TOKEN_EXPIRY_SECONDS", "900"))
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_SENDER = os.environ.get("SMTP_SENDER", "")
    SMTP_TIMEOUT_SECONDS = int(os.environ.get("SMTP_TIMEOUT_SECONDS", "10"))
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "false").lower() == "true"
