from flask import Flask
import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from app.extensions import db, migrate, bcrypt, login_manager, init_services
from sqlalchemy import inspect

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__, template_folder='templates')

    # Configure instance path
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_path = os.path.abspath(os.path.join(basedir, '..', 'instance'))
    os.makedirs(instance_path, exist_ok=True)

    # Database configuration
    db_path = os.path.join(instance_path, 'mela_scan.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path.replace(os.sep, "/")}'

    # Complete configuration setup
    app.config.from_mapping(
        # Security
        SECRET_KEY=os.getenv('SECRET_KEY'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,

        # File Uploads
        UPLOAD_FOLDERS={
            'registration': os.path.join(instance_path, os.getenv('UPLOAD_FOLDER_REGISTRATION')),
            'reports': os.path.join(instance_path, os.getenv('UPLOAD_FOLDER_REPORTS')),
            'patient_images': os.path.join(instance_path, 'uploads/patient_images'),
            'temp_images': os.path.join(instance_path, 'uploads/temp')
        },
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5MB
        ALLOWED_EXTENSIONS={'pdf', 'png', 'jpg', 'jpeg'},

        # AI Model Configuration
        RESNET_PATH=os.path.abspath(os.path.join(basedir, os.getenv('RESNET_PATH'))),
        EFFICIENTNET_PATH=os.path.join(basedir, os.getenv('EFFICIENTNET_PATH')),
        DENSENET_PATH=os.path.join(basedir, os.getenv('DENSENET_PATH')),

        # Admin credentials
        ADMIN_EMAIL=os.getenv('ADMIN_EMAIL'),
        ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD')
    )

    # Debug output
    print(f"Database will be created at: {db_path}")
    print(f"SQLAlchemy URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

    # Create upload directories
    for folder in app.config['UPLOAD_FOLDERS'].values():
        os.makedirs(folder, exist_ok=True)

    # Create models directory if it doesn't exist
    models_dir = os.path.join(basedir, 'models')
    os.makedirs(models_dir, exist_ok=True)

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

    # Initialize database
    with app.app_context():
        if not os.path.exists(db_path):
            print(f"Created new database file at: {db_path}")
        # Import models
        from app.models import (
            User, Clinic, Patient,
            Image, Report,
            ClinicRegistration,
            UserClinicMap, PatientClinicMap
        )
        db.create_all()
        # Verify creation
        try:
            tables = inspect(db.engine).get_table_names()
            print(f"Tables created: {tables}")
        except Exception as e:
            print(f"Error checking tables: {str(e)}")

    # Initialize services (AI models, etc.)
    init_services(app)

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

    return app
