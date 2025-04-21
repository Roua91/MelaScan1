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
    
    # Complete configuration setup
    app.config.from_mapping(
        # Security
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-fallback-key'),
        CSRF_ENABLED=True,
        
        # Database
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{db_path}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        
        # File Uploads
        UPLOAD_FOLDERS={
            'registration': os.path.join(instance_path, 'uploads/registration'),
            'reports': os.path.join(instance_path, 'uploads/reports'),
            'patient_images': os.path.join(instance_path, 'uploads/patient_images')
        },
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5MB
        ALLOWED_EXTENSIONS={'pdf', 'png', 'jpg', 'jpeg'},
        
        # Session
        PERMANENT_SESSION_LIFETIME=3600,  # 1 hour
        SESSION_COOKIE_SECURE=False,  # True in production with HTTPS
        SESSION_COOKIE_HTTPONLY=True,
        
        # Flask-Login
        LOGIN_DISABLED=False
    )
    
    # Create all needed directories
    for folder in app.config['UPLOAD_FOLDERS'].values():
        os.makedirs(folder, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    CSRFProtect(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Import models after db initialization
    with app.app_context():
        from app.models import (
            User, Clinic, Patient, 
            Image, Report, 
            ClinicRegistration,
            UserClinicMap, PatientClinicMap
        )
        db.create_all()  # Creates tables if they don't exist
    
    # Register blueprints
    from app.routes.home import home_bp
    from app.routes.auth import auth_bp, registration_bp
    from app.routes.admin import admin_bp 
    from app.routes.local_admin import local_admin_bp
    from app.routes.doctors import doctor_bp
    
    app.register_blueprint(home_bp)
    app.register_blueprint(registration_bp, url_prefix='/registration')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(local_admin_bp, url_prefix='/local_admin')
    app.register_blueprint(doctor_bp, url_prefix='/doctor')
    
    print("Loaded DB from:", app.config['SQLALCHEMY_DATABASE_URI'])


    return app