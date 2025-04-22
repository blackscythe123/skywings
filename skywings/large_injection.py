# large_injection_optimized.py
import os
import random
import logging
from datetime import datetime, timedelta, UTC
from faker import Faker
from flask import Flask
from models import User, Airport, Aircraft, Flight, Seat, Booking, BookingDetail, Payment
from extensions import db

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_minimal_app():
    """Create a minimal Flask app just for database operations"""
    try:
        logger.info("Creating minimal Flask app")
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///flight_booking.db")
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_recycle": 300, "pool_pre_ping": True}
        db.init_app(app)
        return app
    except Exception as e:
        logger.error(f"Error creating minimal app: {str(e)}")
        raise

fake = Faker()
now = datetime(2025, 4, 19, tzinfo=UTC)

def inject_airports():
    logger.info("Starting airports injection")
    app = create_minimal_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        logger.info("Dropping and recreating all tables")

        airports_data = [
            ("JFK", "John F. Kennedy International Airport", "New York", "USA", 40.6413, -73.7781),
            ("LAX", "Los Angeles International Airport", "Los Angeles", "USA", 33.9416, -118.4085),
            ("SFO", "San Francisco International Airport", "San Francisco", "USA", 37.7749, -122.4194),
            ("ORD", "O'Hare International Airport", "Chicago", "USA", 41.9742, -87.9073),
            ("MIA", "Miami International Airport", "Miami", "USA", 25.7959, -80.2870),
            ("LHR", "Heathrow Airport", "London", "UK", 51.4700, -0.4543),
            ("CDG", "Charles de Gaulle Airport", "Paris", "France", 48.8566, 2.3522),
            ("FRA", "Frankfurt Airport", "Frankfurt", "Germany", 50.0379, 8.5622),
            ("AMS", "Amsterdam Airport Schiphol", "Amsterdam", "Netherlands", 52.3105, 4.7683),
            ("MAD", "Adolfo Suárez Madrid–Barajas Airport", "Madrid", "Spain", 40.4983, -3.5676),
            ("FCO", "Leonardo da Vinci International Airport", "Rome", "Italy", 41.8003, 12.2389),
            ("SYD", "Sydney Airport", "Sydney", "Australia", -33.9399, 151.1753),
            ("HND", "Haneda Airport", "Tokyo", "Japan", 35.5494, 139.7798),
            ("SIN", "Singapore Changi Airport", "Singapore", "Singapore", 1.3644, 103.9915),
            ("DXB", "Dubai International Airport", "Dubai", "UAE", 25.2532, 55.3657),
        ]

        airports = []
        for code, name, city, country, lat, lon in airports_data:
            airport = Airport(code=code, name=name, city=city, country=country, latitude=lat, longitude=lon)
            airports.append(airport)
        db.session.add_all(airports)
        db.session.commit()
        logger.info(f"Added {len(airports)} airports")
        return {airport.code: airport.id for airport in airports}

def inject_aircraft(airport_map):
    logger.info("Starting aircraft injection")
    app = create_minimal_app()
    with app.app_context():
        aircraft_data = [
            ("Boeing 737-800", "N12345", 150, 12, 8),
            ("Airbus A320", "N54321", 140, 10, 6),
            ("Boeing 777-300ER", "N77733", 300, 40, 10),
            ("Airbus A380", "N38080", 420, 60, 14),
        ]

        aircrafts = []
        for model, reg, eco, bus, first in aircraft_data:
            aircraft = Aircraft(model=model, registration=reg, economy_seats=eco, business_seats=bus, first_class_seats=first)
            aircrafts.append(aircraft)
        db.session.add_all(aircrafts)
        db.session.commit()
        logger.info(f"Added {len(aircrafts)} aircraft")
        return {aircraft.registration: aircraft.id for aircraft in aircrafts}

