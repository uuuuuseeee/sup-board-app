"""
Transport management blueprint.
運搬管理機能
"""
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    Transport, TransportCarrier, TransportWaypoint, TransportLog,
    Location, Board, User
)
from app.utils import JST
from app.decorators import admin_required

bp = Blueprint('transports', __name__, url_prefix='/transports')


# =============================================================================
# 定数
# =============================================================================

REASON_TYPES = {
    1: "チーム練のため",
    2: "他拠点のボードが足りないため",
    3: "大会等に持ち出すため",
    4: "その他"
}

TIMING_OPTIONS = [
    ("before_1", "1部練前"),
    ("between_1_2", "1部練後/2部練前"),
    ("between_2_3", "2部練後/3部練前"),
    ("after_3", "3部練後"),
    ("other", "練習外"),
    ("pending", "未定")
]

STATUS_OPTIONS = {
    "scheduled": "予定",
    "in_progress": "進行中",
    "at_waypoint": "中継中",
    "awaiting_handover": "引継ぎ待ち",
    "destination_pending": "目的地未定",
    "completed": "完了",
    "cancelled": "キャンセル"
}


# =============================================================================
# ヘルパー関数
# =============================================================================

def get_locations_for_select():
    """場所選択用のリストを取得（拠点が上位、中継地点が下位）"""
    bases = Location.query.filter_by(is_base=True).order_by(Location.display_order).all()
    waypoints = Location.query.filter_by(is_base=False).order_by(Location.name).all()
    return bases, waypoints


def get_board_last_destination(board_id):
    """ボードの最新運搬目的地を取得"""
    last_transport = Transport.query.filter_by(
        board_id=board_id
    ).filter(
        Transport.status == "completed"
    ).order_by(Transport.actual_arrival.desc()).first()
    
    if last_transport and last_transport.destination:
        return last_transport.destination
    
    # 運搬履歴がなければボードの現在地を返す
    board = Board.query.get(board_id)
    return board.location if board else None


def create_transport_log(transport_id, action, operated_by_id, old_value=None, new_value=None, reason=None):
    """運搬ログを作成"""
    log = TransportLog(
        transport_id=transport_id,
        action=action,
        old_value=json.dumps(old_value, ensure_ascii=False) if old_value else None,
        new_value=json.dumps(new_value, ensure_ascii=False) if new_value else None,
        reason=reason,
        operated_by_id=operated_by_id
    )
    db.session.add(log)
    return log


def update_board_location(board, new_location, updated_by):
    """ボードの現在地を更新"""
    board.location = new_location
    board.user = updated_by
    board.updated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M")


# =============================================================================
# 運搬一覧
# =============================================================================

@bp.route("/")
@login_required
def index():
    """運搬一覧"""
    status_filter = request.args.get("status", "active")
    
    query = Transport.query
    
    if status_filter == "active":
        # 進行中の運搬（予定、進行中、中継中、引継ぎ待ち、目的地未定）
        query = query.filter(Transport.status.in_([
            "scheduled", "in_progress", "at_waypoint", 
            "awaiting_handover", "destination_pending"
        ]))
    elif status_filter == "completed":
        query = query.filter_by(status="completed")
    elif status_filter == "cancelled":
        query = query.filter_by(status="cancelled")
    # else: all
    
    transports = query.order_by(Transport.departure_date.asc().nullslast(), Transport.created_at.desc()).all()
    
    return render_template(
        "transports/index.html",
        transports=transports,
        status_filter=status_filter,
        STATUS_OPTIONS=STATUS_OPTIONS
    )


@bp.route("/pending")
@login_required
def pending():
    """目的地未定一覧"""
    transports = Transport.query.filter(
        db.or_(
            Transport.destination.is_(None),
            Transport.status == "destination_pending"
        )
    ).filter(
        Transport.status != "cancelled"
    ).order_by(Transport.created_at.asc()).all()
    
    return render_template(
        "transports/pending.html",
        transports=transports
    )


# =============================================================================
# 運搬登録
# =============================================================================

