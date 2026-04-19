"""
Updated Configuration for SQLite Development
"""
import os
from pathlib import Path

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    APP_NAME = 'Modern Ideal Kindergarten'
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_FILE_THRESHOLD = 500
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 75 * 1024 * 1024  # 75 MB (allows up to ~50 MB base64-encoded files)
    UPLOAD_FOLDER = 'static/uploads'

class DevelopmentConfig(Config):
    """Development configuration with SQLite"""
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True  # Auto-reload templates in development
    
    # SQLite database for development
    base_dir = Path(__file__).parent
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"sqlite:///{base_dir}/school.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

class ProductionConfig(Config):
    """Production configuration – PostgreSQL on VPS, SQLite fallback"""
    DEBUG = False

    # On VPS set: DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/school_db
    # Falls back to SQLite during migration period
    _db_url = os.environ.get('DATABASE_URL') or "sqlite:////var/www/school/school.db"
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Only apply PostgreSQL pool options when NOT using SQLite
    if not _db_url.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 10,
            'max_overflow': 20,
        }

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
