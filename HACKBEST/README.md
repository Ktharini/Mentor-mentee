# ProGuide

ProGuide is a mentor-mentee management application built with Flask. It provides role-based access for admins, mentors, and mentees with messaging, meetings, concerns, actions, notifications, and audit logging.

## Setup

1. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   . .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the application:
   ```bash
   python apphack.py
   ```

The app starts on `http://127.0.0.1:5000`.

### Email and production configuration

Copy `.env.example` to `.env` and set the SMTP host, username, password, sender and `FRONTEND_URL`. Set `SEED_ADMIN_EMAIL` to a reachable inbox before first setup; if the existing seeded admin still has the default `admin@proguide.local` address, startup updates it from this setting. The app loads these settings from the environment (or the ignored local `.env` file) and sends email using Python's SMTP client with STARTTLS. For production, set `APP_ENV=production`, provide a random `SECRET_KEY` of at least 32 characters, use an HTTPS `FRONTEND_URL`, and keep SMTP TLS enabled. Production startup rejects missing secret, HTTPS URL, or SMTP credentials. Never commit `.env` or put real credentials in `.env.example`.

`RESET_TOKEN_EXPIRY_SECONDS` defaults to `900` (15 minutes). Reset tokens are random, stored only as SHA-256 hashes, single-use, and removed after expiry by periodic application cleanup. Login failures are throttled after five attempts for 15 minutes; reset requests are limited to five per hour per IP and per submitted account. The existing `users` table is unchanged; SQLAlchemy creates separate tables for reset tokens, throttles, and session-version revocation. Access logs redact the token query parameter in Werkzeug; configure any upstream proxy to redact it as well.

## Default admin account

On first run, the app automatically creates a default admin account:

- Username: `admin`
- Set `SEED_ADMIN_PASSWORD` in the environment to supply a provisioning password. Otherwise, the app generates one and stores it temporarily in the ignored `instance/admin_seed.txt` file.
- The first successful admin login deletes the local seed file and forces a password change. The app never prints the password to its logs.

## Features

- Admin dashboard for user management, allocations, substitutions, reports, and audit logs
- Admin Excel import for up to 500 mentees, with generated temporary passwords delivered in a no-cache CSV download
- Mentor-owned substitution scheduling and editing for directly assigned mentees
- Role-aware mentor and mentee dashboards
- Private mentor-mentee messaging with emergency override support
- WhatsApp-style shared inbox with direct conversations and a separate group chat for each mentor and their active, directly assigned mentees
- Meeting request, approval, rescheduling, and status tracking
- Concern tracking and status updates
- Assignment management with progress tracking and overdue detection
- Mentee task status, progress and notes updates, with ownership checks
- Mentee dashboard progress report with overall progress, task counts and per-task progress bars
- Mentees can share achievement titles with PDF or image proof; mentors receive a notification and can review achievements per mentee
- Threaded concern replies and status updates for the mentee, assigned mentor and admin
- Messaging recipient lists limited to assigned/actively covered mentees and the mentee's assigned/cover mentors
- Validated mentor allocation and substitution changes, including role, date and overlap checks
- Mentee meeting requests restricted to today or later and 15-240 minutes
- Admin self-deactivation is blocked, and the last active administrator cannot be deactivated
- Notifications and in-app alert center
- Security headers and rate limiting via Flask-Talisman and Flask-Limiter
- Responsive, role-specific slide-in navigation drawer with keyboard and touch support
- Light/dark appearance toggle, notification dropdown, and Ctrl+K page/person search
- Interactive admin activity chart, first-visit workspace tour, animated dashboard counts, and accessible empty states

## Demo and role testing

There are no hard-coded demo mentor or mentee accounts. On first run, provision the admin with `SEED_ADMIN_PASSWORD` or read the one-time generated password locally from `instance/admin_seed.txt`; it is deleted after the first successful admin login. Change it when prompted. From **User management**, create a mentor and mentee, then assign the mentee to the mentor in **Mentor matching**. Each new account is issued a temporary password and must change it on first sign-in.

Use each account in a separate browser profile or sign out before switching roles:

1. At `/login`, choose the matching role card, sign in with each role's username/password, and verify Admin, Mentor and Mentee reach their own dashboards.
2. Enter valid credentials under a different role card; login is rejected with a role-mismatch message. Wrong passwords use a generic message. Five failed attempts start a 15-minute cooldown.
3. Try opening another role's dashboard URL directly; the server responds with an access-denied page and HTTP 403.
4. Use **Forgot password?** with a matching username, registered email and role. With SMTP configured, verify the reset email's HTTPS link works and expires after 15 minutes.
5. Repeat with a non-matching email or role; the same neutral confirmation appears, and no message is sent.
6. Open an expired or already-used reset link; it is rejected and offers a link to request another.
7. Submit a password missing an uppercase letter, lowercase letter, number, or special character; inline validation prevents the reset. Also check confirmation mismatch and that the current password cannot be reused.
8. Complete a reset and verify the previous password no longer works, the new password does, the confirmation email is sent, and any previously signed-in browser is logged out.

For local flow tests without an SMTP server, set `MAIL_SUPPRESS_SEND=true`; automated tests replace the sender to inspect generated links without sending mail. `pytest` covers role mismatch/lockout, neutral matching and non-matching reset requests, reset password rules, expired and reused tokens, and session invalidation.

The menu contains only routes currently implemented for that role. Features without existing backend routes or database support (such as mentor ratings and resource uploads) are not represented as working links.

### Bulk student import and mentor substitutions

Admins can open **User management → Import students**, download the `.xlsx` template, and fill `username`, `full_name`, `email`, plus an optional active `mentor_username`. Imports accept up to 500 rows and 5 MB per workbook. The import is all-or-nothing: invalid or duplicate rows prevent every account from being created. New mentee accounts receive unique temporary passwords and must change them at first login. The one-time CSV response contains those credentials; deliver it securely and delete the local copy after distribution.

Mentors can open **Substitutions** from their navigation drawer to schedule, update, or deactivate substitutions for their directly assigned mentees. Each new mentor substitution automatically applies the selected substitute, reason and date range to every active mentee assigned to that mentor. Batch creation is atomic: if any assigned active mentee already has overlapping active coverage, none of the substitutions are created until the conflict is resolved. Mentors can select only another active mentor. Admin substitution management remains available.

### Navigation and accessibility

- Use the top-left menu button to open the role-specific drawer; close it with **Esc**, the close button, an outside click, a menu selection, or a left swipe on touch screens.
- Use **Ctrl+K** (or **Cmd+K** on macOS) to open search for available pages and role-accessible people.
- Toggle light/dark appearance from the drawer. The preference is stored in the current browser.
- The first time a role dashboard is opened in a browser, a dismissible ProGuide tour introduces navigation, search, and notifications.

## Security notes

- All role checks are enforced server-side.
- Passwords are hashed using bcrypt.
- Password changes require the current password, enforce complexity and bcrypt's 72-byte limit, and invalidate other sessions. Deactivated accounts and users with an unmodified temporary password cannot access protected routes.
- Temporary user passwords are displayed only in a no-cache response, never in session flash cookies or logs.
- Keep the instance directory private and exclude it from archives; the generated admin seed credential exists there only until the first admin login.
- SQLite is accessed through SQLAlchemy ORM with parameterized queries.
- The app enforces basic CSRF protection and uses security headers for browser hardening.

## Tests

```bash
pytest
```
