from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_login import LoginManager

# Initialize extensions (but don't attach to app yet)
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
mail = Mail()

login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    from app.models import User  # Import inside function to avoid circular imports
    return User.query.get(int(user_id))
