"""
Practice management blueprint.
"""
import random
from typing import List
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload
from app.extensions import db
from app.models import (
    Practice, PracticeSession, Attendance, Transport, 
    User, Team, Board
)
from app.utils import to_int_or_none, natural_sort_key
from app.decorators import admin_required, member_required

bp = Blueprint('practices', __name__, url_prefix='/practices')


@bp.route("")
@login_required
def index():
    practices = Practice.query.order_by(Practice.practice_date.desc()).all()
    return render_template("practice/index.html", practices=practices)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    teams = Team.query.order_by(Team.name).all()
    generations_raw = db.session.query(User.generation).distinct().order_by(User.generation).all()
    generations = [gen[0] for gen in generations_raw if gen[0]]

    if request.method == "POST":
        title = request.form.get("title")
        practice_date_str = request.form.get("practice_date")
        location = request.form.get("location")
        team_id = to_int_or_none(request.form.get("team_id"))
        target_generations = request.form.getlist("generations")

        if not all([title, practice_date_str, location, team_id, target_generations]):
            flash("すべての項目を入力してください。", "error")
            return redirect(url_for("practices.create"))

        # チーム存在確認
        team = Team.query.get(team_id)
        if not team:
            flash("選択されたチームが見つかりませんでした。", "error")
            return redirect(url_for("practices.create"))

        try:
            practice_date = datetime.strptime(practice_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("日付の形式が正しくありません。", "error")
            return redirect(url_for("practices.create"))

        new_practice = Practice(title=title, practice_date=practice_date, location=location, team_id=team_id)
        db.session.add(new_practice)

        target_users = User.query.filter(User.team_id == team_id, User.generation.in_(target_generations)).all()
        if not target_users:
            flash("対象となるユーザーが見つかりませんでした。", "warning")
            db.session.rollback()
            return redirect(url_for("practices.create"))

        for user in target_users:
            attendance = Attendance(practice=new_practice, user_id=user.id, status="unanswered")
            db.session.add(attendance)

        db.session.commit()
        flash(f'新しい練習「{title}」を作成し、{len(target_users)}人に出欠確認を送信しました。', "success")
        return redirect(url_for("practices.index"))

    return render_template("practice/create.html", teams=teams, generations=generations)


@bp.route("/<int:practice_id>")
@login_required
def detail(practice_id: int):
    practice = (
        Practice.query.options(
            selectinload(Practice.sessions).selectinload(PracticeSession.members),
            selectinload(Practice.attendances).selectinload(Attendance.user),
            selectinload(Practice.transports).selectinload(Transport.user),
            selectinload(Practice.transports).selectinload(Transport.board),
        )
        .filter_by(id=practice_id)
        .first_or_404()
    )

    user_attendance = Attendance.query.filter_by(practice_id=practice.id, user_id=current_user.id).first()
    all_attendances: List[Attendance] = (
        Attendance.query.filter_by(practice_id=practice.id)
        .join(User)
        .order_by(User.generation, User.username)
        .all()
    )

    boards_at_location = Board.query.filter_by(location=practice.location).count()

    assignable_attendees = [att.user for att in all_attendances if att.status in ["present", "late_leave"]]
    assigned_user_ids = [member.id for session in practice.sessions for member in session.members]
    unassigned_attendees = [user for user in assignable_attendees if user.id not in assigned_user_ids]

    # セッション最大人数
    max_session_members = max((len(s.members) for s in practice.sessions), default=0)
    required_transport_boards = max(0, max_session_members - boards_at_location)

    transports_to = Transport.query.filter_by(practice_id=practice.id, direction="to").all()
    transports_from = Transport.query.filter_by(practice_id=practice.id, direction="from").all()

    # ボード一覧（自然順）
    all_boards = Board.query.all()
    all_boards = sorted(all_boards, key=lambda b: natural_sort_key(b.name))

    transported_to_board_ids = [t.board_id for t in transports_to]
    boards_at_practice = Board.query.filter(
        (Board.location == practice.location) | (Board.id.in_(transported_to_board_ids))
    ).all()

    return render_template(
        "practice/detail.html",
        practice=practice,
        user_attendance=user_attendance,
        all_attendances=all_attendances,
        boards_at_location=boards_at_location,
        present_attendees=[att.user for att in all_attendances if att.status == "present"],
        assignable_attendees=assignable_attendees,
        unassigned_attendees=unassigned_attendees,
        max_session_members=max_session_members,
        required_transport_boards=required_transport_boards,
        transports_to=transports_to,
        transports_from=transports_from,
        all_boards=all_boards,
        boards_at_practice=boards_at_practice,
    )


@bp.route("/answer/<int:attendance_id>", methods=["POST"])
@login_required
@member_required
def answer(attendance_id: int):
    attendance = Attendance.query.get_or_404(attendance_id)
    if attendance.user_id != current_user.id:
        flash("権限がありません。", "error")
        return redirect(url_for("practices.index"))

    attendance.status = request.form.get("status")
    attendance.notes = request.form.get("notes")
    attendance.reason = request.form.get("reason")
    db.session.commit()
    flash("出欠を更新しました。", "success")
    return redirect(url_for("practices.detail", practice_id=attendance.practice_id))


@bp.route("/<int:practice_id>/add_session", methods=["POST"])
@login_required
@admin_required
def add_session(practice_id: int):
    practice = Practice.query.get_or_404(practice_id)
    session_count = len(practice.sessions)
    new_session = PracticeSession(practice_id=practice.id, session_number=session_count + 1)
    db.session.add(new_session)
    db.session.commit()
    flash(f"{session_count + 1}部を追加しました。", "success")
    return redirect(url_for("practices.detail", practice_id=practice.id, _anchor="session-management"))


@bp.route("/assign_member", methods=["POST"])
@login_required
@admin_required
def assign_member():
    user_ids_raw = request.form.getlist("user_ids")
    session_id = to_int_or_none(request.form.get("session_id"))
    practice_id = to_int_or_none(request.form.get("practice_id"))

    if not practice_id:
        flash("不正なリクエストです。", "error")
        return redirect(url_for("practices.index"))

    if not user_ids_raw:
        flash("割り当てるメンバーが選択されていません。", "error")
        return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="session-management"))

    if not session_id:
        flash("セッションが見つかりません。", "error")
        return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="session-management"))

    session = PracticeSession.query.get(session_id)
    if not session:
        flash("セッションが見つかりません。", "error")
        return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="session-management"))

    user_ids = [to_int_or_none(uid) for uid in user_ids_raw]
    user_ids = [uid for uid in user_ids if uid is not None]

    assigned_count = 0
    assigned_usernames: List[str] = []
    for user_id in user_ids:
        user = User.query.get(user_id)
        if user and user not in session.members:
            session.members.append(user)
            assigned_count += 1
            assigned_usernames.append(user.username)

    if assigned_count > 0:
        db.session.commit()
        flash(f'{", ".join(assigned_usernames)} を{session.session_number}部に割り当てました。', "success")
    else:
        flash("割り当てる新しいメンバーがいませんでした。", "info")
    return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="session-management"))


