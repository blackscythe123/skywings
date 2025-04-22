# weather_monitor.py
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

class WeatherMonitor:
    def __init__(self, app, mail):
        self.app = app
        self.weather_service = WeatherService()
        self.mail = mail
        self.logger = logging.getLogger(__name__)
        self.running = False

    @retry(retry=retry_if_exception_type(OperationalError), stop=stop_after_attempt(3), wait=wait_fixed(1))
    def check_flight_weather(self, flight):
        try:
            origin_weather = self.weather_service.get_weather_by_coordinates(
                flight.origin_airport.latitude, flight.origin_airport.longitude)
            dest_weather = self.weather_service.get_weather_by_coordinates(
                flight.destination_airport.latitude, flight.destination_airport.longitude)

            is_safe = True
            message = ""
            for weather in [origin_weather, dest_weather]:
                if weather.get("cod") != 200:
                    return True, "Weather data unavailable"
                condition = weather.get("weather", [{}])[0].get("main", "").lower()
                if condition in ["thunderstorm", "snow", "tornado"]:
                    is_safe = False
                    message = f"Unsafe weather condition: {condition}"
                    break
                wind_speed = weather.get("wind", {}).get("speed", 0)
                if wind_speed > 20:
                    is_safe = False
                    message = f"High wind speed: {wind_speed} m/s"
                    break

            # self.logger.debug(f"Weather for flight {flight.flight_number}: "
            #                 f"Origin ({flight.origin_airport.code}): {origin_weather}, "
            #                 f"Destination ({flight.destination_airport.code}): {dest_weather}")
            return is_safe, message
        except Exception as e:
            self.logger.error(f"Error checking weather for flight {flight.flight_number}: {str(e)}")
            return True, "Weather API error"


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
                        origin_weather = self.weather_service.get_weather_by_coordinates(
                            flight.origin_airport.latitude, flight.origin_airport.longitude)
                        dest_weather = self.weather_service.get_weather_by_coordinates(
                            flight.destination_airport.latitude, flight.destination_airport.longitude)

                        # Structured terminal output for each flight
                        print(f"\nOrganized Weather Data for Flight {flight.flight_number}")
                        print("Flight Number:", flight.flight_number)
                        print("Route:")
                        print(f"  Origin: {flight.origin_airport.code} ({flight.origin_airport.city}, {origin_weather.get('sys', {}).get('country', 'Unknown')})")
                        print(f"  Destination: {flight.destination_airport.code} ({flight.destination_airport.city}, {dest_weather.get('sys', {}).get('country', 'Unknown')})")
                        print("Origin Weather Data:")
                        print(f"  Coordinates: ({origin_weather.get('coord', {}).get('lon', 'N/A')}, {origin_weather.get('coord', {}).get('lat', 'N/A')})")
                        print(f"  Weather Condition: {origin_weather.get('weather', [{}])[0].get('description', 'N/A')}")
                        print(f"  Icon: {origin_weather.get('weather', [{}])[0].get('icon', 'N/A')}")
                        print(f"  Temperature: {origin_weather.get('main', {}).get('temp', 'N/A')}°C")
                        print(f"  Feels Like: {origin_weather.get('main', {}).get('feels_like', 'N/A')}°C")
                        print(f"  Temperature Range: {origin_weather.get('main', {}).get('temp_min', 'N/A')}°C (min) to {origin_weather.get('main', {}).get('temp_max', 'N/A')}°C (max)")
                        print(f"  Pressure: {origin_weather.get('main', {}).get('pressure', 'N/A')} hPa (sea level), {origin_weather.get('main', {}).get('grnd_level', 'N/A')} hPa (ground level)")
                        print(f"  Humidity: {origin_weather.get('main', {}).get('humidity', 'N/A')}%")
                        print(f"  Visibility: {origin_weather.get('visibility', 'N/A')} meters")
                        print(f"  Wind: Speed {origin_weather.get('wind', {}).get('speed', 'N/A')} m/s, Direction {origin_weather.get('wind', {}).get('deg', 'N/A')}°, Gust {origin_weather.get('wind', {}).get('gust', 'N/A')} m/s")
                        print(f"  Cloud Cover: {origin_weather.get('clouds', {}).get('all', 'N/A')}%")
                        print(f"  Timestamp: {origin_weather.get('dt', 'N/A')}")
                        print(f"  Sunrise: {origin_weather.get('sys', {}).get('sunrise', 'N/A')}")
                        print(f"  Sunset: {origin_weather.get('sys', {}).get('sunset', 'N/A')}")
                        print(f"  Timezone: {origin_weather.get('timezone', 'N/A')} seconds")
                        print(f"  Location ID: {origin_weather.get('id', 'N/A')}")
                        print(f"  Location Name: {origin_weather.get('name', 'N/A')}")
                        print(f"  Country Code: {origin_weather.get('sys', {}).get('country', 'N/A')}")
                        print(f"  Response Code: {origin_weather.get('cod', 'N/A')}")
                        print("Destination Weather Data:")
                        print(f"  Coordinates: ({dest_weather.get('coord', {}).get('lon', 'N/A')}, {dest_weather.get('coord', {}).get('lat', 'N/A')})")
                        print(f"  Weather Condition: {dest_weather.get('weather', [{}])[0].get('description', 'N/A')}")
                        print(f"  Icon: {dest_weather.get('weather', [{}])[0].get('icon', 'N/A')}")
                        print(f"  Temperature: {dest_weather.get('main', {}).get('temp', 'N/A')}°C")
                        print(f"  Feels Like: {dest_weather.get('main', {}).get('feels_like', 'N/A')}°C")
                        print(f"  Temperature Range: {dest_weather.get('main', {}).get('temp_min', 'N/A')}°C (min) to {dest_weather.get('main', {}).get('temp_max', 'N/A')}°C (max)")
                        print(f"  Pressure: {dest_weather.get('main', {}).get('pressure', 'N/A')} hPa (sea level), {dest_weather.get('main', {}).get('grnd_level', 'N/A')} hPa (ground level)")
                        print(f"  Humidity: {dest_weather.get('main', {}).get('humidity', 'N/A')}%")
                        print(f"  Visibility: {dest_weather.get('visibility', 'N/A')} meters")
                        print(f"  Wind: Speed {dest_weather.get('wind', {}).get('speed', 'N/A')} m/s, Direction {dest_weather.get('wind', {}).get('deg', 'N/A')}°, Gust {dest_weather.get('wind', {}).get('gust', 'N/A')} m/s")
                        print(f"  Cloud Cover: {dest_weather.get('clouds', {}).get('all', 'N/A')}%")
                        print(f"  Timestamp: {dest_weather.get('dt', 'N/A')}")
                        print(f"  Sunrise: {dest_weather.get('sys', {}).get('sunrise', 'N/A')}")
                        print(f"  Sunset: {dest_weather.get('sys', {}).get('sunset', 'N/A')}")
                        print(f"  Timezone: {dest_weather.get('timezone', 'N/A')} seconds")
                        print(f"  Location ID: {dest_weather.get('id', 'N/A')}")
                        print(f"  Location Name: {dest_weather.get('name', 'N/A')}")
                        print(f"  Country Code: {dest_weather.get('sys', {}).get('country', 'N/A')}")
                        print(f"  Response Code: {dest_weather.get('cod', 'N/A')}")
                        self.logger.info(f"- Flight {flight.flight_number}: {flight.origin_airport.city} ({flight.origin_airport.code}) to {flight.destination_airport.city} ({flight.destination_airport.code}), Departure: {flight.departure_time.strftime('%Y-%m-%d %H:%M:%S')}, Weather Status: {'Safe' if weather_safe else weather_message}")

                updated_flights = 0
                for flight in upcoming_flights:
                    weather_safe, weather_message = self.check_flight_weather(flight)
                    if not weather_safe and weather_message not in ["Weather data unavailable", "Weather API error"]:
                        self.process_flight_update(flight, weather_message, flight.postponed_count > 0)
                        updated_flights += 1

                db.session.commit()
                self.logger.info(f"Weather monitoring completed: {updated_flights} flights updated")
            except Exception as e:
                self.logger.error(f"Weather monitoring error: {str(e)}")
                db.session.rollback()

