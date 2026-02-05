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
    transports_legacy = db.relationship("TransportLegacy", backref="practice", lazy=True, cascade="all, delete-orphan")


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


class TransportLegacy(db.Model):
    """旧Transport（練習紐付け用）- 後方互換のため残す"""
    __tablename__ = "transport_legacy"
    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.Integer, db.ForeignKey("practice.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    board_id = db.Column(db.Integer, db.ForeignKey("board.id"), nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # 'to' or 'from'
    user = db.relationship("User")
    board = db.relationship("Board")


# =============================================================================
# 運搬管理システム（新規）
# =============================================================================

class Location(db.Model):
    """拠点マスタ"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_base = db.Column(db.Boolean, nullable=False, default=True)  # True=拠点, False=中継地点
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(JST))
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_by = db.relationship("User", foreign_keys=[created_by_id])


class Transport(db.Model):
    """運搬"""
    __tablename__ = "transport"
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey("board.id"), nullable=False)
    
    # ステータス: scheduled, in_progress, at_waypoint, awaiting_handover, 
    #            destination_pending, completed, cancelled
    status = db.Column(db.String(30), nullable=False, default="scheduled")
    
    # 場所
    origin = db.Column(db.String(100), nullable=False)  # 出発地
    destination = db.Column(db.String(100), nullable=True)  # 目的地（NULL=未定）
    current_location = db.Column(db.String(100), nullable=True)  # 現在地
    
    # 理由: 1=チーム練, 2=他拠点不足, 3=大会等, 4=その他
    reason_type = db.Column(db.Integer, nullable=False, default=4)
    reason_detail = db.Column(db.Text, nullable=True)  # その他の場合の詳細
    
    # 出発予定
    departure_date = db.Column(db.Date, nullable=True)  # NULL=未定
    # before_1, between_1_2, between_2_3, after_3, other, pending
    departure_timing = db.Column(db.String(20), nullable=True, default="pending")
    
    # 到着予定
    arrival_date = db.Column(db.Date, nullable=True)  # NULL=未定
    arrival_timing = db.Column(db.String(20), nullable=True, default="pending")
    
    # 実績
    actual_departure = db.Column(db.DateTime, nullable=True)
    actual_arrival = db.Column(db.DateTime, nullable=True)
    
    # メタ情報
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(JST))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(JST), onupdate=lambda: datetime.now(JST))
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    # キャンセル
    cancelled_reason = db.Column(db.Text, nullable=True)
    
    # 目的地変更時の引継ぎ元
    linked_transport_id = db.Column(db.Integer, db.ForeignKey("transport.id"), nullable=True)
    
    # リレーションシップ
    board = db.relationship("Board", backref=db.backref("transports", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_id], backref=db.backref("created_transports", lazy=True))
    linked_transport = db.relationship("Transport", remote_side=[id], backref=db.backref("derived_transports", lazy=True))
    carriers = db.relationship("TransportCarrier", backref="transport", lazy=True, cascade="all, delete-orphan", order_by="TransportCarrier.sequence")
    waypoints = db.relationship("TransportWaypoint", backref="transport", lazy=True, cascade="all, delete-orphan", order_by="TransportWaypoint.sequence")
    logs = db.relationship("TransportLog", backref="transport", lazy=True, cascade="all, delete-orphan", order_by="TransportLog.operated_at.desc()")
    
    @property
    def is_destination_pending(self):
        return self.destination is None or self.status == "destination_pending"
    
    @property
    def days_pending(self):
        """目的地未定の日数"""
        if not self.is_destination_pending:
            return 0
        return (datetime.now(JST).date() - self.created_at.date()).days
    
    def get_reason_display(self):
        """理由の表示文字列"""
        reasons = {
            1: "チーム練のため",
            2: "他拠点のボードが足りないため",
            3: "大会等に持ち出すため",
            4: "その他"
        }
        base = reasons.get(self.reason_type, "その他")
        if self.reason_type == 4 and self.reason_detail:
            return f"{base}（{self.reason_detail}）"
        return base
    
    def get_timing_display(self, timing):
        """タイミングの表示文字列"""
        timings = {
            "before_1": "1部練前",
            "between_1_2": "1部練後/2部練前",
            "between_2_3": "2部練後/3部練前",
            "after_3": "3部練後",
            "other": "練習外",
            "pending": "未定"
        }
        return timings.get(timing, "未定")
    
    def get_status_display(self):
        """ステータスの表示文字列"""
        statuses = {
            "scheduled": "予定",
            "in_progress": "進行中",
            "at_waypoint": "中継中",
            "awaiting_handover": "引継ぎ待ち",
            "destination_pending": "目的地未定",
            "completed": "完了",
            "cancelled": "キャンセル"
        }
        return statuses.get(self.status, self.status)


class TransportCarrier(db.Model):
    """運搬者"""
    id = db.Column(db.Integer, primary_key=True)
    transport_id = db.Column(db.Integer, db.ForeignKey("transport.id"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False, default=1)  # 順番（リレー運搬用）
    
    # 登録ユーザーの場合
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    # 非登録ユーザーの場合
    unregistered_name = db.Column(db.String(100), nullable=True)
    # 非登録ユーザーを登録したユーザー
    registered_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    
    # ステータス: pending, active, completed
    status = db.Column(db.String(20), nullable=False, default="pending")
    
    # 引継ぎ確認
    handover_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    handover_confirmed_at = db.Column(db.DateTime, nullable=True)
    handover_confirmed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    
    # リレーションシップ
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("carrier_assignments", lazy=True))
    registered_by = db.relationship("User", foreign_keys=[registered_by_id])
    handover_confirmed_by = db.relationship("User", foreign_keys=[handover_confirmed_by_id])
    
    @property
    def carrier_name(self):
        """運搬者名を取得"""
        if self.user:
            return self.user.username
        return self.unregistered_name or "不明"
    
    @property
    def is_unregistered(self):
        """非登録ユーザーかどうか"""
        return self.user_id is None


class TransportWaypoint(db.Model):
    """中継地点"""
    id = db.Column(db.Integer, primary_key=True)
    transport_id = db.Column(db.Integer, db.ForeignKey("transport.id"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)  # 順番
    location = db.Column(db.String(100), nullable=False)  # 中継地点名
    arrived_at = db.Column(db.DateTime, nullable=True)  # 到着日時
    departed_at = db.Column(db.DateTime, nullable=True)  # 出発日時


class TransportLog(db.Model):
    """操作ログ"""
    id = db.Column(db.Integer, primary_key=True)
    transport_id = db.Column(db.Integer, db.ForeignKey("transport.id"), nullable=False)
    
    # アクション: created, status_changed, destination_set, date_changed,
    #            carrier_changed, handover_confirmed, cancelled, etc.
    action = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.Text, nullable=True)  # JSON
    new_value = db.Column(db.Text, nullable=True)  # JSON
    reason = db.Column(db.Text, nullable=True)  # 変更理由
    
    operated_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    operated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(JST))
    
    # リレーションシップ
    operated_by = db.relationship("User", backref=db.backref("transport_logs", lazy=True))
