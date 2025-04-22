# app.py
from datetime import timedelta
import os
import logging
from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
from extensions import db, mail
from chatbot_routes import chatbot_routes_bp
from flight_status_updater import init_flight_status_updater
from weather_monitor import init_weather_monitor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(processName)s:%(threadName)s] - %(levelname)s - %(message)s"
)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "dev_secret_key")

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///flight_booking.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_recycle": 300, "pool_pre_ping": True}
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Initialize SQLAlchemy with the app
db.init_app(app)

# Flask-Mail configuration
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_USERNAME"),
)

# Initialize Flask-Mail with the app
mail.init_app(app)

# Import models and initialize database
with app.app_context():
    from models import User
    db.create_all()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "routes.login"
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register Blueprints
from routes import routes_bp
app.register_blueprint(routes_bp)
app.register_blueprint(chatbot_routes_bp)

# Global variables for background tasks
flight_status_updater = None
weather_monitor = None

def init_background_tasks():
    global flight_status_updater, weather_monitor
    try:
        # flight_status_updater = init_flight_status_updater(app)
        # weather_monitor = init_weather_monitor(app)
        # from test_weather_monitor import init_test_weather_monitor
        # weather_monitor = init_test_weather_monitor(app)
        logging.info("Background tasks initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize background tasks: {str(e)}")
        raise

# Initialize background tasks only once
with app.app_context():
    init_background_tasks()

# Run the app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5500, use_reloader=False)