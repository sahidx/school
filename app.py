"""
Flask Application Factory
Main application setup and configuration
"""
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_session import Session
import os

# Import extensions
from models import db
from config import config_by_name

# Initialize extensions
bcrypt = Bcrypt()
sess = Session()

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__, template_folder='templates/templates', static_folder='static/static')
    app.config.from_object(config_by_name[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    bcrypt.init_app(app)
    sess.init_app(app)
    
    # Enable CORS for all domains on all routes
    CORS(app, supports_credentials=True)
    
    # Register blueprints
    from routes.auth import auth_bp
    from users import users_bp  # Import from users.py (full implementation)
    from routes.batches import batches_bp
    from routes.exams import exams_bp
    from routes.questions import questions_bp
    from routes.fees_new import fees_bp  # Using new rewritten fee routes
    from routes.sms import sms_bp
    from routes.sms_templates import sms_templates_bp
    from routes.attendance import attendance_bp
    from routes.results import results_bp
    from routes.ai import ai_bp
    from routes.dashboard import dashboard_bp
    from routes.settings import settings_bp
    from routes.students import students_bp
    from routes.monthly_exams import monthly_exams_bp
    from routes.online_exams import online_exams_bp  # NEW: Online MCQ Exam System
    from routes.debug import debug_bp
    from routes.documents import documents_bp
    from routes.database import database_bp
    from routes.school import school_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(students_bp, url_prefix='/api/students')
    app.register_blueprint(batches_bp, url_prefix='/api/batches')
    app.register_blueprint(exams_bp, url_prefix='/api/exams')
    app.register_blueprint(questions_bp, url_prefix='/api/questions')
    app.register_blueprint(fees_bp, url_prefix='/api/fees')
    app.register_blueprint(sms_bp, url_prefix='/api/sms')
    app.register_blueprint(sms_templates_bp, url_prefix='/api/sms/templates')
    app.register_blueprint(attendance_bp, url_prefix='/api/attendance')
    app.register_blueprint(results_bp, url_prefix='/api/results')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(monthly_exams_bp, url_prefix='/api/monthly-exams')
    app.register_blueprint(online_exams_bp)  # Uses /api/online-exams prefix from blueprint
    app.register_blueprint(debug_bp, url_prefix='/api/debug')
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(database_bp, url_prefix='/api/database')
    app.register_blueprint(school_bp)  # routes define /api/school/...
    
    # Register template routes
    from routes.templates import templates_bp
    app.register_blueprint(templates_bp)
    
    # Add favicon route
    @app.route('/favicon.ico')
    def favicon():
        return '', 204  # No content response for favicon
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        from flask import request
        # Log 404 details for debugging (method, path, headers, body)
        try:
            log_text = []
            log_text.append(f"TIME: {__import__('datetime').datetime.utcnow().isoformat()}Z")
            log_text.append(f"METHOD: {request.method}")
            log_text.append(f"PATH: {request.path}")
            # Headers
            headers = '\n'.join([f"{k}: {v}" for k, v in request.headers.items()])
            log_text.append('HEADERS:')
            log_text.append(headers)
            # Body (may be empty)
            try:
                body = request.get_data(as_text=True)
            except Exception:
                body = '<unable to read body>'
            log_text.append('BODY:')
            log_text.append(body or '')
            log_text.append('-' * 80)
            with open('/tmp/last_404.log', 'a') as f:
                f.write('\n'.join(log_text) + '\n')
        except Exception:
            # Best-effort logging only
            pass

        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import request
        db.session.rollback()
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden(error):
        from flask import request
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'app': app.config['APP_NAME'],
            'environment': config_name
        })
    
    # Database health check endpoint
    @app.route('/health/db')
    def database_health():
        """Database health check endpoint"""
        try:
            from services.database import health_check as db_health_check
            return jsonify(db_health_check())
        except ImportError:
            # Fallback if service not available
            try:
                db.session.execute('SELECT 1')
                return jsonify({'status': 'healthy', 'message': 'Database connection OK'})
            except Exception as e:
                return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
    
    # Root endpoint handled by templates blueprint
    
    # Create database tables
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully!")
        except Exception as e:
            print(f"Error creating database tables: {str(e)}")
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 8001))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Modern Ideal Kindergarten on port {port}")
    print(f"Debug mode: {debug}")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)