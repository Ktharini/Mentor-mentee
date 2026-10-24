from datetime import date

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, HiddenField, IntegerField, PasswordField, SelectField, SelectMultipleField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, ValidationError


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField("Password", validators=[DataRequired()])
    role = HiddenField(validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log in")


class PasswordResetRequestForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField("Registered email", validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField(
        "Role",
        choices=[("admin", "Admin"), ("mentor", "Mentor"), ("mentee", "Mentee")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    token = HiddenField(validators=[DataRequired()])
    password = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")],
    )
    submit = SubmitField("Reset password")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    password = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")],
    )
    submit = SubmitField("Update password")


class UserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=50)])
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=120)])
    role = SelectField("Role", choices=[("mentor", "Mentor"), ("mentee", "Mentee")], validators=[DataRequired()])
    password = PasswordField("Temporary password", validators=[Optional(), Length(min=8)])
    submit = SubmitField("Save")


class MeetingRequestForm(FlaskForm):
    date = DateField("Date", validators=[DataRequired()], default=date.today)
    time = StringField("Time", validators=[DataRequired(), Length(min=3, max=10)])
    duration = IntegerField(
        "Duration (minutes)",
        validators=[DataRequired(), NumberRange(min=15, max=240)],
        default=60,
    )
    mode = SelectField("Mode", choices=[("online", "Online"), ("offline", "Offline")], default="online")
    agenda = TextAreaField("Agenda", validators=[DataRequired(), Length(min=3, max=500)])
    submit = SubmitField("Request meeting")

    def validate_date(self, field):
        if field.data and field.data < date.today():
            raise ValidationError("Choose today or a future date.")


class MentorMeetingForm(FlaskForm):
    audience = SelectField(
        "Arrange with",
        choices=[("all", "All my active mentees"), ("selected", "Selected mentees")],
        validators=[DataRequired()],
        default="all",
    )
    mentee_ids = SelectMultipleField("Select mentees", coerce=int)
    date = DateField("Date", validators=[DataRequired()], default=date.today)
    time = StringField("Time", validators=[DataRequired(), Length(min=3, max=10)])
    duration = IntegerField("Duration (minutes)", validators=[DataRequired(), NumberRange(min=15, max=240)], default=60)
    mode = SelectField("Mode", choices=[("online", "Online"), ("offline", "In person")], default="online")
    agenda = TextAreaField("Agenda", validators=[DataRequired(), Length(min=3, max=500)])
    submit = SubmitField("Create meeting")


class MeetingDecisionForm(FlaskForm):
    decision = SelectField("Decision", choices=[("Approved", "Approve"), ("Rejected", "Reject"), ("Rescheduled", "Reschedule")])
    reason = TextAreaField("Reason / note", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Submit")


class ConcernForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=200)])
    category = SelectField("Category", choices=[("academic", "Academic"), ("personal", "Personal"), ("project", "Project"), ("other", "Other")], default="academic")
    priority = SelectField("Priority", choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")], default="medium")
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10, max=2000)])
    submit = SubmitField("Raise concern")


class ConcernReplyForm(FlaskForm):
    response = TextAreaField("Reply", validators=[DataRequired(), Length(min=1, max=2000)])
    submit = SubmitField("Send reply")


class ConcernReviewForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[("Open", "Open"), ("In Progress", "In progress"), ("Resolved", "Resolved")],
        validators=[DataRequired()],
    )
    response = TextAreaField("Reply", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Save update")


class ActionProgressForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[("Not Started", "Not started"), ("In Progress", "In progress"), ("Completed", "Completed")],
        validators=[DataRequired()],
    )
    progress = IntegerField("Progress", validators=[DataRequired(), NumberRange(min=0, max=100)], default=0)
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Update task")


class AchievementForm(FlaskForm):
    title = StringField("Achievement title", validators=[DataRequired(), Length(min=3, max=120)])
    submit = SubmitField("Upload achievement")


class ActionForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=200)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10, max=2000)])
    deadline = DateField("Deadline", validators=[DataRequired()], default=date.today)
    submit = SubmitField("Create action")


class MessageForm(FlaskForm):
    content = TextAreaField("Message", validators=[DataRequired(), Length(min=1, max=500)])
    emergency = BooleanField("Mark as emergency")
    submit = SubmitField("Send")


class AllocationForm(FlaskForm):
    mentor_id = SelectField("Mentor", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Assign mentor")


class SubstitutionForm(FlaskForm):
    mentee_id = SelectField("Mentee", coerce=int, validators=[DataRequired()])
    substitute_mentor_id = SelectField("Substitute mentor", coerce=int, validators=[DataRequired()])
    reason = StringField("Reason", validators=[DataRequired(), Length(min=3, max=255)])
    start_date = DateField("Start date", validators=[DataRequired()], default=date.today)
    end_date = DateField("End date", validators=[DataRequired()], default=date.today)
    submit = SubmitField("Save substitution")


class MentorSubstitutionForm(FlaskForm):
    mentee_id = SelectField("Mentee", coerce=int, validators=[Optional()])
    substitute_mentor_id = SelectField("Substitute mentor", coerce=int, validators=[DataRequired()])
    reason = StringField("Reason", validators=[DataRequired(), Length(min=3, max=255)])
    start_date = DateField("Start date", validators=[DataRequired()], default=date.today)
    end_date = DateField("End date", validators=[DataRequired()], default=date.today)
    active = BooleanField("Active")
    submit = SubmitField("Save substitution")
