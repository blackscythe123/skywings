from app import app, db
from sqlalchemy import text

def run_migration():
    """Add new columns for weather monitoring."""
    with app.app_context():
        try:
            # Add weather-related columns to Flight table one by one
            with db.engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE flight ADD COLUMN postponed_count INTEGER DEFAULT 0;"))
                except Exception as e:
                    if 'duplicate column name' not in str(e).lower():
                        raise e
                
                try:
                    conn.execute(text("ALTER TABLE flight ADD COLUMN weather_status VARCHAR(500);"))
                except Exception as e:
                    if 'duplicate column name' not in str(e).lower():
                        raise e
                
                try:
                    conn.execute(text("ALTER TABLE flight ADD COLUMN cancellation_reason VARCHAR(500);"))
                except Exception as e:
                    if 'duplicate column name' not in str(e).lower():
                        raise e
                
                conn.commit()
            
            print('Successfully added weather monitoring columns')
            return True
        except Exception as e:
            print(f'Error upgrading database: {str(e)}')
            return False

if __name__ == '__main__':
    run_migration()