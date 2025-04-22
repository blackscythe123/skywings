# flight_status_updater.py
from extensions import db
from models import Flight, Airport
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from flask_mail import Message
from threading import Thread
import time

class FlightStatusUpdater:
    def __init__(self, app, mail):
        self.app = app
        self.mail = mail
        self.logger = logging.getLogger(__name__)
        self.running = False

    def update_flight_statuses(self):
        with self.app.app_context():
            try:
                self.logger.info(f"Starting flight status update at {datetime.now()}")
                current_time = datetime.now()
                past_flights = db.session.query(Flight).options(
                    joinedload(Flight.origin_airport),
                    joinedload(Flight.destination_airport)
                ).filter(Flight.departure_time < current_time, 
                         Flight.status != "Completed").with_for_update().all()

                updated_flights = 0
                for flight in past_flights:
                    flight.status = "Completed"
                    updated_flights += 1
                    self.logger.info(f"Updated flight {flight.flight_number} to status 'Completed'")

                db.session.commit()
                self.logger.info(f"Flight status update completed: {updated_flights} flights marked as Completed")
                
                print(f"\nFlight Status Update Summary ({datetime.now()}):")
                if updated_flights > 0:
                    print(f"Marked {updated_flights} flights as Completed")
                else:
                    print("No past flights needed updating")
            except Exception as e:
                self.logger.error(f"Error in update_flight_statuses: {str(e)}")
                db.session.rollback()

    def run_continuously(self):
        self.running = True
        self.logger.info("Flight status updater loop started")
        while self.running:
            try:
                self.update_flight_statuses()
                self.logger.debug("Flight status check completed, waiting for next cycle")
            except Exception as e:
                self.logger.error(f"Error in flight status updater: {str(e)}")
            
            # Wait 5 minutes before next check
            time.sleep(300)

    def start(self):
        self.logger.info("Starting continuous flight status updater")
        self.thread = Thread(target=self.run_continuously, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Flight status updater stopped")

def init_flight_status_updater(app):
    from extensions import mail
    updater = FlightStatusUpdater(app, mail)
    updater.start()
    return updater