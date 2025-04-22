"""
Script to fix frequent flyer status for all users based on their miles.
Usage: Run this script with your Flask app context.
"""

from extensions import db
from models import User

def fix_frequent_flyer_status():
    users = User.query.all()
    updated = 0
    for user in users:
        miles = user.frequent_flyer_miles or 0
        if miles >= 50000:
            correct_status = "Platinum"
        elif miles >= 25000:
            correct_status = "Gold"
        elif miles >= 10000:
            correct_status = "Silver"
        else:
            correct_status = "Standard"
        if user.frequent_flyer_status != correct_status:
            user.frequent_flyer_status = correct_status
            updated += 1
    db.session.commit()
    print(f"Updated {updated} users' frequent flyer status.")

if __name__ == "__main__":
    from app import app
    with app.app_context():
        fix_frequent_flyer_status()
