#!/usr/bin/env python3
"""
SmartGardenHub Application Runner
Start the Flask application with proper configuration
"""
import os
import sys
from pathlib import Path

# Add the python_conversion directory to the Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = current_dir / '.env'
    load_dotenv(env_path)
    print(f"📋 Loaded environment variables from {env_path}")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables")

# Set environment variables if not already set
if not os.getenv('FLASK_ENV'):
    os.environ['FLASK_ENV'] = 'development'

if not os.getenv('FLASK_APP'):
    os.environ['FLASK_APP'] = 'app.py'

# Import and create the Flask application
from app import create_app

def main():
    """Main application entry point"""
    # Get configuration
    env = os.getenv('FLASK_ENV', 'development')
    port = int(os.getenv('PORT', 3001))  # Changed default from 5000 to 3001
    debug = os.getenv('DEBUG', 'true').lower() == 'true'
    host = os.getenv('HOST', '0.0.0.0')
    
    print("🏫 Modern Ideal Non Government Primary School - Management System")
    print("=" * 50)
    print(f"Environment: {env}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print("=" * 50)
    
    # Create Flask application
    try:
        app = create_app(env)
        print("✅ Flask application created successfully!")
        
        # Start the application
        print(f"🚀 Starting server on http://{host}:{port}")
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
        
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()