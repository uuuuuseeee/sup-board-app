"""
Board management blueprint.
"""
from typing import List
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Board, UpdateHistory
from app.utils import (
    natural_sort_key, 
    get_selected_location, 
    validated_order_param, 
    validated_sort_by_param,
    now_jst_str,
    to_int_or_none
)
from app.decorators import member_required

bp = Blueprint('boards', __name__, url_prefix='/boards')


@bp.route("")
@login_required
def index():
    sort_by = validated_sort_by_param(request.args.get("sort_by"), "id")
    order = validated_order_param(request.args.get("order"), "asc")

    # すべてのボードを取得
    boards: List[Board] = Board.query.all()

    # ソート
    reverse = order == "desc"
    if sort_by == "name":
        boards = sorted(boards, key=lambda b: natural_sort_key(b.name), reverse=reverse)
    else:
        boards = sorted(boards, key=lambda b: b.id, reverse=reverse)

    # ロケーション件数集計
    location_counts: dict[str, int] = {}
    for b in boards:
        location_counts[b.location] = location_counts.get(b.location, 0) + 1

    return render_template("boards/index.html", boards=boards, location_counts=location_counts)


@bp.route("/add", methods=["GET", "POST"])
@login_required
@member_required
def add():
    if request.method == "POST":
        name = request.form.get("name")
        serial_number = (request.form.get("serial_number") or None) or None
        notes = request.form.get("notes")
        location = get_selected_location(request.form)
        user = current_user.username

        if not all([name, location]):
            flash("必須項目が入力されていません。", "error")
            return redirect(url_for("boards.add"))

        if Board.query.filter_by(name=name).first():
            flash(f'ボード名「{name}」は既に使用されています。', "error")
            return redirect(url_for("boards.add"))

        if serial_number and Board.query.filter_by(serial_number=serial_number).first():
            flash(f'シリアル番号「{serial_number}」は既に使用されています。', "error")
            return redirect(url_for("boards.add"))

        new_board = Board(
            name=name,
            serial_number=serial_number,
            location=location,
            user=user,
            notes=notes,
            updated_at=now_jst_str(),
        )
        db.session.add(new_board)
        db.session.commit()
        flash(f'ボード「{name}」が正常に追加されました。', "success")
        return redirect(url_for("boards.index"))
    return render_template("boards/add.html")


@bp.route("/update/<int:board_id>", methods=["GET", "POST"])
@login_required
@member_required
def update(board_id: int):
    board_to_update = Board.query.get_or_404(board_id)
    if request.method == "POST":
        new_name = request.form.get("name")
        new_serial_number = (request.form.get("serial_number") or None) or None
        notes = request.form.get("notes")

        if not new_name:
            flash("必須項目が入力されていません。", "error")
            return redirect(url_for("boards.update", board_id=board_id))

        if Board.query.filter(Board.name == new_name, Board.id != board_id).first():
            flash(f'ボード名「{new_name}」は既に使用されています。', "error")
            return redirect(url_for("boards.update", board_id=board_id))

        if new_serial_number and Board.query.filter(
            Board.serial_number == new_serial_number, Board.id != board_id
        ).first():
            flash(f'シリアル番号「{new_serial_number}」は既に使用されています。', "error")
            return redirect(url_for("boards.update", board_id=board_id))

        board_to_update.name = new_name
        board_to_update.serial_number = new_serial_number
        board_to_update.notes = notes
        board_to_update.updated_at = now_jst_str()

        db.session.commit()
        flash(f'ボード「{board_to_update.name}」が正常に更新されました。', "success")
        return redirect(url_for("boards.index"))
    return render_template("boards/update.html", board=board_to_update)


@bp.route("/delete/<int:board_id>", methods=["POST"])
@login_required
@member_required
def delete(board_id: int):
    board_to_delete = Board.query.get_or_404(board_id)
    db.session.delete(board_to_delete)
    db.session.commit()
    flash(f'ボード「{board_to_delete.name}」を削除しました。', "success")
    return redirect(url_for("boards.index"))


@bp.route("/history/<int:board_id>")
@login_required
def history(board_id: int):
    """旧履歴ページ - 新しい運搬履歴ページへリダイレクト"""
    return redirect(url_for("transports.board_history", board_id=board_id))


@bp.route("/bulk_update", methods=["POST"])
@login_required
@member_required
def bulk_update():
    board_ids_raw = request.form.getlist("board_ids")
    board_ids = [to_int_or_none(bid) for bid in board_ids_raw if to_int_or_none(bid) is not None]

    if not board_ids:
        flash("更新するボードが選択されていません。", "error")
        return redirect(url_for("boards.index"))

    updater = current_user.username
    new_location = get_selected_location(request.form)
    current_time_jst = now_jst_str()

    updated_count = 0
    for board_id in board_ids:
        board = Board.query.get(board_id)
        if not board:
            continue

        previous_location = board.location
        previous_user = board.user

        if previous_location != new_location or previous_user != updater:
            history_entry = UpdateHistory(
                board_id=board.id,
                previous_location=previous_location,
                new_location=new_location,
                updated_by=updater,
                updated_at=current_time_jst,
            )
            db.session.add(history_entry)

        board.location = new_location
        board.user = updater
        board.updated_at = current_time_jst
        updated_count += 1

    if updated_count > 0:
        db.session.commit()
        flash(f"{updated_count}件のボード情報を一括更新しました。", "success")
    return redirect(url_for("boards.index"))
