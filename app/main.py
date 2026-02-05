"""
Main routes blueprint (index, dashboard).
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import Attendance, Practice, Announcement, Transport
from app.extensions import db
from app.utils import JST

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
    
    # 3日以上目的地未定の運搬を取得
    three_days_ago = datetime.now(JST) - timedelta(days=3)
    pending_transports = Transport.query.filter(
        db.or_(
            Transport.destination.is_(None),
            Transport.status == "destination_pending"
        )
    ).filter(
        Transport.status != "cancelled",
        Transport.created_at <= three_days_ago
    ).order_by(Transport.created_at.asc()).all()
    
    return render_template(
        "dashboard.html",
        unanswered_attendances=unanswered_attendances,
        announcements=announcements,
        pending_transports=pending_transports,
    )
