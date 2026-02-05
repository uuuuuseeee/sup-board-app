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
    from app import main, auth, boards, practices, admin, transports
    
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(boards.bp)
    app.register_blueprint(practices.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(transports.bp)
    
    # Register template filters
    app.template_filter("nl2br")(nl2br)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        # 初期拠点データの投入
        _init_locations()
    
    # Setup user loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))
    
    return app


def _init_locations():
    """初期拠点データを投入"""
    from app.models import Location
    
    initial_bases = [
        ("横浜", 1),
        ("海の公園", 2),
        ("平塚", 3),
        ("日本橋", 4),
    ]
    
    for name, order in initial_bases:
        if not Location.query.filter_by(name=name).first():
            location = Location(name=name, is_base=True, display_order=order)
            db.session.add(location)
    
    db.session.commit()


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
    
    @app.cli.command("migrate-history")
    def migrate_history_command():
        """Migrate UpdateHistory to Transport."""
        from app.models import UpdateHistory, Transport, TransportCarrier, TransportLog, Board
        
        with app.app_context():
            histories = UpdateHistory.query.order_by(UpdateHistory.updated_at).all()
            migrated = 0
            
            for history in histories:
                # 既に移行済みかチェック（同じボード、同じ日時）
                existing = Transport.query.filter_by(
                    board_id=history.board_id,
                ).filter(
                    Transport.created_at <= history.updated_at
                ).first()
                
                if existing:
                    continue
                
                # 運搬を作成
                transport = Transport(
                    board_id=history.board_id,
                    status="completed",
                    origin=history.previous_location or "不明",
                    destination=history.new_location,
                    current_location=history.new_location,
                    reason_type=4,  # その他
                    reason_detail="移行データ",
                    created_by_id=1,  # デフォルトユーザー
                    actual_departure=None,
                    actual_arrival=None,
                )
                db.session.add(transport)
                db.session.flush()
                
                # 運搬者を作成
                carrier = TransportCarrier(
                    transport_id=transport.id,
                    sequence=1,
                    unregistered_name=history.updated_by,
                    registered_by_id=1,
                    status="completed",
                    handover_confirmed=True
                )
                db.session.add(carrier)
                
                # ログを作成
                log = TransportLog(
                    transport_id=transport.id,
                    action="migrated",
                    new_value=f"UpdateHistory #{history.id} から移行",
                    operated_by_id=1
                )
                db.session.add(log)
                
                migrated += 1
            
            db.session.commit()
            print(f"{migrated} 件の履歴を移行しました。")
