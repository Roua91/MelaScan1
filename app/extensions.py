from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_login import LoginManager
from app.services.ai_service import ai_service

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
mail = Mail()
login_manager = LoginManager()

def init_services(app):
    """Initialize all services when app starts"""
    with app.app_context():
        try:
            # Initialize AI service with app context
            ai_service.init_app(app)
            app.extensions['ai_service'] = ai_service 
            
            # Verify model loading
            if 'resnet_cbam' not in ai_service.models:
                raise RuntimeError("Failed to load primary model")
                
            app.logger.info("AI models loaded successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize services: {str(e)}")
            raise

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))