from app import app
from models import db

def update_database_schema():
    """Update database schema to include weather monitoring columns."""
    with app.app_context():
        try:
            # This will create any new columns defined in the models
            db.create_all()
            print('Successfully updated database schema')
            return True
        except Exception as e:
            print(f'Error updating database schema: {str(e)}')
            return False

if __name__ == '__main__':
    update_database_schema()