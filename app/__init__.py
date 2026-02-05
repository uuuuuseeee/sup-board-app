"""
Flask application factory.
"""
import os
import logging
import click
from flask import Flask
from app.config import Config
from app.extensions import db, login_manager
from app.models import User
from app.utils import nl2br

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    """
    Application factory function.
    
    Args:
        config_class: Configuration class to use (defaults to Config)
        
    Returns:
        Configured Flask application instance
    """
    # Get the parent directory of the app package for templates and static
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    # Load configuration
    app.config.from_object(config_class)
    config_class.init_app(app)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "このページにアクセスするにはログインが必要です。"
    login_manager.login_message_category = "error"
    
    # Register blueprints
    from app import main, auth, boards, practices, admin
    
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(boards.bp)
    app.register_blueprint(practices.bp)
    app.register_blueprint(admin.bp)
    
    # Register template filters
    app.template_filter("nl2br")(nl2br)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Setup user loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))
    
    return app


def register_cli_commands(app):
    """Register CLI commands with the application."""
    
    @app.cli.command("promote-admin")
    @click.argument("username")
    def promote_admin_command(username: str):
        """Promote a user to admin role."""
        with app.app_context():
            user = User.query.filter_by(username=username).first()
            if user:
                user.role = "admin"
                db.session.commit()
                print(f"ユーザー '{username}' は管理者に昇格しました。")
            else:
                print(f"ユーザー '{username}' が見つかりません。")