def inject_users(airport_map, aircraft_map):
    logger.info("Starting users injection")
    app = create_minimal_app()
    with app.app_context():
        default_users = [
            ("johndoe", "john@example.com", "John", "Doe", "Gold", 25000, False),
            ("janedoe", "jane@example.com", "Jane", "Doe", "Silver", 12000, False),
            ("admin", "admin@example.com", "Admin", "User", "Platinum", 50000, True),
        ]

        users = []
        for username, email, fname, lname, status, miles, is_admin in default_users:
            user = User(
                username=username,
                email=email,
                first_name=fname,
                last_name=lname,
                frequent_flyer_status=status,
                frequent_flyer_miles=miles,
                date_joined=datetime.now(UTC),
                is_admin=is_admin,
            )
            user.set_password("password123" if not is_admin else "adminpass123")
            users.append(user)

        statuses = ["Standard", "Silver", "Gold", "Platinum"]
        for i in range(97):
            username = fake.user_name() + str(i)
            email = fake.email()
            user = User(
                username=username,
                email=email,
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=80),
                phone_number=fake.phone_number(),
                address=fake.address(),
                passport_number=fake.bothify(text='??######', letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
                nationality=fake.country(),
                frequent_flyer_status=random.choice(statuses),
                frequent_flyer_miles=random.randint(0, 50000),
                date_joined=fake.date_time_between(start_date="-3m", end_date="now").replace(tzinfo=UTC),
                is_admin=False,
            )
            user.set_password("password123")
            users.append(user)
        
        db.session.add_all(users)
        db.session.commit()
        logger.info(f"Added {len(users)} users")
        return User.query.all()