@bp.route("/unassign_member/<int:session_id>/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def unassign_member(session_id: int, user_id: int):
    session = PracticeSession.query.get_or_404(session_id)
    user = User.query.get_or_404(user_id)
    if user in session.members:
        session.members.remove(user)
        db.session.commit()
        flash(f"{user.username}を{session.session_number}部から外しました。", "success")
    return redirect(url_for("practices.detail", practice_id=session.practice_id, _anchor="session-management"))


@bp.route("/delete_session/<int:session_id>", methods=["POST"])
@login_required
@admin_required
def delete_session(session_id: int):
    session_to_delete = PracticeSession.query.get_or_404(session_id)
    practice_id = session_to_delete.practice_id
    db.session.delete(session_to_delete)
    db.session.commit()
    flash(f"{session_to_delete.session_number}部を削除しました。", "success")
    return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="session-management"))


@bp.route("/delete/<int:practice_id>", methods=["POST"])
@login_required
@admin_required
def delete(practice_id: int):
    practice_to_delete = Practice.query.get_or_404(practice_id)
    db.session.delete(practice_to_delete)
    db.session.commit()
    flash(f'練習「{practice_to_delete.title}」を削除しました。', "success")
    return redirect(url_for("practices.index"))


@bp.route("/assign_transport", methods=["POST"])
@login_required
@admin_required
def assign_transport():
    practice_id = to_int_or_none(request.form.get("practice_id"))
    user_id = to_int_or_none(request.form.get("user_id"))
    board_ids_raw = request.form.getlist("board_ids")
    direction = request.form.get("direction", "to")

    if not practice_id:
        flash("不正なリクエストです。", "error")
        return redirect(url_for("practices.index"))

    board_ids = [to_int_or_none(bid) for bid in board_ids_raw]
    board_ids = [bid for bid in board_ids if bid is not None]

    if not all([practice_id, user_id, board_ids]):
        flash("運搬者とボードを選択してください。", "error")
        return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="transport-planning"))

    user = User.query.get(user_id)
    if not user:
        flash("ユーザーが見つかりません。", "error")
        return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="transport-planning"))

    for board_id in board_ids:
        existing = Transport.query.filter_by(
            practice_id=practice_id, board_id=board_id, direction=direction
        ).first()
        if existing:
            # 上書き処理
            old_user = User.query.get(existing.user_id)
            if old_user and old_user.id != user_id:
                old_user.transport_count = max(0, old_user.transport_count - 1)
                user.transport_count += 1
            existing.user_id = user_id
        else:
            # 新規登録
            transport = Transport(practice_id=practice_id, user_id=user_id, board_id=board_id, direction=direction)
            db.session.add(transport)
            user.transport_count += 1

    db.session.commit()
    flash("運搬情報を登録しました。", "success")
    return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="transport-planning"))


