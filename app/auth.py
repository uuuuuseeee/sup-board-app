"""
Authentication and user profile blueprint.
"""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, Team
from app.utils import to_int_or_none

bp = Blueprint('auth', __name__)


def _get_or_create_dev_user():
    """開発用のダミーユーザーを取得または作成する"""
    dev_user = User.query.filter_by(username="dev_admin").first()
    if not dev_user:
        dev_user = User(username="dev_admin", role="admin")
        dev_user.set_password("dev")
        db.session.add(dev_user)
        db.session.commit()
    return dev_user


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    
    # 開発モードの場合、POSTで自動ログイン
    if request.method == "POST":
        if os.environ.get("FLASK_DEBUG") == "1":
            # 開発モード: ダミーユーザーで自動ログイン
            dev_user = _get_or_create_dev_user()
            login_user(dev_user, remember=True)
            flash("開発モード: 自動ログインしました", "info")
            return redirect(url_for("main.dashboard"))
        
        # 本番モード: 通常の認証
        username = request.form.get("username") or ""
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for("main.dashboard"))
        flash("ユーザー名またはパスワードが正しくありません。", "error")
    return render_template("auth/login.html")


@bp.route("/guest-login")
def guest_login():
    guest_user = User.query.filter_by(role="guest").first()
    if not guest_user:
        guest_user = User(username="guest", role="guest")
        guest_user.set_password(os.urandom(16).hex())
        db.session.add(guest_user)
        db.session.commit()
    login_user(guest_user, remember=True)
    return redirect(url_for("main.dashboard"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not all([username, password]):
            flash("ユーザー名とパスワードの両方を入力してください。", "error")
            return redirect(url_for("auth.register"))
        if User.query.filter_by(username=username).first():
            flash("そのユーザー名は既に使用されています。", "error")
            return redirect(url_for("auth.register"))

        # 最初のユーザーを自動で管理者に設定
        is_first_user = User.query.count() == 0
        role = "admin" if is_first_user else "member"

        new_user = User(username=username, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        if is_first_user:
            flash(
                "最初のユーザーとして登録され、管理者権限が付与されました。ログイン後、プロフィールで詳細を設定してください。",
                "success",
            )
        else:
            flash("ユーザー登録が完了しました。ログインしてプロフィールを設定してください。", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    teams = Team.query.order_by(Team.name).all()
    if request.method == "POST":
        new_username = request.form.get("username")
        if not new_username:
            flash("ユーザー名を入力してください。", "error")
            return redirect(url_for("auth.profile"))

        if new_username != current_user.username and User.query.filter_by(username=new_username).first():
            flash("そのユーザー名は既に使用されています。", "error")
            return redirect(url_for("auth.profile"))

        current_user.username = new_username
        current_user.generation = request.form.get("generation")
        team_id_raw = request.form.get("team_id")
        current_user.team_id = to_int_or_none(team_id_raw)

        password = request.form.get("password")
        if password:
            current_user.set_password(password)

        db.session.commit()
        flash("プロフィールが更新されました。", "success")
        return redirect(url_for("auth.profile"))
    return render_template("profile.html", teams=teams)