def inject_flights(airport_map, aircraft_map, users):
    logger.info("Starting flights injection")
    app = create_minimal_app()
    with app.app_context():
        now = datetime.now()
        flights_data = [
            ("AA", "JFK", "LAX", 199.99, 499.99, 999.99),
            ("AA", "LAX", "JFK", 219.99, 519.99, 1019.99),
            ("UA", "SFO", "ORD", 179.99, 479.99, 879.99),
            ("UA", "ORD", "SFO", 189.99, 489.99, 889.99),
            ("BA", "JFK", "LHR", 599.99, 1499.99, 2999.99),
            ("BA", "LHR", "JFK", 629.99, 1529.99, 3029.99),
            ("LH", "LHR", "FRA", 249.99, 649.99, 1249.99),
            ("LH", "FRA", "LHR", 269.99, 669.99, 1269.99),
            ("SQ", "SIN", "HND", 499.99, 1299.99, 2499.99),
            ("SQ", "HND", "SIN", 519.99, 1319.99, 2519.99),
            ("EK", "DXB", "SYD", 799.99, 1999.99, 3999.99),
            ("EK", "SYD", "DXB", 829.99, 2029.99, 4029.99),
            ("AF", "CDG", "MIA", 549.99, 1399.99, 2799.99),
            ("AF", "MIA", "CDG", 579.99, 1429.99, 2829.99),
            ("KL", "AMS", "FCO", 299.99, 799.99, 1499.99),
            ("KL", "FCO", "AMS", 319.99, 819.99, 1519.99),
        ]

        flights = []
        for day in range(30):
            flight_date = now + timedelta(days=day)
            for airline, origin, dest, eco_price, bus_price, first_price in flights_data:
                flight_num = f"{airline}{random.randint(100, 999)}"
                dep_hour = random.randint(0, 23)
                dep_minute = random.choice([0, 15, 30, 45])
                departure_time = flight_date.replace(hour=dep_hour, minute=dep_minute, second=0, microsecond=0)
                duration = random.randint(2, 14)
                arrival_time = departure_time + timedelta(hours=duration)
                aircraft_reg = random.choice(list(aircraft_map.keys()))

                flight = Flight(
                    flight_number=flight_num,
                    origin_id=airport_map[origin],
                    destination_id=airport_map[dest],
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    aircraft_id=aircraft_map[aircraft_reg],
                    economy_base_price=eco_price,
                    business_base_price=bus_price,
                    first_class_base_price=first_price,
                    status="Scheduled",
                )
                flights.append(flight)

        for day in range(-90, 0):
            flight_date = now + timedelta(days=day)
            for airline, origin, dest, eco_price, bus_price, first_price in flights_data:
                flight_num = f"{airline}{random.randint(100, 999)}"
                dep_hour = random.randint(0, 23)
                dep_minute = random.choice([0, 15, 30, 45])
                departure_time = flight_date.replace(hour=dep_hour, minute=dep_minute, second=0, microsecond=0)
                duration = random.randint(2, 14)
                arrival_time = departure_time + timedelta(hours=duration)
                aircraft_reg = random.choice(list(aircraft_map.keys()))

                flight = Flight(
                    flight_number=flight_num,
                    origin_id=airport_map[origin],
                    destination_id=airport_map[dest],
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    aircraft_id=aircraft_map[aircraft_reg],
                    economy_base_price=eco_price,
                    business_base_price=bus_price,
                    first_class_base_price=first_price,
                    status="Departed" if departure_time < now else "Scheduled",
                )
                flights.append(flight)
        
        db.session.add_all(flights[:len(flights)//2])  # Commit half the flights
        db.session.commit()
        db.session.add_all(flights[len(flights)//2:])  # Commit the other half
        db.session.commit()
        logger.info(f"Added {len(flights)} flights")
        return Flight.query.all()

def inject_seats(flights):
    logger.info("Starting seats injection")
    app = create_minimal_app()
    with app.app_context():
        seats = []
        for flight in flights[:len(flights)//2]:  # Process half the flights
            aircraft = db.session.get(Aircraft, flight.aircraft_id)
            for i in range(1, aircraft.economy_seats + 1):
                row = (i - 1) // 6 + 10
                col = chr(65 + ((i - 1) % 6))
                seat = Seat(flight_id=flight.id, seat_number=f"{row}{col}", seat_class="Economy", is_booked=False)
                seats.append(seat)
            for i in range(1, aircraft.business_seats + 1):
                row = (i - 1) // 4 + 3
                col = chr(65 + ((i - 1) % 4))
                seat = Seat(flight_id=flight.id, seat_number=f"{row}{col}", seat_class="Business", is_booked=False)
                seats.append(seat)
            for i in range(1, aircraft.first_class_seats + 1):
                row = (i - 1) // 2 + 1
                col = chr(65 + ((i - 1) % 2) * 3)
                seat = Seat(flight_id=flight.id, seat_number=f"{row}{col}", seat_class="First Class", is_booked=False)
                seats.append(seat)
        db.session.add_all(seats)
        db.session.commit()
        logger.info(f"Added {len(seats)} seats for first half of flights")

        seats = []
        for flight in flights[len(flights)//2:]:  # Process the other half
            aircraft = db.session.get(Aircraft, flight.aircraft_id)
            for i in range(1, aircraft.economy_seats + 1):
                row = (i - 1) // 6 + 10
                col = chr(65 + ((i - 1) % 6))
                seat = Seat(flight_id=flight.id, seat_number=f"{row}{col}", seat_class="Economy", is_booked=False)
                seats.append(seat)
            for i in range(1, aircraft.business_seats + 1):
                row = (i - 1) // 4 + 3
                col = chr(65 + ((i - 1) % 4))
                seat = Seat(flight_id=flight.id, seat_number=f"{row}{col}", seat_class="Business", is_booked=False)
                seats.append(seat)
            for i in range(1, aircraft.first_class_seats + 1):
                row = (i - 1) // 2 + 1
                col = chr(65 + ((i - 1) % 2) * 3)
                seat = Seat(flight_id=flight.id, seat_number=f"{row}{col}", seat_class="First Class", is_booked=False)
                seats.append(seat)
        db.session.add_all(seats)
        db.session.commit()
        logger.info(f"Added {len(seats)} seats for second half of flights")
        return Seat.query.filter_by(is_booked=False).all()

# ... (previous imports and functions remain unchanged until inject_bookings)

def inject_bookings():
    logger.info("Starting bookings injection")
    app = create_minimal_app()
    with app.app_context():
        users = User.query.all()
        seat_classes = ["Economy", "Business", "First Class"]
        booking_statuses = ["Reserved", "Confirmed", "Cancelled"]
        payment_statuses = ["Pending", "Paid", "Refunded"]

        # Process all flights
        flights = Flight.query.all()
        booking_counter = 1

        for flight in flights:
            aircraft = db.session.get(Aircraft, flight.aircraft_id)
            total_seats = aircraft.economy_seats + aircraft.business_seats + aircraft.first_class_seats
            target_booked_seats = int(total_seats * 0.7)
            current_booked_seats = Seat.query.filter_by(flight_id=flight.id, is_booked=True).count()

            if current_booked_seats >= target_booked_seats:
                continue

            seats_to_book = target_booked_seats - current_booked_seats
            available_seats = Seat.query.filter_by(flight_id=flight.id, is_booked=False).all()

            if not available_seats:
                continue

            for _ in range(min(seats_to_book, len(available_seats))):
                seat = random.choice(available_seats)
                available_seats.remove(seat)
                seat_class = seat.seat_class

                user = random.choice(users)
                flight_departure_time = flight.departure_time.replace(tzinfo=UTC) if flight.departure_time else now
                booking_date = fake.date_time_between(
                    start_date="-90d" if flight_departure_time < now else "-30d",
                    end_date=min(flight_departure_time, now)
                ).replace(tzinfo=UTC)
                booking_ref = f"BOOK{booking_counter:04d}"
                booking_counter += 1

                if Booking.query.filter_by(booking_reference=booking_ref).first():
                    continue

                days_before = max(0, (flight_departure_time - booking_date).days)
                price = flight.calculate_price(seat_class, days_before)

                # Randomly assign status, but ensure some are Cancelled for refunds
                status = random.choices(
                    ["Confirmed", "Cancelled", "Reserved"],
                    weights=[0.7, 0.2, 0.1]
                )[0]
                payment_status = "Paid" if status == "Confirmed" else ("Refunded" if status == "Cancelled" else random.choice(payment_statuses))

                booking = Booking(
                    booking_reference=booking_ref,
                    user_id=user.id,
                    flight_id=flight.id,
                    booking_date=booking_date,
                    status=status,
                    total_price=price,
                    payment_status=payment_status
                )
                db.session.add(booking)
                db.session.flush()

                seat.is_booked = True
                db.session.merge(seat)

                booking_detail = BookingDetail(
                    booking_id=booking.id,
                    seat_id=seat.id,
                    passenger_first_name=fake.first_name(),
                    passenger_last_name=fake.last_name(),
                    passenger_dob=fake.date_of_birth(minimum_age=0, maximum_age=80),
                    passenger_passport=fake.bothify(text='??######', letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
                    passenger_nationality=fake.country(),
                    special_requests=random.choice([None, "Vegetarian meal", "Wheelchair assistance", "Extra legroom"]),
                    price=price
                )
                db.session.add(booking_detail)

                # Always create a payment record for Confirmed and Cancelled (Refunded) bookings
                if payment_status == "Paid":
                    payment = Payment(
                        booking_id=booking.id,
                        amount=price,
                        payment_date=booking_date,
                        payment_method=random.choice(["Credit Card", "Debit Card", "PayPal"]),
                        transaction_id=fake.bothify(text='TXN-####-####'),
                        status="Completed"
                    )
                    db.session.add(payment)
                elif payment_status == "Refunded":
                    # Add a negative payment for refund
                    payment = Payment(
                        booking_id=booking.id,
                        amount=-price,
                        payment_date=booking_date + timedelta(days=random.randint(1, 10)),
                        payment_method=random.choice(["Credit Card", "Debit Card", "PayPal"]),
                        transaction_id=fake.bothify(text='REF-####-####'),
                        status="Refunded"
                    )
                    db.session.add(payment)

            db.session.commit()
            logger.info(f"Added bookings for flight {flight.flight_number}")

def print_summary():
    logger.info("Printing summary")
    app = create_minimal_app()
    with app.app_context():
        print("\nCombined data successfully injected into the database:")
        print(f"- {User.query.count()} Users")
        print(f"- {Airport.query.count()} Airports")
        print(f"- {Aircraft.query.count()} Aircraft")
        print(f"- {Flight.query.count()} Flights")
        print(f"- {Seat.query.count()} Seats")
        print(f"- {Booking.query.count()} Bookings")
        print(f"- {BookingDetail.query.count()} Booking Details")
        print(f"- {Payment.query.count()} Payments")
        logger.info("Data injection completed successfully")

if __name__ == "__main__":
    try:
        logger.info("Starting large_injection_optimized.py")
        airport_map = inject_airports()
        aircraft_map = inject_aircraft(airport_map)
        users = inject_users(airport_map, aircraft_map)
        flights = inject_flights(airport_map, aircraft_map, users)
        available_seats = inject_seats(flights)
        inject_bookings()  # Removed arguments
        print_summary()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        raise