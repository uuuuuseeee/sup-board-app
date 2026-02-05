"""
Main routes blueprint (index, dashboard).
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import Attendance, Practice, Announcement

bp = Blueprint('main', __name__)


@bp.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard")
@login_required
def dashboard():
    unanswered_attendances = (
        Attendance.query.filter_by(user_id=current_user.id, status="unanswered")
        .join(Practice)
        .order_by(Practice.practice_date)
        .all()
    )
    announcements = Announcement.query.order_by(Announcement.timestamp.desc()).all()
    return render_template(
        "dashboard.html",
        unanswered_attendances=unanswered_attendances,
        announcements=announcements,
    )
