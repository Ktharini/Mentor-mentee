import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app, render_template


def _send_email(recipient, subject, text_body, html_body):
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        current_app.logger.info("Email delivery suppressed by configuration.")
        return

    host = current_app.config.get("SMTP_HOST")
    sender = current_app.config.get("SMTP_SENDER")
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_SENDER must be configured to send email.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(
        host,
        current_app.config["SMTP_PORT"],
        timeout=current_app.config["SMTP_TIMEOUT_SECONDS"],
    ) as server:
        if current_app.config["SMTP_USE_TLS"]:
            server.starttls(context=ssl.create_default_context())
        username = current_app.config.get("SMTP_USERNAME")
        if username:
            server.login(username, current_app.config.get("SMTP_PASSWORD", ""))
        server.send_message(message)


def send_password_reset_email(user, reset_url):
    html_body = render_template("emails/password_reset.html", user=user, reset_url=reset_url)
    text_body = (
        f"Hello {user.full_name},\n\n"
        f"Reset your ProGuide password using this link: {reset_url}\n"
        f"The link expires in {current_app.config['RESET_TOKEN_EXPIRY_SECONDS'] // 60} minutes.\n"
        "If you did not request this, ignore this email.\n"
    )
    _send_email(user.email, "Reset your ProGuide password", text_body, html_body)


def send_password_changed_email(user):
    html_body = render_template("emails/password_changed.html", user=user)
    text_body = (
        f"Hello {user.full_name},\n\n"
        "Your ProGuide password was changed. If you did not make this change, contact your administrator.\n"
    )
    _send_email(user.email, "Your ProGuide password was changed", text_body, html_body)
