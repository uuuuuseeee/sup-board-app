"""
Custom decorators for access control.
"""
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def admin_required(f):
    """Decorator to require admin role for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(current_user, "role") or current_user.role != "admin":
            flash("このページにアクセスするには管理者権限が必要です。", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def member_required(f):
    """Decorator to prevent guest users from accessing a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if hasattr(current_user, "role") and current_user.role == "guest":
            flash("ゲストユーザーはこの操作を実行できません。", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated_function
