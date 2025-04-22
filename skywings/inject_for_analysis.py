from app import app, db
from models import User, Flight, Airport, Aircraft, Seat, Booking, BookingDetail
from datetime import datetime, timedelta

with app.app_context():
    # Check if airports already exist, and create them if they don't
    airport1 = Airport.query.filter_by(code='JFK').first()
    if not airport1:
        airport1 = Airport(code='JFK', name='John F. Kennedy International', city='New York', country='USA')
        db.session.add(airport1)

    airport2 = Airport.query.filter_by(code='LAX').first()
    if not airport2:
        airport2 = Airport(code='LAX', name='Los Angeles International', city='Los Angeles', country='USA')
        db.session.add(airport2)

    db.session.commit()

    # Check if aircraft already exists
    aircraft = Aircraft.query.filter_by(registration='N12345').first()
    if not aircraft:
        aircraft = Aircraft(model='Boeing 737', registration='N12345', economy_seats=100, business_seats=20, first_class_seats=10)
        db.session.add(aircraft)
        db.session.commit()

    # Check if flight already exists
    flight = Flight.query.filter_by(flight_number='AA123').first()
    if not flight:
        flight = Flight(
            flight_number='AA123',
            origin_id=airport1.id,
            destination_id=airport2.id,
            departure_time=datetime.utcnow() + timedelta(days=1),
            arrival_time=datetime.utcnow() + timedelta(days=1, hours=5),
            aircraft_id=aircraft.id,
            economy_base_price=200,
            business_base_price=500,
            first_class_base_price=1000,
            status='Scheduled'
        )
        db.session.add(flight)
        db.session.commit()

    # Check if seat already exists
    seat = Seat.query.filter_by(flight_id=flight.id, seat_number='1A').first()
    if not seat:
        seat = Seat(flight_id=flight.id, seat_number='1A', seat_class='First Class', is_booked=True)
        db.session.add(seat)
        db.session.commit()

    # Check if user already exists
    user = User.query.filter_by(username='testuser').first()
    if not user:
        user = User(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User',
            frequent_flyer_status='Gold'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

    # Add bookings (within the last 30 days)
    for i in range(5):
        booking_ref = f'BOOK{i+1}'
        booking = Booking.query.filter_by(booking_reference=booking_ref).first()
        if not booking:
            booking_date = datetime.utcnow() - timedelta(days=i)
            booking = Booking(
                booking_reference=booking_ref,
                user_id=user.id,
                flight_id=flight.id,
                booking_date=booking_date,
                status='Confirmed',
                total_price=1000,
                payment_status='Paid'
            )
            db.session.add(booking)
            db.session.commit()

            # Add a booking detail
            booking_detail = BookingDetail.query.filter_by(booking_id=booking.id, seat_id=seat.id).first()
            if not booking_detail:
                booking_detail = BookingDetail(
                    booking_id=booking.id,
                    seat_id=seat.id,
                    passenger_first_name='Test',
                    passenger_last_name='User',
                    passenger_dob=datetime(1990, 1, 1).date(),
                    passenger_passport='P123456',
                    passenger_nationality='USA',
                    price=1000
                )
                db.session.add(booking_detail)
                db.session.commit()