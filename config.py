"""
Updated Configuration for SQLite Development
"""
import os
from pathlib import Path

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    APP_NAME = 'Modern Ideal Non Government Primary School'
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_FILE_THRESHOLD = 500
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
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
    """Production configuration with SQLite"""
    DEBUG = False
    
    # SQLite database for production
    # Using absolute path for VPS deployment at /var/www/saroyarsir
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or "sqlite:////var/www/saroyarsir/school.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
