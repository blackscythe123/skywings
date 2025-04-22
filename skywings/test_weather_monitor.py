import logging
from datetime import datetime, timedelta
from threading import Thread
import time
from extensions import db
from models import Flight, Airport, User
from weather_service import WeatherService
from flask_mail import Message
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from sqlalchemy.exc import OperationalError

class TestWeatherMonitor:
    def __init__(self, app, mail):
        self.app = app
        self.weather_service = WeatherService()
        self.mail = mail
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.flight_counter = 0  # Add a counter to track flight processing order

    def check_flight_weather(self, flight):
        self.flight_counter += 1
        
        # First flight: Postponed
        if self.flight_counter == 1:
            return False, "Simulated bad weather - flight will be postponed"
        
        # Second flight: Cancelled
        elif self.flight_counter == 2:
            return False, "Simulated severe weather - flight will be cancelled"
        # All other flights: Safe
        else:
            return True, "Weather is safe"

    # ... [rest of the class remains the same] ...
    def monitor_weather(self):
        with self.app.app_context():
            try:
                current_time = datetime.now()
                end_time = current_time + timedelta(hours=12)
                self.logger.info(f"Checking weather for flights from {current_time} to {end_time}")

                upcoming_flights = db.session.query(Flight).filter(
                    Flight.departure_time >= current_time,
                    Flight.departure_time <= end_time,
                    Flight.status == "Scheduled"
                ).all()

                self.logger.info("=== Scheduled Flights Summary (Next 12 Hours) ===")
                if not upcoming_flights:
                    self.logger.info("No flights scheduled in the next 12 hours.")
                else:
                    for flight in upcoming_flights:
                        weather_safe, weather_message = self.check_flight_weather(flight)

                        origin_weather = {
                            'coord': {'lon': flight.origin_airport.longitude, 'lat': flight.origin_airport.latitude},
                            'weather': [{'id': 500, 'main': 'Rain', 'description': 'heavy rain', 'icon': '10d'}],
                            'main': {'temp': 15.0, 'feels_like': 14.0, 'pressure': 1010, 'humidity': 80, 'visibility': 800},
                            'wind': {'speed': 16.0, 'deg': 180, 'gust': 20.0},
                            'sys': {'country': 'XX'}
                        }
                        dest_weather = {
                            'coord': {'lon': flight.destination_airport.longitude, 'lat': flight.destination_airport.latitude},
                            'weather': [{'id': 500, 'main': 'Rain', 'description': 'heavy rain', 'icon': '10d'}],
                            'main': {'temp': 10.0, 'feels_like': 9.0, 'pressure': 1005, 'humidity': 85, 'visibility': 900},
                            'wind': {'speed': 17.0, 'deg': 190, 'gust': 22.0},
                            'sys': {'country': 'YY'}
                        }

                        print(f"\nOrganized Weather Data for Flight {flight.flight_number}")
                        print("Flight Number:", flight.flight_number)
                        print("Route:")
                        print(f"  Origin: {flight.origin_airport.code} ({flight.origin_airport.city}, {origin_weather.get('sys', {}).get('country', 'Unknown')})")
                        print(f"  Destination: {flight.destination_airport.code} ({flight.destination_airport.city}, {dest_weather.get('sys', {}).get('country', 'Unknown')})")
                        
                        if not weather_safe:
                            self.process_flight_update(flight, weather_message, flight.postponed_count > 0)

                        self.logger.info(f"- Flight {flight.flight_number}: {flight.origin_airport.city} ({flight.origin_airport.code}) to {flight.destination_airport.city} ({flight.destination_airport.code}), Departure: {flight.departure_time.strftime('%Y-%m-%d %H:%M:%S')}, Weather Status: {'Safe' if weather_safe else weather_message}")

                db.session.commit()
            except Exception as e:
                self.logger.error(f"Weather monitoring error: {str(e)}")
                db.session.rollback()

    def run_continuously(self):
        self.monitor_weather()
        self.logger.info("Weather monitor completed single run")

    def start(self):
        self.logger.info("Starting weather monitor for single run")
        self.thread = Thread(target=self.run_continuously, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Weather monitor stopped")

    def process_flight_update(self, flight, weather_message, is_postponed):
        with self.app.app_context():
            try:
                with db.session.no_autoflush:
                    if is_postponed and flight.postponed_count > 0:
                        # Cancellation logic
                        flight.status = "Cancelled"
                        action_message = f"Cancelled due to repeated weather issues. 100% refund issued."
                        self.logger.info(f"Flight {flight.flight_number} {action_message}")
                    else:
                        # Postponement logic
                        flight.departure_time += timedelta(hours=4)
                        flight.arrival_time += timedelta(hours=4)
                        flight.status = "Postponed"
                        flight.postponed_count += 1
                        action_message = f"Postponed due to weather: {weather_message}. New departure: {flight.departure_time}"

                    email_count = 0
                    max_emails = 3
                    
                    for booking in flight.bookings:
                        if booking.user.email and booking.user.booking_notifications:
                            if email_count < max_emails:
                                self.send_weather_email(booking.user, flight, weather_message, flight.status)
                                email_count += 1
                                self.logger.info(f"Sent email to {booking.user.email} (email {email_count} of {max_emails})")
                            else:
                                self.logger.info(f"Skipping email to {booking.user.email} (reached max of {max_emails} emails)")

                    db.session.commit()
            except Exception as e:
                self.logger.error(f"Error updating flight {flight.flight_number}: {str(e)}")
                db.session.rollback()
                raise

    def send_weather_email(self, user, flight, weather_message, new_status):
        with self.app.app_context():
            try:
                subject = f"Flight {flight.flight_number} {new_status}"
                sender = self.app.config['MAIL_DEFAULT_SENDER']
                
                if new_status == "Cancelled":
                    message = f"""Dear {user.first_name},

    We regret to inform you that your flight has been CANCELLED due to severe weather conditions.

    Flight Details:
    - Number: {flight.flight_number}
    - Route: {flight.origin_airport.city} ({flight.origin_airport.code}) to {flight.destination_airport.city} ({flight.destination_airport.code})
    - Original Departure: {flight.departure_time}

    IMPORTANT: A 100% refund will be processed automatically within 5-7 business days.

    We sincerely apologize for this inconvenience and appreciate your understanding.

    Best regards,
    SkyWings Team"""
                elif new_status == "Postponed" :
                    message = f"""Dear {user.first_name},

    Your flight has been POSTPONED due to adverse weather conditions ({weather_message}).

    Updated Flight Details:
    - Number: {flight.flight_number}
    - Route: {flight.origin_airport.city} ({flight.origin_airport.code}) to {flight.destination_airport.city} ({flight.destination_airport.code})
    - New Departure: {flight.departure_time}
    - New Arrival: {flight.arrival_time}

    Your existing booking remains valid for the rescheduled flight. If the new time is inconvenient, you may request a full refund through our website.

    We apologize for any inconvenience this may cause.

    Best regards,
    SkyWings Team"""

                msg = Message(subject=subject, sender=sender, recipients=[user.email], body=message)
                Thread(target=self._send_email_async, args=(self.app, msg)).start()
            except Exception as e:
                self.logger.error(f"Failed to send weather email to {user.email}: {str(e)}")

    def _send_email_async(self, app, msg):
        with app.app_context():
            try:
                self.mail.send(msg)
            except Exception as e:
                self.logger.error(f"Async email send failed: {str(e)}")

def init_test_weather_monitor(app):
    from extensions import mail
    monitor = TestWeatherMonitor(app, mail)
    monitor.start()
    return monitor
