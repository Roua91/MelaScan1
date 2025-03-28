from flask import Flask
import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from app.extensions import db, migrate, bcrypt, login_manager

# Load environment variables first
load_dotenv()

def create_app():
    app = Flask(__name__, template_folder='templates')
    
    # Configuration
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-fallback-key'),
        SQLALCHEMY_DATABASE_URI = r'sqlite:///D:\MelaScan1\instance\mela_scan.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER_REGISTRATION=os.getenv('UPLOAD_FOLDER_REGISTRATION', 'uploads/registration'),
        UPLOAD_FOLDER_REPORTS=os.getenv('UPLOAD_FOLDER_REPORTS', 'uploads/reports')
    )
    
    # Ensure instance and upload folders exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER_REGISTRATION'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER_REPORTS'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    
    # Flask-Login setup
    login_manager.init_app(app)  # This must come after db.init_app()
    login_manager.login_view = 'auth.login'  
    
    # CSRF Protection
    CSRFProtect(app)
    
    @app.context_processor
    def inject_csrf():
        from flask_wtf.csrf import generate_csrf
        return {'csrf_token': generate_csrf} 

    # Register blueprints
    from app.routes.home import home_bp
    from app.routes.auth import auth_bp, registration_bp, admin_bp
    
    app.register_blueprint(home_bp)
    app.register_blueprint(registration_bp, url_prefix='/registration')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app