# ... (rest of the class remains unchanged)

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
                        flight.status = "Cancelled"
                        self.logger.info(f"Flight {flight.flight_number} cancelled due to repeated weather issues")
                        self.logger.info(f"100% refund issued for flight {flight.flight_number} to all passengers")
                    else:
                        flight.departure_time += timedelta(hours=4)
                        flight.arrival_time += timedelta(hours=4)
                        flight.status = "Postponed"
                        flight.postponed_count += 1
                        self.logger.info(f"Flight {flight.flight_number} postponed due to weather: {weather_message}")

                    for booking in flight.bookings:
                        if booking.user.email and booking.user.booking_notifications:
                            self.send_weather_email(booking.user, flight, weather_message, flight.status)

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
                message = f"""Dear {user.first_name},

Due to adverse weather conditions ({weather_message}), your flight has been {new_status.lower()}.

Flight: {flight.flight_number}
From: {flight.origin_airport.city} ({flight.origin_airport.code})
To: {flight.destination_airport.city} ({flight.destination_airport.code})
New Departure: {flight.departure_time if new_status == 'Postponed' else 'N/A'}
{'100% refund issued' if new_status == 'Cancelled' else ''}

We apologize for the inconvenience.

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

def init_weather_monitor(app):
    from extensions import mail
    monitor = WeatherMonitor(app, mail)
    monitor.start()
    return monitor