from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from app.forms import AchievementForm, ActionProgressForm, ConcernForm, ConcernReplyForm, MeetingRequestForm
from app.models import Achievement, ActionAssignment, Concern, Meeting, Message, Notification, User, db
from app.security import role_required
from app.utils import active_substitute_for_mentee, add_notification, append_concern_response, sanitize_text

mentee_bp = Blueprint("mentee", __name__)
ACHIEVEMENT_MAX_BYTES = 10 * 1024 * 1024
ACHIEVEMENT_PROOF_SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}


def _valid_achievement_proof(extension, content):
    signatures = ACHIEVEMENT_PROOF_SIGNATURES.get(extension)
    if not signatures:
        return False
    if extension == ".webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return any(content.startswith(signature) for signature in signatures)


@mentee_bp.route("/dashboard")
@role_required("mentee")
def dashboard():
    mentor = User.query.get(current_user.mentor_id)
    all_assignments = (
        ActionAssignment.query.filter_by(mentee_id=current_user.id)
        .order_by(ActionAssignment.created_at.desc())
        .all()
    )
    report_tasks = [
        {
            "assignment": assignment,
            "progress": 100 if assignment.status == "Completed" else min(max(assignment.progress or 0, 0), 100),
        }
        for assignment in all_assignments[:5]
    ]
    completed_actions = sum(assignment.status == "Completed" for assignment in all_assignments)
    in_progress_actions = sum(assignment.status == "In Progress" for assignment in all_assignments)
    total_progress = sum(
        100 if assignment.status == "Completed" else min(max(assignment.progress or 0, 0), 100)
        for assignment in all_assignments
    )
    progress_percent = (
        (total_progress + len(all_assignments) // 2) // len(all_assignments)
        if all_assignments
        else 0
    )
    meetings = (
        Meeting.query.filter_by(mentee_id=current_user.id)
        .filter(Meeting.date >= date.today(), Meeting.status.in_(["Pending", "Approved", "Rescheduled"]))
        .order_by(Meeting.date, Meeting.time)
        .limit(5)
        .all()
    )
    concerns = Concern.query.filter_by(mentee_id=current_user.id).order_by(Concern.created_at.desc()).limit(5).all()
    substitute = active_substitute_for_mentee(current_user.id)
    return render_template(
        "mentee/dashboard.html",
        mentor=mentor,
        assignments=all_assignments[:5],
        report_tasks=report_tasks,
        completed_actions=completed_actions,
        in_progress_actions=in_progress_actions,
        action_count=len(all_assignments),
        meetings=meetings,
        next_meeting=meetings[0] if meetings else None,
        concerns=concerns,
        substitute=substitute,
        progress_percent=progress_percent,
    )


@mentee_bp.route("/meetings")
@role_required("mentee")
def meetings():
    meetings = Meeting.query.filter_by(mentee_id=current_user.id).order_by(Meeting.created_at.desc()).all()
    return render_template("mentee/meetings.html", meetings=meetings)


@mentee_bp.route("/meetings/new", methods=["GET", "POST"])
@role_required("mentee")
def create_meeting():
    form = MeetingRequestForm()
    if form.validate_on_submit():
        mentor = User.query.get(current_user.mentor_id)
        if not mentor:
            flash("No mentor is assigned to your account yet.", "warning")
            return render_template("mentee/meeting_form.html", form=form, min_meeting_date=date.today())
        meeting = Meeting(
            mentee_id=current_user.id,
            mentor_id=mentor.id,
            requested_by_id=current_user.id,
            date=form.date.data,
            time=form.time.data,
            duration=form.duration.data,
            mode=form.mode.data,
            agenda=form.agenda.data,
            status="Pending",
            reason="Requested by mentee",
        )
        db.session.add(meeting)
        db.session.commit()
        add_notification(mentor.id, "meeting_requested", f"New meeting request from {current_user.full_name}", meeting.id)
        flash("Meeting requested successfully.", "success")
        return redirect(url_for("mentee.meetings"))
    return render_template("mentee/meeting_form.html", form=form, min_meeting_date=date.today())


@mentee_bp.route("/actions")
@role_required("mentee")
def actions():
    assignments = ActionAssignment.query.filter_by(mentee_id=current_user.id).order_by(ActionAssignment.created_at.desc()).all()
    return render_template(
        "mentee/actions.html",
        assignments=assignments,
        progress_form=ActionProgressForm(),
    )


@mentee_bp.route("/actions/<int:assignment_id>", methods=["POST"])
@role_required("mentee")
def update_action(assignment_id):
    assignment = ActionAssignment.query.filter_by(
        id=assignment_id,
        mentee_id=current_user.id,
    ).first_or_404()
    form = ActionProgressForm()
    if form.validate_on_submit():
        assignment.status = form.status.data
        assignment.progress = 100 if form.status.data == "Completed" else form.progress.data
        assignment.notes = form.notes.data.strip() if form.notes.data else ""
        assignment.submitted_at = datetime.utcnow()
        db.session.commit()
        flash("Task progress updated.", "success")
    else:
        flash("Check the task status and enter progress from 0 to 100.", "danger")
    return redirect(url_for("mentee.actions"))


@mentee_bp.route("/achievements", methods=["GET", "POST"])
@role_required("mentee")
def achievements():
    form = AchievementForm()
    if form.validate_on_submit():
        proof = request.files.get("proof")
        original_filename = secure_filename(proof.filename or "") if proof else ""
        extension = Path(original_filename).suffix.lower()
        if not proof or not original_filename:
            flash("Choose an image or PDF file as proof.", "danger")
        elif extension not in ACHIEVEMENT_PROOF_SIGNATURES:
            flash("Proof must be a PDF, JPG, PNG, or WEBP file.", "danger")
        else:
            content = proof.stream.read(ACHIEVEMENT_MAX_BYTES + 1)
            if len(content) > ACHIEVEMENT_MAX_BYTES:
                flash("Proof files must be 10 MB or smaller.", "danger")
            elif not _valid_achievement_proof(extension, content):
                flash("The uploaded file does not match its file type.", "danger")
            else:
                storage_name = f"{uuid4().hex}{extension}"
                upload_dir = Path(current_app.instance_path) / "achievement_proofs"
                upload_dir.mkdir(parents=True, exist_ok=True)
                proof_path = upload_dir / storage_name
                with proof_path.open("xb") as stored_proof:
                    stored_proof.write(content)

                achievement = Achievement(
                    mentee_id=current_user.id,
                    title=form.title.data.strip(),
                    proof_filename=storage_name,
                    original_filename=original_filename,
                )
                try:
                    db.session.add(achievement)
                    db.session.flush()
                    mentor = db.session.get(User, current_user.mentor_id) if current_user.mentor_id else None
                    if mentor and mentor.role == "mentor" and mentor.is_active:
                        db.session.add(Notification(
                            user_id=mentor.id,
                            type="achievement",
                            message=f"{current_user.full_name} shared a new achievement: {achievement.title}",
                            related_id=achievement.id,
                        ))
                    db.session.commit()
                except SQLAlchemyError:
                    db.session.rollback()
                    proof_path.unlink(missing_ok=True)
                    raise
                flash("Achievement shared with your mentor.", "success")
                return redirect(url_for("mentee.achievements"))

    achievements_list = (
        Achievement.query.filter_by(mentee_id=current_user.id)
        .order_by(Achievement.created_at.desc(), Achievement.id.desc())
        .all()
    )
    return render_template("mentee/achievements.html", form=form, achievements=achievements_list)


@mentee_bp.route("/achievements/<int:achievement_id>/proof")
@role_required("mentee")
def achievement_proof(achievement_id):
    achievement = Achievement.query.filter_by(
        id=achievement_id,
        mentee_id=current_user.id,
    ).first_or_404()
    proof_path = Path(current_app.instance_path) / "achievement_proofs" / achievement.proof_filename
    if not proof_path.is_file():
        abort(404)
    return send_file(
        proof_path,
        as_attachment=True,
        download_name=achievement.original_filename,
        conditional=True,
    )


@mentee_bp.route("/concerns", methods=["GET", "POST"])
@role_required("mentee")
def concerns():
    form = ConcernForm()
    if form.validate_on_submit():
        concern = Concern(
            mentee_id=current_user.id,
            mentor_id=current_user.mentor_id,
            title=form.title.data,
            category=form.category.data,
            priority=form.priority.data,
            description=form.description.data,
            status="Open",
        )
        db.session.add(concern)
        db.session.commit()
        if current_user.mentor_id:
            add_notification(current_user.mentor_id, "concern", f"New concern raised: {concern.title}", concern.id)
        flash("Concern raised successfully.", "success")
        return redirect(url_for("mentee.concerns"))
    concerns_list = Concern.query.filter_by(mentee_id=current_user.id).order_by(Concern.created_at.desc()).all()
    return render_template(
        "mentee/concerns.html",
        form=form,
        concerns=concerns_list,
        reply_form=ConcernReplyForm(),
    )


@mentee_bp.route("/concerns/<int:concern_id>/reply", methods=["POST"])
@role_required("mentee")
def reply_to_concern(concern_id):
    concern = Concern.query.filter_by(id=concern_id, mentee_id=current_user.id).first_or_404()
    form = ConcernReplyForm()
    if form.validate_on_submit():
        append_concern_response(concern, form.response.data, current_user.full_name, current_user.role)
        db.session.commit()
        if concern.mentor_id:
            add_notification(
                concern.mentor_id,
                "concern_reply",
                f"{current_user.full_name} replied to a concern: {concern.title}",
                concern.id,
            )
        flash("Reply added to your concern.", "success")
    else:
        flash("Write a reply before submitting.", "danger")
    return redirect(url_for("mentee.concerns"))


@mentee_bp.route("/messages")
@role_required("mentee")
def messages():
    return redirect(url_for("messaging.inbox"))
