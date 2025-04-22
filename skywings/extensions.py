from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_mail import Mail

# Define the base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Create a single SQLAlchemy instance (not bound to an app yet)
db = SQLAlchemy(model_class=Base)

# Create a single Flask-Mail instance (not bound to an app yet)
mail = Mail()