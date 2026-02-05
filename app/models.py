"""
Database models for the application.
"""
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db
from app.utils import JST


# =============================================================================
# Association Table for Session Members
# =============================================================================

session_members = db.Table(
    "session_members",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("session_id", db.Integer, db.ForeignKey("practice_session.id"), primary_key=True),
)


# =============================================================================
# Models
# =============================================================================

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    users = db.relationship("User", backref="team", lazy=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="member")
    generation = db.Column(db.String(20), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    transport_count = db.Column(db.Integer, nullable=False, default=0)

    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)


class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    serial_number = db.Column(db.String(100), unique=True, nullable=True)
    location = db.Column(db.String(100), nullable=False)
    user = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50), nullable=False)  # 表示依存のため文字列のまま
    notes = db.Column(db.Text, nullable=True)
    histories = db.relationship("UpdateHistory", backref="board", lazy=True, cascade="all, delete-orphan")


class UpdateHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey("board.id"), nullable=False)
    previous_location = db.Column(db.String(100))
    new_location = db.Column(db.String(100), nullable=False)
    updated_by = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50), nullable=False)  # 表示依存のため文字列のまま


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(JST))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", backref=db.backref("announcements", lazy=True))


class Practice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, default="チーム練習")
    practice_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    target_team = db.relationship("Team")
    sessions = db.relationship("PracticeSession", backref="practice", lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship("Attendance", backref="practice", lazy=True, cascade="all, delete-orphan")
    transports = db.relationship("Transport", backref="practice", lazy=True, cascade="all, delete-orphan")


class PracticeSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.Integer, db.ForeignKey("practice.id"), nullable=False)
    session_number = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    members = db.relationship(
        "User",
        secondary=session_members,
        backref=db.backref("sessions_attending", lazy="dynamic")
    )


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.Integer, db.ForeignKey("practice.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User")
    status = db.Column(db.String(20), nullable=False, default="unanswered")
    reason = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)


class Transport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.Integer, db.ForeignKey("practice.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    board_id = db.Column(db.Integer, db.ForeignKey("board.id"), nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # 'to' or 'from'
    user = db.relationship("User")
    board = db.relationship("Board")
