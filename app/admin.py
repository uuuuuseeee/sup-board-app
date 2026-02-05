"""
Admin panel blueprint.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Team, User, Announcement, PracticeSession, Attendance, Transport
from app.decorators import admin_required

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route("")
@login_required
@admin_required
def panel():
    return render_template("admin/panel.html")


@bp.route("/teams", methods=["GET", "POST"])
@login_required
@admin_required
def teams():
    if request.method == "POST":
        team_name = request.form.get("team_name")
        if team_name:
            if Team.query.filter_by(name=team_name).first():
                flash("そのチーム名は既に使用されています。", "error")
            else:
                new_team = Team(name=team_name)
                db.session.add(new_team)
                db.session.commit()
                flash(f'チーム「{team_name}」を追加しました。', "success")
        else:
            flash("チーム名を入力してください。", "error")
        return redirect(url_for("admin.teams"))
    teams = Team.query.order_by(Team.name).all()
    return render_template("admin/teams.html", teams=teams)


@bp.route("/teams/delete/<int:team_id>", methods=["POST"])
@login_required
@admin_required
def delete_team(team_id: int):
    team_to_delete = Team.query.get_or_404(team_id)
    if team_to_delete.users:
        flash("所属しているユーザーがいるため、このチームは削除できません。", "error")
    else:
        db.session.delete(team_to_delete)
        db.session.commit()
        flash(f'チーム「{team_to_delete.name}」を削除しました。', "success")
    return redirect(url_for("admin.teams"))


@bp.route("/users")
@login_required
@admin_required
def users():
    users = User.query.all()
    return render_template("admin/users.html", users=users)


@bp.route("/users/promote/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def promote_user(user_id: int):
    user_to_promote = User.query.get_or_404(user_id)
    user_to_promote.role = "admin"
    db.session.commit()
    flash(f"ユーザー '{user_to_promote.username}' は管理者に昇格しました。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/demote/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def demote_user(user_id: int):
    if current_user.id == user_id:
        flash("自分自身を降格させることはできません。", "error")
        return redirect(url_for("admin.users"))
    user_to_demote = User.query.get_or_404(user_id)
    user_to_demote.role = "member"
    db.session.commit()
    flash(f"ユーザー '{user_to_demote.username}' は一般ユーザーに降格しました。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id: int):
    if current_user.id == user_id:
        flash("自分自身を削除することはできません。", "error")
        return redirect(url_for("admin.users"))

    user_to_delete = User.query.get_or_404(user_id)

    # 関連する子レコードを先に削除
    Announcement.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    Attendance.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    Transport.query.filter_by(user_id=user_id).delete(synchronize_session=False)

    # ユーザーをセッションから削除
    for session in PracticeSession.query.all():
        if user_to_delete in session.members:
            session.members.remove(user_to_delete)

    # ユーザー本体を削除
    db.session.delete(user_to_delete)

    db.session.commit()
    flash(f"ユーザー '{user_to_delete.username}' と関連データをすべて削除しました。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/announcements")
@login_required
@admin_required
def announcements():
    all_announcements = Announcement.query.order_by(Announcement.timestamp.desc()).all()
    return render_template("admin/announcements.html", announcements=all_announcements)


@bp.route("/announcements/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_announcement():
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        if not title or not content:
            flash("タイトルと内容の両方を入力してください。", "error")
            return redirect(url_for("admin.new_announcement"))
        announcement = Announcement(title=title, content=content, user_id=current_user.id)
        db.session.add(announcement)
        db.session.commit()
        flash("新しいお知らせを投稿しました。", "success")
        return redirect(url_for("admin.announcements"))
    return render_template("admin/new_announcement.html")


@bp.route("/announcements/delete/<int:announcement_id>", methods=["POST"])
@login_required
@admin_required
def delete_announcement(announcement_id: int):
    announcement_to_delete = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement_to_delete)
    db.session.commit()
    flash("お知らせを削除しました。", "success")
    return redirect(url_for("admin.announcements"))