@bp.route("/unassign_transport/<int:transport_id>", methods=["POST"])
@login_required
@admin_required
def unassign_transport(transport_id: int):
    transport_to_delete = Transport.query.get_or_404(transport_id)
    practice_id = transport_to_delete.practice_id
    user = User.query.get(transport_to_delete.user_id)
    if user:
        user.transport_count = max(0, user.transport_count - 1)
    db.session.delete(transport_to_delete)
    db.session.commit()
    flash("運搬情報を削除しました。", "success")
    return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="transport-planning"))


@bp.route("/<int:practice_id>/run_lottery", methods=["POST"])
@login_required
@admin_required
def run_lottery(practice_id: int):
    practice = Practice.query.get_or_404(practice_id)
    board_ids_for_lottery_raw = request.form.getlist("board_ids_for_lottery")
    board_ids_for_lottery = [to_int_or_none(bid) for bid in board_ids_for_lottery_raw]
    board_ids_for_lottery = [bid for bid in board_ids_for_lottery if bid is not None]

    if not board_ids_for_lottery:
        flash("抽選対象のボードが選択されていません。", "error")
        return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="transport-planning"))

    boards_to_take_home_count = len(board_ids_for_lottery)

    attendees = {att.user for att in practice.attendances if att.status == "present"}
    transports_to = Transport.query.filter_by(practice_id=practice.id, direction="to").all()
    transports_from_confirmed = Transport.query.filter_by(practice_id=practice.id, direction="from").all()

    transporters_to_users = {t.user for t in transports_to if t.user is not None}
    transporters_from_confirmed_users = {t.user for t in transports_from_confirmed if t.user is not None}

    primary_pool = list(attendees - transporters_to_users - transporters_from_confirmed_users)
    secondary_pool = list(transporters_to_users - transporters_from_confirmed_users)

    if len(primary_pool) >= boards_to_take_home_count:
        final_pool = primary_pool
    else:
        final_pool = primary_pool + secondary_pool

    if len(final_pool) < boards_to_take_home_count:
        flash(
            f"運搬可能な人数が足りません！(必要: {boards_to_take_home_count}人, 候補: {len(final_pool)}人)",
            "error",
        )
        return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="transport-planning"))

    # 重み: 既存のtransport_countが少ないほど当たりやすいよう二乗で調整
    weights = [1 / ((user.transport_count + 1) ** 2) for user in final_pool]

    winners = []
    pool_with_weights = list(zip(final_pool, weights))
    for _ in range(boards_to_take_home_count):
        if not pool_with_weights:
            break
        users, current_weights = zip(*pool_with_weights)
        winner = random.choices(users, weights=current_weights, k=1)[0]
        winners.append(winner)
        # 当選者はプールから除外
        pool_with_weights = [item for item in pool_with_weights if item[0].id != winner.id]

    # 当選者をボードに割り当て
    for i, winner in enumerate(winners):
        board_id = board_ids_for_lottery[i]
        existing = Transport.query.filter_by(
            practice_id=practice_id, board_id=board_id, direction="from"
        ).first()
        if not existing:
            transport = Transport(practice_id=practice_id, user_id=winner.id, board_id=board_id, direction="from")
            db.session.add(transport)
            winner.transport_count += 1

    db.session.commit()
    winner_names = [w.username for w in winners]
    flash(f'抽選が完了し、{", ".join(winner_names)} が運搬者に自動で割り当てられました。', "success")
    return redirect(url_for("practices.detail", practice_id=practice_id, _anchor="transport-planning"))
