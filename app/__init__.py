from flask import Flask
import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from app.extensions import db, migrate, bcrypt, login_manager

# Load environment variables first
load_dotenv()

def create_app():
    app = Flask(__name__, template_folder='templates')
    
    # Configure instance path - more robust handling
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_path = os.path.join(basedir, '..', 'instance')
    os.makedirs(instance_path, exist_ok=True)
    
    # Database configuration
    db_path = os.path.join(instance_path, 'mela_scan.db')
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-fallback-key'),
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{db_path}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER_REGISTRATION=os.getenv('UPLOAD_FOLDER_REGISTRATION', 'uploads/registration'),
        UPLOAD_FOLDER_REPORTS=os.getenv('UPLOAD_FOLDER_REPORTS', 'uploads/reports')
    )
    
    # Create directories
    os.makedirs(app.config['UPLOAD_FOLDER_REGISTRATION'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER_REPORTS'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    
    # Import models AFTER db initialization but BEFORE migrate
    with app.app_context():
        from app.models import User, Clinic, Patient, Image, Report, ClinicRegistration, UserClinicMap, PatientClinicMap
        db.create_all()  # Creates tables if they don't exist

    # Now initialize migrate
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    
    # Flask-Login setup
    login_manager.init_app(app)
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