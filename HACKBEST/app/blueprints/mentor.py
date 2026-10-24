from datetime import date, datetime

from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user

from app.forms import ActionForm, ConcernReviewForm, MeetingDecisionForm, MentorMeetingForm, MentorSubstitutionForm, MessageForm
from app.models import Achievement, Action, ActionAssignment, AuditLog, Concern, Meeting, Message, Notification, Substitution, User, db
from app.security import can_access_mentee, role_required
from app.utils import add_notification, append_concern_response, sanitize_text, user_is_mentor_for_mentee

mentor_bp = Blueprint("mentor", __name__)


@mentor_bp.route("/dashboard")
@role_required("mentor")
def dashboard():
    mentees = User.query.filter_by(role="mentee", mentor_id=current_user.id).all()
    meetings = Meeting.query.filter_by(mentor_id=current_user.id).order_by(Meeting.created_at.desc()).all()
    concerns = Concern.query.filter(Concern.mentee_id.in_([m.id for m in mentees])).order_by(Concern.created_at.desc()).limit(10).all()
    actions = Action.query.filter_by(created_by_id=current_user.id).order_by(Action.created_at.desc()).limit(10).all()
    upcoming_meetings = (
        Meeting.query.filter_by(mentor_id=current_user.id)
        .filter(Meeting.date >= date.today(), Meeting.status.in_(["Pending", "Approved", "Rescheduled"]))
        .order_by(Meeting.date, Meeting.time)
        .limit(5)
        .all()
    )
    pending_requests = Meeting.query.filter_by(mentor_id=current_user.id, status="Pending").count()
    recent_messages = (
        Message.query.filter(
            (Message.sender_id == current_user.id) | (Message.recipient_id == current_user.id)
        )
        .order_by(Message.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "mentor/dashboard.html",
        mentees=mentees,
        meetings=meetings,
        upcoming_meetings=upcoming_meetings,
        pending_requests=pending_requests,
        concerns=concerns,
        actions=actions,
        recent_messages=recent_messages,
        average_rating=None,
    )


@mentor_bp.route("/mentees")
@role_required("mentor")
def mentees():
    mentees = User.query.filter_by(role="mentee", mentor_id=current_user.id).all()
    return render_template("mentor/mentees.html", mentees=mentees)


@mentor_bp.route("/achievements")
@role_required("mentor")
def student_achievements():
    mentees = User.query.filter_by(
        role="mentee",
        mentor_id=current_user.id,
        is_active=True,
    ).order_by(User.full_name).all()
    achievements_by_mentee = {
        mentee.id: Achievement.query.filter_by(mentee_id=mentee.id)
        .order_by(Achievement.created_at.desc(), Achievement.id.desc())
        .all()
        for mentee in mentees
    }
    return render_template(
        "mentor/achievements.html",
        mentees=mentees,
        achievements_by_mentee=achievements_by_mentee,
    )


@mentor_bp.route("/achievements/<int:mentee_id>")
@role_required("mentor")
def mentee_achievements(mentee_id):
    mentee = User.query.filter_by(
        id=mentee_id,
        role="mentee",
        mentor_id=current_user.id,
        is_active=True,
    ).first_or_404()
    achievements_list = Achievement.query.filter_by(mentee_id=mentee.id).order_by(
        Achievement.created_at.desc(),
        Achievement.id.desc(),
    ).all()
    achievement_ids = [achievement.id for achievement in achievements_list]
    if achievement_ids:
        Notification.query.filter(
            Notification.user_id == current_user.id,
            Notification.type == "achievement",
            Notification.related_id.in_(achievement_ids),
            Notification.is_read.is_(False),
        ).update({"is_read": True}, synchronize_session=False)
        db.session.commit()
    return render_template(
        "mentor/mentee_achievements.html",
        mentee=mentee,
        achievements=achievements_list,
    )


@mentor_bp.route("/achievements/<int:mentee_id>/<int:achievement_id>/proof")
@role_required("mentor")
def student_achievement_proof(mentee_id, achievement_id):
    achievement = Achievement.query.join(User, Achievement.mentee_id == User.id).filter(
        Achievement.id == achievement_id,
        Achievement.mentee_id == mentee_id,
        User.role == "mentee",
        User.mentor_id == current_user.id,
        User.is_active.is_(True),
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


@mentor_bp.route("/substitutions", methods=["GET", "POST"])
@role_required("mentor")
def substitutions():
    form = MentorSubstitutionForm()
    assigned_mentees = User.query.filter_by(
        role="mentee",
        mentor_id=current_user.id,
        is_active=True,
    ).order_by(User.full_name).all()
    substitute_mentors = User.query.filter(
        User.role == "mentor",
        User.is_active.is_(True),
        User.id != current_user.id,
    ).order_by(User.full_name).all()
    form.mentee_id.choices = [(mentee.id, mentee.full_name) for mentee in assigned_mentees]
    form.substitute_mentor_id.choices = [(mentor.id, mentor.full_name) for mentor in substitute_mentors]

    if form.validate_on_submit():
        target_mentee_ids = [mentee.id for mentee in assigned_mentees]
        if not target_mentee_ids:
            flash("You need at least one active assigned mentee to create a substitution.", "danger")
        elif form.start_date.data < date.today():
            flash("A substitution cannot start in the past.", "danger")
        elif form.end_date.data < form.start_date.data:
            flash("The end date must be on or after the start date.", "danger")
        else:
            overlapping = Substitution.query.filter(
                Substitution.mentee_id.in_(target_mentee_ids),
                Substitution.active.is_(True),
                Substitution.start_date <= form.end_date.data,
                Substitution.end_date >= form.start_date.data,
            ).all()
            if overlapping:
                conflict_ids = {item.mentee_id for item in overlapping}
                conflict_names = [
                    mentee.full_name for mentee in assigned_mentees if mentee.id in conflict_ids
                ]
                flash(
                    "No substitutions were created because active coverage overlaps for: "
                    + ", ".join(conflict_names)
                    + ".",
                    "danger",
                )
            else:
                target_mentees = [mentee for mentee in assigned_mentees if mentee.id in target_mentee_ids]
                records = [
                    Substitution(
                        mentee_id=mentee.id,
                        mentor_id=current_user.id,
                        substitute_mentor_id=form.substitute_mentor_id.data,
                        reason=form.reason.data.strip(),
                        start_date=form.start_date.data,
                        end_date=form.end_date.data,
                        active=True,
                    )
                    for mentee in target_mentees
                ]
                db.session.add_all(records)
                db.session.add_all([
                    Notification(
                        user_id=mentee.id,
                        type="substitution",
                        message="Your mentor has arranged a temporary mentor substitution.",
                    )
                    for mentee in target_mentees
                ])
                db.session.add(AuditLog(
                    user_id=current_user.id,
                    action="mentor_substitution_create",
                    details=(
                        f"Created a substitution for {len(target_mentees)} mentee(s): "
                        + ", ".join(mentee.username for mentee in target_mentees)
                        + "."
                    ),
                ))
                db.session.commit()
                flash(
                    f"Substitution saved for all {len(target_mentees)} active mentees.",
                    "success",
                )
                return redirect(url_for("mentor.substitutions"))

    mentee_ids = db.session.query(User.id).filter_by(
        role="mentee",
        mentor_id=current_user.id,
    )
    substitutions = (
        Substitution.query.filter(
            Substitution.mentor_id == current_user.id,
            Substitution.mentee_id.in_(mentee_ids),
        )
        .order_by(Substitution.start_date.desc())
        .all()
    )
    return render_template(
        "mentor/substitutions.html",
        form=form,
        assigned_mentees=assigned_mentees,
        substitute_mentors=substitute_mentors,
        substitutions=substitutions,
        today=date.today(),
    )


@mentor_bp.route("/substitutions/<int:substitution_id>", methods=["POST"])
@role_required("mentor")
def update_substitution(substitution_id):
    substitution = Substitution.query.filter_by(
        id=substitution_id,
        mentor_id=current_user.id,
    ).first_or_404()
    mentee = User.query.filter_by(
        id=substitution.mentee_id,
        role="mentee",
        mentor_id=current_user.id,
    ).first_or_404()
    form = MentorSubstitutionForm()
    form.mentee_id.choices = [(mentee.id, mentee.full_name)]
    substitute_mentors = User.query.filter(
        User.role == "mentor",
        User.is_active.is_(True),
        User.id != current_user.id,
    ).order_by(User.full_name).all()
    form.substitute_mentor_id.choices = [(mentor.id, mentor.full_name) for mentor in substitute_mentors]

    if form.validate_on_submit():
        if form.mentee_id.data != substitution.mentee_id:
            abort(404)
        if form.active.data and form.start_date.data < date.today():
            flash("An active substitution cannot start in the past.", "danger")
        elif form.end_date.data < form.start_date.data:
            flash("The end date must be on or after the start date.", "danger")
        elif form.active.data and Substitution.query.filter(
            Substitution.id != substitution.id,
            Substitution.mentee_id == substitution.mentee_id,
            Substitution.active.is_(True),
            Substitution.start_date <= form.end_date.data,
            Substitution.end_date >= form.start_date.data,
        ).first():
            flash("This mentee already has an active substitution during those dates.", "danger")
        else:
            substitution.substitute_mentor_id = form.substitute_mentor_id.data
            substitution.reason = form.reason.data.strip()
            substitution.start_date = form.start_date.data
            substitution.end_date = form.end_date.data
            substitution.active = form.active.data
            db.session.add(Notification(
                user_id=mentee.id,
                type="substitution",
                message=f"Your mentor substitution was updated and is {'active' if substitution.active else 'inactive'}.",
            ))
            db.session.add(AuditLog(
                user_id=current_user.id,
                action="mentor_substitution_update",
                details=f"Updated substitution ID {substitution.id}.",
            ))
            db.session.commit()
            flash("Substitution updated.", "success")
            return redirect(url_for("mentor.substitutions"))

    mentee_ids = db.session.query(User.id).filter_by(
        role="mentee",
        mentor_id=current_user.id,
    )
    substitutions = (
        Substitution.query.filter(
            Substitution.mentor_id == current_user.id,
            Substitution.mentee_id.in_(mentee_ids),
        )
        .order_by(Substitution.start_date.desc())
        .all()
    )
    return render_template(
        "mentor/substitutions.html",
        form=form,
        assigned_mentees=User.query.filter_by(
            role="mentee",
            mentor_id=current_user.id,
            is_active=True,
        ).order_by(User.full_name).all(),
        substitute_mentors=substitute_mentors,
        substitutions=substitutions,
        today=date.today(),
    )


@mentor_bp.route("/meetings", methods=["GET", "POST"])
@role_required("mentor")
def meetings():
    form = MentorMeetingForm()
    assigned_mentees = User.query.filter_by(
        role="mentee",
        mentor_id=current_user.id,
        is_active=True,
    ).order_by(User.full_name).all()
    form.mentee_ids.choices = [(mentee.id, mentee.full_name) for mentee in assigned_mentees]

    if form.validate_on_submit():
        selected_mentees = (
            assigned_mentees
            if form.audience.data == "all"
            else [mentee for mentee in assigned_mentees if mentee.id in form.mentee_ids.data]
        )
        if not selected_mentees:
            flash("Select at least one of your active mentees.", "danger")
        elif form.date.data < date.today():
            flash("Meeting date must be today or later.", "danger")
        else:
            agenda = sanitize_text(form.agenda.data, 500)
            meetings_to_create = [
                Meeting(
                    mentee_id=mentee.id,
                    mentor_id=current_user.id,
                    requested_by_id=current_user.id,
                    status="Approved",
                    date=form.date.data,
                    time=form.time.data.strip(),
                    duration=form.duration.data,
                    mode=form.mode.data,
                    agenda=agenda,
                    reason="Scheduled by mentor",
                )
                for mentee in selected_mentees
            ]
            db.session.add_all(meetings_to_create)
            db.session.commit()
            for mentee, meeting in zip(selected_mentees, meetings_to_create):
                add_notification(
                    mentee.id,
                    "meeting_scheduled",
                    f"{current_user.full_name} scheduled a meeting with you.",
                    meeting.id,
                )
            if form.audience.data == "selected" and len(meetings_to_create) == 1:
                flash("Meeting created and added to the mentee's sessions.", "success")
            elif form.audience.data == "selected":
                flash(f"Meeting created for {len(meetings_to_create)} selected mentees.", "success")
            else:
                flash(f"Meeting created for all {len(meetings_to_create)} active mentees.", "success")
            return redirect(url_for("mentor.meetings"))

    meetings = Meeting.query.filter_by(mentor_id=current_user.id).order_by(Meeting.created_at.desc()).all()
    return render_template(
        "mentor/meetings.html",
        meetings=meetings,
        form=form,
        assigned_mentees=assigned_mentees,
        min_meeting_date=date.today().isoformat(),
    )


@mentor_bp.route("/meetings/<int:meeting_id>", methods=["GET", "POST"])
@role_required("mentor")
def meeting_detail(meeting_id):
    meeting = Meeting.query.filter_by(id=meeting_id).first_or_404()
    if not can_access_mentee(current_user, meeting.mentee_id):
        abort(404)
    form = MeetingDecisionForm()
    if form.validate_on_submit():
        meeting.status = form.decision.data
        meeting.decision_reason = form.reason.data or "No reason provided"
        meeting.updated_at = datetime.utcnow()
        db.session.commit()
        add_notification(meeting.mentee_id, "meeting_update", f"Your meeting status is now {meeting.status}.", meeting.id)
        flash("Meeting updated.", "success")
        return redirect(url_for("mentor.meetings"))
    return render_template("mentor/meeting_detail.html", meeting=meeting, form=form)


@mentor_bp.route("/actions")
@role_required("mentor")
def actions():
    actions = Action.query.filter_by(created_by_id=current_user.id).order_by(Action.created_at.desc()).all()
    return render_template("mentor/actions.html", actions=actions)


@mentor_bp.route("/actions/new", methods=["GET", "POST"])
@role_required("mentor")
def create_action():
    form = ActionForm()
    assigned_mentees = User.query.filter_by(
        role="mentee",
        mentor_id=current_user.id,
        is_active=True,
    ).all()
    if form.validate_on_submit():
        assigned_by_id = {mentee.id: mentee for mentee in assigned_mentees}
        raw_recipient_ids = request.form.getlist("mentee_ids")
        if not raw_recipient_ids:
            flash("Select at least one of your active mentees.", "danger")
            return render_template("mentor/action_form.html", form=form, assigned_mentees=assigned_mentees)
        try:
            recipient_ids = [int(raw_id) for raw_id in raw_recipient_ids]
        except (TypeError, ValueError):
            flash("The selected mentees are invalid. Please select from your mentee list.", "danger")
            return render_template("mentor/action_form.html", form=form, assigned_mentees=assigned_mentees)
        if len(recipient_ids) != len(set(recipient_ids)) or any(
            recipient_id not in assigned_by_id for recipient_id in recipient_ids
        ):
            flash("You can assign actions only to your own active mentees.", "danger")
            return render_template("mentor/action_form.html", form=form, assigned_mentees=assigned_mentees)

        action = Action(
            title=form.title.data,
            description=form.description.data,
            deadline=form.deadline.data,
            created_by_id=current_user.id,
        )
        db.session.add(action)
        db.session.flush()
        for recipient_id in recipient_ids:
            mentee = assigned_by_id[recipient_id]
            db.session.add(ActionAssignment(action_id=action.id, mentee_id=mentee.id, status="Not Started"))
            db.session.add(Notification(
                user_id=mentee.id,
                type="action_assigned",
                message=f"New action assigned: {action.title}",
                related_id=action.id,
            ))
        db.session.commit()
        flash("Action created and assigned.", "success")
        return redirect(url_for("mentor.actions"))
    return render_template("mentor/action_form.html", form=form, assigned_mentees=assigned_mentees)


@mentor_bp.route("/concerns")
@role_required("mentor")
def concerns():
    mentee_ids = db.session.query(User.id).filter(
        User.role == "mentee",
        User.mentor_id == current_user.id,
    )
    substitute_mentee_ids = db.session.query(Substitution.mentee_id).filter(
        Substitution.substitute_mentor_id == current_user.id,
        Substitution.active.is_(True),
        Substitution.start_date <= date.today(),
        Substitution.end_date >= date.today(),
    )
    concerns = Concern.query.filter(
        Concern.mentee_id.in_(mentee_ids.union(substitute_mentee_ids))
    ).order_by(Concern.created_at.desc()).all()
    return render_template(
        "mentor/concerns.html",
        concerns=concerns,
        review_form=ConcernReviewForm(),
    )


@mentor_bp.route("/concerns/<int:concern_id>", methods=["POST"])
@role_required("mentor")
def update_concern(concern_id):
    concern = Concern.query.get_or_404(concern_id)
    if not user_is_mentor_for_mentee(current_user, concern.mentee_id):
        abort(403)
    form = ConcernReviewForm()
    if form.validate_on_submit():
        concern.status = form.status.data
        if form.response.data and form.response.data.strip():
            append_concern_response(concern, form.response.data, current_user.full_name, current_user.role)
        db.session.commit()
        add_notification(
            concern.mentee_id,
            "concern_update",
            f"Your concern was updated: {concern.title}",
            concern.id,
        )
        AuditLog.log(current_user.id, "concern_update", f"Updated concern {concern.id}.")
        flash("Concern update saved.", "success")
    else:
        flash("Choose a valid status and provide a reply of up to 2,000 characters.", "danger")
    return redirect(url_for("mentor.concerns"))


@mentor_bp.route("/messages")
@role_required("mentor")
def messages():
    return redirect(url_for("messaging.inbox"))
