from extensions import db
from models import Airport, Flight
from sqlalchemy import text

def upgrade_database():
    """Add new columns for weather monitoring."""
    try:
        # Add columns to Airport table
        with db.engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE airport 
                ADD COLUMN latitude FLOAT,
                ADD COLUMN longitude FLOAT;
            """))
            
            # Add columns to Flight table
            conn.execute(text("""
                ALTER TABLE flight
                ADD COLUMN postponed_count INTEGER DEFAULT 0,
                ADD COLUMN weather_status VARCHAR(500),
                ADD COLUMN cancellation_reason VARCHAR(500);
            """))
            
            conn.commit()
        
        print('Successfully added weather monitoring columns')
        return True
    except Exception as e:
        print(f'Error upgrading database: {str(e)}')
        return False

def downgrade_database():
    """Remove weather monitoring columns."""
    try:
        # Remove columns from Airport table
        with db.engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE airport
                DROP COLUMN latitude,
                DROP COLUMN longitude;
            """))
            
            # Remove columns from Flight table
            conn.execute(text("""
                ALTER TABLE flight
                DROP COLUMN postponed_count,
                DROP COLUMN weather_status,
                DROP COLUMN cancellation_reason;
            """))
            
            conn.commit()
        
        print('Successfully removed weather monitoring columns')
        return True
    except Exception as e:
        print(f'Error downgrading database: {str(e)}')
        return False

if __name__ == '__main__':
    upgrade_database()