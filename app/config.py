"""
Configuration module for the Flask application.
Handles environment variables and database configuration.
"""
import os
import logging

logger = logging.getLogger(__name__)


class Config:
    """Base configuration class."""
    
    # Security
    SECRET_KEY = os.environ.get("SECRET_KEY", "a_default_secret_key_for_development")
    
    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL:
        # Heroku compatibility: postgres:// -> postgresql://
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # SQLite fallback for development
        basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "boards.db")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_recycle": 280}
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with configuration."""
        if app.config["SECRET_KEY"] == "a_default_secret_key_for_development":
            logger.warning(
                "SECRET_KEY がデフォルトのままです。本番環境では必ず環境変数で設定してください。"
            )
