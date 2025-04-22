import random
from datetime import datetime, timedelta
from faker import Faker
from flask import Flask
from extensions import db
from models import User, Airport, Aircraft, Flight, Booking, Seat, BookingDetail
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///flight_booking.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_recycle": 300, "pool_pre_ping": True}
db.init_app(app)

fake = Faker()

# Add new data within application context
with app.app_context():
    # Create 5 new users
    users = []
    for _ in range(5):
        user = User(
            username=fake.user_name(),
            email=fake.email(),
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            date_joined=fake.date_time_between(start_date="-3m", end_date="now"),
            booking_notifications=True
        )
        user.set_password(fake.password())
        users.append(user)
    db.session.add_all(users)
    db.session.commit()

    # Create 4 new airports
    airports = [
        Airport(code="SFO", name="San Francisco International Airport", city="San Francisco", country="USA", latitude=37.6213, longitude=-122.3789),
        Airport(code="DXB", name="Dubai International Airport", city="Dubai", country="UAE", latitude=25.2528, longitude=55.3644),
        Airport(code="SYD", name="Sydney Kingsford Smith Airport", city="Sydney", country="Australia", latitude=-33.9461, longitude=151.1772),
        Airport(code="HND", name="Haneda Airport", city="Tokyo", country="Japan", latitude=35.5533, longitude=139.7811)
    ]
    db.session.add_all(airports)
    db.session.commit()

    # Create 2 new aircraft
    aircraft = [
        Aircraft(model="Boeing 787", registration=fake.unique.bothify("N#####"), 
                 economy_seats=200, business_seats=40, first_class_seats=10),
        Aircraft(model="Airbus A350", registration=fake.unique.bothify("N#####"),
                 economy_seats=250, business_seats=50, first_class_seats=12)
    ]
    db.session.add_all(aircraft)
    db.session.commit()

    # Create 3 new flights in the specified period (2025-04-18 22:06:18 to 2025-04-19 22:06:18)
    base_time = datetime(2025, 4, 18, 22, 6, 18)
    flights = [
        Flight(
            flight_number="SQ901",
            origin_id=airports[0].id,  # SFO
            destination_id=airports[1].id,  # DXB
            departure_time=base_time + timedelta(hours=3),  # 2025-04-19 01:06:18
            arrival_time=base_time + timedelta(hours=12),   # 2025-04-19 10:06:18
            aircraft_id=aircraft[0].id,
            economy_base_price=600.00,
            business_base_price=1500.00,
            first_class_base_price=3000.00,
            status="Scheduled",
            postponed_count=0
        ),
        Flight(
            flight_number="QF005",
            origin_id=airports[2].id,  # SYD
            destination_id=airports[3].id,  # HND
            departure_time=base_time + timedelta(hours=7),  # 2025-04-19 05:06:18
            arrival_time=base_time + timedelta(hours=15),  # 2025-04-19 13:06:18
            aircraft_id=aircraft[1].id,
            economy_base_price=700.00,
            business_base_price=1800.00,
            first_class_base_price=3500.00,
            status="Scheduled",
            postponed_count=0
        ),
        Flight(
            flight_number="EK407",
            origin_id=airports[1].id,  # DXB
            destination_id=airports[0].id,  # SFO
            departure_time=base_time + timedelta(hours=11), # 2025-04-19 09:06:18
            arrival_time=base_time + timedelta(hours=19),  # 2025-04-19 17:06:18
            aircraft_id=aircraft[0].id,
            economy_base_price=650.00,
            business_base_price=1600.00,
            first_class_base_price=3200.00,
            status="Scheduled",
            postponed_count=0
        )
    ]
    db.session.add_all(flights)
    db.session.commit()

    # Create seats for each new flight
    for flight in flights:
        # Create economy seats
        for i in range(1, 31):
            seat = Seat(
                flight_id=flight.id,
                seat_number=f"{i}A",
                seat_class="Economy",
                is_booked=False
            )
            db.session.add(seat)
        # Create business seats
        for i in range(1, 7):
            seat = Seat(
                flight_id=flight.id,
                seat_number=f"{i}B",
                seat_class="Business",
                is_booked=False
            )
            db.session.add(seat)
        # Create first class seats
        for i in range(1, 3):
            seat = Seat(
                flight_id=flight.id,
                seat_number=f"{i}F",
                seat_class="First Class",
                is_booked=False
            )
            db.session.add(seat)
    db.session.commit()

    # Create 6 new bookings (2 per flight)
    for i, flight in enumerate(flights):
        for _ in range(2):
            # Find an available seat
            seat = Seat.query.filter_by(flight_id=flight.id, is_booked=False).first()
            if not seat:
                continue
                
            seat.is_booked = True
            
            booking = Booking(
                booking_reference=fake.unique.bothify("??######"),
                user_id=users[i % len(users)].id,
                flight_id=flight.id,
                booking_date=datetime.now(),
                total_price=flight.economy_base_price * 1.2,  # Example price calculation
                status="Confirmed",
                payment_status="Paid"
            )
            db.session.add(booking)
            db.session.flush()  # To get the booking ID
            
            booking_detail = BookingDetail(
                booking_id=booking.id,
                seat_id=seat.id,
                passenger_first_name=fake.first_name(),
                passenger_last_name=fake.last_name(),
                passenger_dob=fake.date_of_birth(minimum_age=18, maximum_age=90),
                passenger_passport=fake.bothify("#########"),
                passenger_nationality=fake.country(),
                special_requests=fake.sentence() if random.random() > 0.7 else None,
                price=flight.economy_base_price * 1.2
            )
            db.session.add(booking_detail)
    
    db.session.commit()

    print("New test data injected successfully:")
    print(f"- {len(users)} users")
    print(f"- {len(airports)} airports")
    print(f"- {len(aircraft)} aircraft")
    print(f"- {len(flights)} flights")
    seats = Seat.query.count()
    print(f"- {seats} seats")
    bookings = Booking.query.count()
    print(f"- {bookings} bookings")
    booking_details = BookingDetail.query.count()
    print(f"- {booking_details} booking details")