@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    """運搬登録"""
    if request.method == "POST":
        return _create_transport()
    
    # GET: フォーム表示
    boards = Board.query.order_by(Board.name).all()
    users = User.query.filter(User.role != "guest").order_by(User.username).all()
    bases, waypoints = get_locations_for_select()
    
    # ボードが指定されている場合、デフォルトの出発地を設定
    board_id = request.args.get("board_id", type=int)
    default_origin = None
    if board_id:
        default_origin = get_board_last_destination(board_id)
    
    return render_template(
        "transports/new.html",
        boards=boards,
        users=users,
        bases=bases,
        waypoints=waypoints,
        default_origin=default_origin,
        selected_board_id=board_id,
        REASON_TYPES=REASON_TYPES,
        TIMING_OPTIONS=TIMING_OPTIONS
    )


def _create_transport():
    """運搬を作成"""
    try:
        # 基本情報
        board_id = request.form.get("board_id", type=int)
        if not board_id:
            flash("ボードを選択してください。", "error")
            return redirect(url_for("transports.new"))
        
        # 出発地
        origin_type = request.form.get("origin_type")
        if origin_type == "base":
            origin = request.form.get("origin_base")
        else:
            origin = request.form.get("origin_other")
        
        if not origin:
            flash("出発地を入力してください。", "error")
            return redirect(url_for("transports.new"))
        
        # 目的地
        destination_pending = request.form.get("destination_pending") == "on"
        if destination_pending:
            destination = None
        else:
            destination_type = request.form.get("destination_type")
            if destination_type == "base":
                destination = request.form.get("destination_base")
            else:
                destination = request.form.get("destination_other")
        
        # 日程
        departure_date_str = request.form.get("departure_date")
        if not departure_date_str:
            flash("出発予定日を入力してください。", "error")
            return redirect(url_for("transports.new"))
        
        departure_date = datetime.strptime(departure_date_str, "%Y-%m-%d").date()
        # 1ヶ月以上先の警告チェック
        if departure_date > datetime.now(JST).date() + timedelta(days=30):
            flash("出発予定日が1ヶ月以上先です。予定が変わる可能性があります。", "warning")
        
        departure_timing = request.form.get("departure_timing", "pending")
        
        # 到着日（未定可能）
        arrival_pending = request.form.get("arrival_pending") == "on"
        arrival_date = None
        arrival_timing = "pending"
        if not arrival_pending and not destination_pending:
            arrival_date_str = request.form.get("arrival_date")
            if arrival_date_str:
                arrival_date = datetime.strptime(arrival_date_str, "%Y-%m-%d").date()
            arrival_timing = request.form.get("arrival_timing", "pending")
        
        # 理由
        reason_type = request.form.get("reason_type", type=int) or 4
        reason_detail = request.form.get("reason_detail") if reason_type == 4 else None
        
        # ステータス決定
        if destination_pending or destination is None:
            status = "destination_pending"
        else:
            status = "scheduled"
        
        # 運搬作成
        transport = Transport(
            board_id=board_id,
            status=status,
            origin=origin,
            destination=destination,
            current_location=origin,
            reason_type=reason_type,
            reason_detail=reason_detail,
            departure_date=departure_date,
            departure_timing=departure_timing,
            arrival_date=arrival_date,
            arrival_timing=arrival_timing,
            created_by_id=current_user.id
        )
        db.session.add(transport)
        db.session.flush()  # IDを取得
        
        # 運搬者
        carrier_type = request.form.get("carrier_type")
        if carrier_type == "registered":
            carrier_user_id = request.form.get("carrier_user_id", type=int)
            carrier = TransportCarrier(
                transport_id=transport.id,
                sequence=1,
                user_id=carrier_user_id,
                status="pending"
            )
        else:
            unregistered_name = request.form.get("carrier_unregistered_name")
            if not unregistered_name:
                flash("非登録ユーザーの名前を入力してください。", "error")
                db.session.rollback()
                return redirect(url_for("transports.new"))
            carrier = TransportCarrier(
                transport_id=transport.id,
                sequence=1,
                unregistered_name=unregistered_name,
                registered_by_id=current_user.id,
                status="pending"
            )
        db.session.add(carrier)
        
        # 追加の運搬者（リレー運搬）
        additional_carriers = request.form.getlist("additional_carrier_user_id")
        for i, user_id in enumerate(additional_carriers, start=2):
            if user_id:
                additional_carrier = TransportCarrier(
                    transport_id=transport.id,
                    sequence=i,
                    user_id=int(user_id),
                    status="pending"
                )
                db.session.add(additional_carrier)
        
        # 中継地点
        waypoint_locations = request.form.getlist("waypoint_location")
        for i, loc in enumerate(waypoint_locations, start=1):
            if loc:
                waypoint = TransportWaypoint(
                    transport_id=transport.id,
                    sequence=i,
                    location=loc
                )
                db.session.add(waypoint)
                
                # 中継地点をLocationに追加（存在しなければ）
                if not Location.query.filter_by(name=loc).first():
                    new_location = Location(
                        name=loc,
                        is_base=False,
                        created_by_id=current_user.id
                    )
                    db.session.add(new_location)
        
        # ログ作成
        create_transport_log(
            transport.id,
            "created",
            current_user.id,
            new_value={
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date_str,
                "departure_timing": departure_timing
            }
        )
        
        db.session.commit()
        flash("運搬を登録しました。", "success")
        return redirect(url_for("transports.detail", transport_id=transport.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"エラーが発生しました: {str(e)}", "error")
        return redirect(url_for("transports.new"))


# =============================================================================
# 運搬詳細
# =============================================================================

@bp.route("/<int:transport_id>")
@login_required
def detail(transport_id):
    """運搬詳細"""
    transport = Transport.query.get_or_404(transport_id)
    
    return render_template(
        "transports/detail.html",
        transport=transport,
        STATUS_OPTIONS=STATUS_OPTIONS,
        TIMING_OPTIONS=TIMING_OPTIONS
    )


# =============================================================================
# ステータス変更
# =============================================================================

@bp.route("/<int:transport_id>/start", methods=["POST"])
@login_required
def start(transport_id):
    """運搬開始（出発）"""
    transport = Transport.query.get_or_404(transport_id)
    
    if transport.status not in ["scheduled", "destination_pending"]:
        flash("この運搬は開始できません。", "error")
        return redirect(url_for("transports.detail", transport_id=transport_id))
    
    old_status = transport.status
    transport.status = "in_progress" if transport.destination else "destination_pending"
    transport.actual_departure = datetime.now(JST)
    
    # 最初の運搬者をactiveに
    first_carrier = TransportCarrier.query.filter_by(
        transport_id=transport_id, sequence=1
    ).first()
    if first_carrier:
        first_carrier.status = "active"
    
    create_transport_log(
        transport_id, "started", current_user.id,
        old_value={"status": old_status},
        new_value={"status": transport.status}
    )
    
    db.session.commit()
    flash("運搬を開始しました。", "success")
    return redirect(url_for("transports.detail", transport_id=transport_id))


@bp.route("/<int:transport_id>/arrive-waypoint", methods=["POST"])
@login_required
def arrive_waypoint(transport_id):
    """中継地点に到着"""
    transport = Transport.query.get_or_404(transport_id)
    waypoint_id = request.form.get("waypoint_id", type=int)
    
    waypoint = TransportWaypoint.query.get_or_404(waypoint_id)
    waypoint.arrived_at = datetime.now(JST)
    
    transport.status = "at_waypoint"
    transport.current_location = waypoint.location
    
    # ボードの現在地を更新
    update_board_location(transport.board, waypoint.location, current_user.username)
    
    create_transport_log(
        transport_id, "arrived_waypoint", current_user.id,
        new_value={"waypoint": waypoint.location}
    )
    
    db.session.commit()
    flash(f"{waypoint.location}に到着しました。", "success")
    return redirect(url_for("transports.detail", transport_id=transport_id))


@bp.route("/<int:transport_id>/depart-waypoint", methods=["POST"])
@login_required
def depart_waypoint(transport_id):
    """中継地点から出発"""
    transport = Transport.query.get_or_404(transport_id)
    waypoint_id = request.form.get("waypoint_id", type=int)
    
    waypoint = TransportWaypoint.query.get_or_404(waypoint_id)
    waypoint.departed_at = datetime.now(JST)
    
    transport.status = "in_progress"
    
    create_transport_log(
        transport_id, "departed_waypoint", current_user.id,
        new_value={"waypoint": waypoint.location}
    )
    
    db.session.commit()
    flash(f"{waypoint.location}から出発しました。", "success")
    return redirect(url_for("transports.detail", transport_id=transport_id))


@bp.route("/<int:transport_id>/complete", methods=["POST"])
@login_required
def complete(transport_id):
    """運搬完了"""
    transport = Transport.query.get_or_404(transport_id)
    
    if not transport.destination:
        flash("目的地が未定のため完了できません。先に目的地を設定してください。", "error")
        return redirect(url_for("transports.detail", transport_id=transport_id))
    
    old_status = transport.status
    transport.status = "completed"
    transport.actual_arrival = datetime.now(JST)
    transport.current_location = transport.destination
    
    # 最後の運搬者をcompletedに
    last_carrier = TransportCarrier.query.filter_by(
        transport_id=transport_id
    ).order_by(TransportCarrier.sequence.desc()).first()
    if last_carrier:
        last_carrier.status = "completed"
    
    # ボードの現在地を更新
    update_board_location(transport.board, transport.destination, current_user.username)
    
    create_transport_log(
        transport_id, "completed", current_user.id,
        old_value={"status": old_status},
        new_value={"status": "completed", "location": transport.destination}
    )
    
    db.session.commit()
    flash("運搬が完了しました。", "success")
    return redirect(url_for("transports.detail", transport_id=transport_id))


# =============================================================================
# 引継ぎ
# =============================================================================

@bp.route("/<int:transport_id>/handover", methods=["POST"])
@login_required
def handover(transport_id):
    """引継ぎ確認"""
    transport = Transport.query.get_or_404(transport_id)
    carrier_id = request.form.get("carrier_id", type=int)
    
    # 現在のアクティブな運搬者を完了に
    current_carrier = TransportCarrier.query.filter_by(
        transport_id=transport_id, status="active"
    ).first()
    
    if current_carrier:
        current_carrier.status = "completed"
        current_carrier.handover_confirmed = True
        current_carrier.handover_confirmed_at = datetime.now(JST)
        current_carrier.handover_confirmed_by_id = current_user.id
    
    # 次の運搬者をアクティブに
    next_carrier = TransportCarrier.query.filter_by(
        transport_id=transport_id, sequence=current_carrier.sequence + 1 if current_carrier else 1
    ).first()
    
    if next_carrier:
        next_carrier.status = "active"
        transport.status = "in_progress"
        flash(f"{next_carrier.carrier_name}に引き継ぎました。", "success")
    else:
        transport.status = "awaiting_handover"
        flash("引継ぎを確認しました。", "success")
    
    create_transport_log(
        transport_id, "handover_confirmed", current_user.id,
        new_value={
            "from": current_carrier.carrier_name if current_carrier else None,
            "to": next_carrier.carrier_name if next_carrier else None
        }
    )
    
    db.session.commit()
    return redirect(url_for("transports.detail", transport_id=transport_id))


@bp.route("/<int:transport_id>/change-carrier", methods=["POST"])
@login_required
def change_carrier(transport_id):
    """引継ぎ者変更"""
    transport = Transport.query.get_or_404(transport_id)
    
    carrier_type = request.form.get("new_carrier_type")
    
    # 現在待機中の次の運搬者を取得
    current_carrier = TransportCarrier.query.filter_by(
        transport_id=transport_id, status="active"
    ).first()
    
    next_sequence = current_carrier.sequence + 1 if current_carrier else 1
    
    # 既存の次の運搬者があれば更新、なければ作成
    next_carrier = TransportCarrier.query.filter_by(
        transport_id=transport_id, sequence=next_sequence
    ).first()
    
    if carrier_type == "registered":
        new_user_id = request.form.get("new_carrier_user_id", type=int)
        if next_carrier:
            old_name = next_carrier.carrier_name
            next_carrier.user_id = new_user_id
            next_carrier.unregistered_name = None
            next_carrier.registered_by_id = None
        else:
            next_carrier = TransportCarrier(
                transport_id=transport_id,
                sequence=next_sequence,
                user_id=new_user_id,
                status="pending"
            )
            db.session.add(next_carrier)
            old_name = None
    else:
        new_name = request.form.get("new_carrier_name")
        if next_carrier:
            old_name = next_carrier.carrier_name
            next_carrier.user_id = None
            next_carrier.unregistered_name = new_name
            next_carrier.registered_by_id = current_user.id
        else:
            next_carrier = TransportCarrier(
                transport_id=transport_id,
                sequence=next_sequence,
                unregistered_name=new_name,
                registered_by_id=current_user.id,
                status="pending"
            )
            db.session.add(next_carrier)
            old_name = None
    
    create_transport_log(
        transport_id, "carrier_changed", current_user.id,
        old_value={"carrier": old_name},
        new_value={"carrier": next_carrier.carrier_name},
        reason=request.form.get("change_reason")
    )
    
    db.session.commit()
    flash("引継ぎ者を変更しました。", "success")
    return redirect(url_for("transports.detail", transport_id=transport_id))


# =============================================================================
# 目的地・日程変更
# =============================================================================

@bp.route("/<int:transport_id>/set-destination", methods=["POST"])
@login_required
def set_destination(transport_id):
    """目的地を確定"""
    transport = Transport.query.get_or_404(transport_id)
    
    destination_type = request.form.get("destination_type")
    if destination_type == "base":
        destination = request.form.get("destination_base")
    else:
        destination = request.form.get("destination_other")
    
    if not destination:
        flash("目的地を入力してください。", "error")
        return redirect(url_for("transports.detail", transport_id=transport_id))
    
    old_destination = transport.destination
    transport.destination = destination
    
    # 到着予定日
    arrival_date_str = request.form.get("arrival_date")
    if arrival_date_str:
        transport.arrival_date = datetime.strptime(arrival_date_str, "%Y-%m-%d").date()
    
    transport.arrival_timing = request.form.get("arrival_timing", "pending")
    
    # ステータス更新
    if transport.status == "destination_pending":
        transport.status = "in_progress" if transport.actual_departure else "scheduled"
    
    create_transport_log(
        transport_id, "destination_set", current_user.id,
        old_value={"destination": old_destination},
        new_value={"destination": destination}
    )
    
    db.session.commit()
    flash("目的地を設定しました。", "success")
    return redirect(url_for("transports.detail", transport_id=transport_id))


@bp.route("/<int:transport_id>/change-date", methods=["POST"])
@login_required
def change_date(transport_id):
    """日程変更"""
    transport = Transport.query.get_or_404(transport_id)
    
    old_departure = transport.departure_date.isoformat() if transport.departure_date else None
    old_arrival = transport.arrival_date.isoformat() if transport.arrival_date else None
    
    departure_date_str = request.form.get("departure_date")
    if departure_date_str:
        transport.departure_date = datetime.strptime(departure_date_str, "%Y-%m-%d").date()
    
    transport.departure_timing = request.form.get("departure_timing", transport.departure_timing)
    
    arrival_date_str = request.form.get("arrival_date")
    if arrival_date_str:
        transport.arrival_date = datetime.strptime(arrival_date_str, "%Y-%m-%d").date()
    
    transport.arrival_timing = request.form.get("arrival_timing", transport.arrival_timing)
    
    reason = request.form.get("change_reason")
    
    create_transport_log(
        transport_id, "date_changed", current_user.id,
        old_value={"departure_date": old_departure, "arrival_date": old_arrival},
        new_value={
            "departure_date": departure_date_str,
            "arrival_date": arrival_date_str
        },
        reason=reason
    )
    
    db.session.commit()
    flash("日程を変更しました。", "success")
    return redirect(url_for("transports.detail", transport_id=transport_id))


# =============================================================================
# キャンセル
# =============================================================================

@bp.route("/<int:transport_id>/cancel", methods=["POST"])
@login_required
def cancel(transport_id):
    """運搬キャンセル"""
    transport = Transport.query.get_or_404(transport_id)
    
    if transport.status == "completed":
        flash("完了済みの運搬はキャンセルできません。", "error")
        return redirect(url_for("transports.detail", transport_id=transport_id))
    
    old_status = transport.status
    transport.status = "cancelled"
    transport.cancelled_reason = request.form.get("cancel_reason")
    
    create_transport_log(
        transport_id, "cancelled", current_user.id,
        old_value={"status": old_status},
        new_value={"status": "cancelled"},
        reason=transport.cancelled_reason
    )
    
    db.session.commit()
    flash("運搬をキャンセルしました。新しい運搬予定の登録をお勧めします。", "warning")
    return redirect(url_for("transports.detail", transport_id=transport_id))


# =============================================================================
# 目的地変更（新規運搬作成）
# =============================================================================

@bp.route("/<int:transport_id>/change-destination", methods=["POST"])
@login_required
def change_destination(transport_id):
    """目的地変更（元をキャンセルして新規作成）"""
    old_transport = Transport.query.get_or_404(transport_id)
    
    # 元の運搬をキャンセル
    old_transport.status = "cancelled"
    old_transport.cancelled_reason = "目的地変更のためキャンセル"
    
    # 新しい目的地
    destination_type = request.form.get("destination_type")
    if destination_type == "base":
        new_destination = request.form.get("destination_base")
    else:
        new_destination = request.form.get("destination_other")
    
    # 新規運搬作成（持ち出し日を引き継ぎ）
    new_transport = Transport(
        board_id=old_transport.board_id,
        status="scheduled" if new_destination else "destination_pending",
        origin=old_transport.current_location or old_transport.origin,
        destination=new_destination,
        current_location=old_transport.current_location,
        reason_type=old_transport.reason_type,
        reason_detail=old_transport.reason_detail,
        departure_date=old_transport.departure_date,  # 引き継ぎ
        departure_timing=old_transport.departure_timing,
        arrival_date=None,
        arrival_timing="pending",
        created_by_id=current_user.id,
        actual_departure=old_transport.actual_departure,  # 引き継ぎ
        linked_transport_id=old_transport.id
    )
    db.session.add(new_transport)
    db.session.flush()
    
    # 運搬者を引き継ぎ（現在アクティブな人以降）
    active_carriers = TransportCarrier.query.filter_by(
        transport_id=transport_id
    ).filter(
        TransportCarrier.status.in_(["active", "pending"])
    ).order_by(TransportCarrier.sequence).all()
    
    for i, carrier in enumerate(active_carriers, start=1):
        new_carrier = TransportCarrier(
            transport_id=new_transport.id,
            sequence=i,
            user_id=carrier.user_id,
            unregistered_name=carrier.unregistered_name,
            registered_by_id=carrier.registered_by_id,
            status=carrier.status
        )
        db.session.add(new_carrier)
    
    create_transport_log(
        old_transport.id, "destination_changed", current_user.id,
        old_value={"destination": old_transport.destination},
        new_value={"new_transport_id": new_transport.id, "destination": new_destination},
        reason=request.form.get("change_reason")
    )
    
    create_transport_log(
        new_transport.id, "created_from_change", current_user.id,
        new_value={"linked_from": old_transport.id}
    )
    
    db.session.commit()
    flash("目的地を変更しました。新しい運搬として登録されました。", "success")
    return redirect(url_for("transports.detail", transport_id=new_transport.id))


# =============================================================================
# ボード別運搬履歴
# =============================================================================

@bp.route("/board/<int:board_id>")
@login_required
def board_history(board_id):
    """ボードの運搬履歴"""
    board = Board.query.get_or_404(board_id)
    transports = Transport.query.filter_by(board_id=board_id).order_by(Transport.created_at.desc()).all()
    
    return render_template(
        "transports/board_history.html",
        board=board,
        transports=transports,
        STATUS_OPTIONS=STATUS_OPTIONS
    )


# =============================================================================
# 場所×日付マトリクス
# =============================================================================

@bp.route("/matrix")
@login_required
def matrix():
    """場所×日付マトリクス"""
    # 表示期間（デフォルト: 今日から2週間）
    start_date_str = request.args.get("start")
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    else:
        start_date = datetime.now(JST).date()
    
    end_date = start_date + timedelta(days=13)  # 2週間
    
    # 詳細モードかどうか
    detail_mode = request.args.get("detail") == "1"
    
    # 拠点一覧
    bases = Location.query.filter_by(is_base=True).order_by(Location.display_order).all()
    
    # 日付リスト
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    
    # マトリクスデータを計算
    matrix_data = _calculate_matrix(bases, dates, detail_mode)
    
    # 未定のボード
    pending_count = Transport.query.filter(
        db.or_(
            Transport.destination.is_(None),
            Transport.status == "destination_pending"
        )
    ).filter(Transport.status != "cancelled").count()
    
    return render_template(
        "transports/matrix.html",
        bases=bases,
        dates=dates,
        matrix_data=matrix_data,
        start_date=start_date,
        detail_mode=detail_mode,
        pending_count=pending_count,
        TIMING_OPTIONS=TIMING_OPTIONS,
        timedelta=timedelta
    )



def _estimate_board_location(board, target_date):
    """指定日のボード位置を推定（タイミングなし）"""
    # 完了した最新の運搬
    completed_transport = Transport.query.filter_by(
        board_id=board.id,
        status="completed"
    ).filter(
        Transport.actual_arrival <= datetime.combine(target_date, datetime.max.time())
    ).order_by(Transport.actual_arrival.desc()).first()
    if completed_transport:
        later_transport = Transport.query.filter_by(
            board_id=board.id
        ).filter(
            Transport.status.in_(["scheduled", "in_progress", "at_waypoint", "awaiting_handover", "destination_pending"]),
            Transport.departure_date <= target_date
        ).first()
        if later_transport:
            if later_transport.current_location:
                return later_transport.current_location
            return None
        return completed_transport.destination
    scheduled_transport = Transport.query.filter_by(
        board_id=board.id
    ).filter(
        Transport.status.in_(["scheduled", "in_progress", "at_waypoint", "awaiting_handover", "destination_pending"]),
        Transport.departure_date <= target_date
    ).first()
    if scheduled_transport and scheduled_transport.departure_date and scheduled_transport.departure_date <= target_date:
        if scheduled_transport.arrival_date and scheduled_transport.arrival_date <= target_date:
            return scheduled_transport.destination
        return scheduled_transport.current_location or None
    return board.location

def _calculate_matrix(bases, dates, detail_mode=False):
    """マトリクスデータを計算"""
    # 全ボードの初期位置を取得
    boards = Board.query.all()
    
    # 各ボードについて、各日の位置とタイミングを推定
    matrix = {}
    for base in bases:
        matrix[base.name] = {}
        for date in dates:
            if detail_mode:
                matrix[base.name][date] = {timing: 0 for timing, _ in TIMING_OPTIONS}
            else:
                matrix[base.name][date] = 0
    matrix["中継中"] = {}
    for date in dates:
        if detail_mode:
            matrix["中継中"][date] = {timing: 0 for timing, _ in TIMING_OPTIONS}
        else:
            matrix["中継中"][date] = 0
    for board in boards:
        for date in dates:
            if detail_mode:
                location, timing = _estimate_board_location_and_timing(board, date)
                if location in matrix:
                    if timing in matrix[location][date]:
                        matrix[location][date][timing] += 1
                    else:
                        matrix[location][date][timing] = 1
                elif location:
                    if timing in matrix["中継中"][date]:
                        matrix["中継中"][date][timing] += 1
                    else:
                        matrix["中継中"][date][timing] = 1
            else:
                location = _estimate_board_location(board, date)
                if location in matrix:
                    matrix[location][date] = matrix[location][date] + 1
                elif location:
                    matrix["中継中"][date] = matrix["中継中"][date] + 1
    return matrix


def _estimate_board_location_and_timing(board, target_date):
    """指定日のボード位置とタイミングを推定"""
    # 完了した最新の運搬
    completed_transport = Transport.query.filter_by(
        board_id=board.id,
        status="completed"
    ).filter(
        Transport.actual_arrival <= datetime.combine(target_date, datetime.max.time())
    ).order_by(Transport.actual_arrival.desc()).first()
    if completed_transport:
        later_transport = Transport.query.filter_by(
            board_id=board.id
        ).filter(
            Transport.status.in_(["scheduled", "in_progress", "at_waypoint", "awaiting_handover", "destination_pending"]),
            Transport.departure_date <= target_date
        ).first()
        if later_transport:
            if later_transport.current_location:
                return later_transport.current_location, later_transport.departure_timing or "pending"
            return None, "pending"
        return completed_transport.destination, completed_transport.arrival_timing or "pending"
    scheduled_transport = Transport.query.filter_by(
        board_id=board.id
    ).filter(
        Transport.status.in_(["scheduled", "in_progress", "at_waypoint", "awaiting_handover", "destination_pending"]),
        Transport.departure_date <= target_date
    ).first()
    if scheduled_transport and scheduled_transport.departure_date and scheduled_transport.departure_date <= target_date:
        if scheduled_transport.arrival_date and scheduled_transport.arrival_date <= target_date:
            return scheduled_transport.destination, scheduled_transport.arrival_timing or "pending"
        return scheduled_transport.current_location or None, scheduled_transport.departure_timing or "pending"
    return board.location, "pending"


# =============================================================================
# API（AJAX用）
# =============================================================================

@bp.route("/api/board-origin/<int:board_id>")
@login_required
def api_board_origin(board_id):
    """ボードのデフォルト出発地を取得"""
    origin = get_board_last_destination(board_id)
    return jsonify({"origin": origin})
