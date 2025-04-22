from datetime import datetime
from extensions import db  # Import db from extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    passport_number = db.Column(db.String(50), nullable=True)
    nationality = db.Column(db.String(50), nullable=True)
    frequent_flyer_status = db.Column(db.String(20), default="Standard")
    frequent_flyer_miles = db.Column(db.Integer, default=0)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    
    booking_notifications = db.Column(db.Boolean, default=True)  # Default to True (or False, as desired)
    promotional_emails = db.Column(db.Boolean, default=True)
    newsletter = db.Column(db.Boolean, default=True)
    # Relationships
    bookings = db.relationship('Booking', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Airport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(3), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    
    # Relationships
    departing_flights = db.relationship('Flight', foreign_keys='Flight.origin_id', backref='origin_airport', lazy=True)
    arriving_flights = db.relationship('Flight', foreign_keys='Flight.destination_id', backref='destination_airport', lazy=True)
    
    def __repr__(self):
        return f'<Airport {self.code}>'


class Aircraft(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(100), nullable=False)
    registration = db.Column(db.String(20), unique=True, nullable=False)
    economy_seats = db.Column(db.Integer, nullable=False)
    business_seats = db.Column(db.Integer, nullable=False)
    first_class_seats = db.Column(db.Integer, nullable=False)
    
    # Relationships
    flights = db.relationship('Flight', backref='aircraft', lazy=True)
    
    def __repr__(self):
        return f'<Aircraft {self.registration}>'


class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flight_number = db.Column(db.String(10), nullable=False)
    origin_id = db.Column(db.Integer, db.ForeignKey('airport.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('airport.id'), nullable=False)
    departure_time = db.Column(db.DateTime, nullable=False)
    arrival_time = db.Column(db.DateTime, nullable=False)
    aircraft_id = db.Column(db.Integer, db.ForeignKey('aircraft.id'), nullable=False)
    economy_base_price = db.Column(db.Float, nullable=False)
    business_base_price = db.Column(db.Float, nullable=False)
    first_class_base_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Scheduled")
    postponed_count = db.Column(db.Integer, default=0)
    weather_status = db.Column(db.String(500), nullable=True)
    cancellation_reason = db.Column(db.String(500), nullable=True)
    
    # Relationships
    seats = db.relationship('Seat', backref='flight', lazy=True)
    bookings = db.relationship('Booking', backref='flight', lazy=True)
    
    def __repr__(self):
        return f'<Flight {self.flight_number}>'
    
    def calculate_price(self, seat_class, days_before_departure):
        """Calculate dynamic price based on class, booking time, and availability"""
        if seat_class == "Economy":
            base_price = self.economy_base_price
        elif seat_class == "Business":
            base_price = self.business_base_price
        else:  # First Class
            base_price = self.first_class_base_price
            
        # Time-based pricing: flights booked earlier get discounts
        if days_before_departure > 60:
            time_factor = 0.8
        elif days_before_departure > 30:
            time_factor = 0.9
        elif days_before_departure > 14:
            time_factor = 1.0
        elif days_before_departure > 7:
            time_factor = 1.1
        elif days_before_departure > 2:
            time_factor = 1.2
        else:
            time_factor = 1.3
            
        # Calculate availability percentage for the class
        total_seats = 0
        booked_seats = 0
        
        for seat in self.seats:
            if seat.seat_class == seat_class:
                total_seats += 1
                if seat.is_booked:
                    booked_seats += 1
        
        # Availability factor
        if total_seats > 0:
            availability_percentage = booked_seats / total_seats
            if availability_percentage < 0.3:
                availability_factor = 0.9
            elif availability_percentage < 0.6:
                availability_factor = 1.0
            elif availability_percentage < 0.8:
                availability_factor = 1.1
            else:
                availability_factor = 1.2
        else:
            availability_factor = 1.0
            
        # Calculate final price
        final_price = base_price * time_factor * availability_factor
        
        return round(final_price, 2)


class Seat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    seat_number = db.Column(db.String(5), nullable=False)
    seat_class = db.Column(db.String(20), nullable=False)  # Economy, Business, First Class
    is_booked = db.Column(db.Boolean, default=False)
    
    # Relationship
    booking_detail = db.relationship('BookingDetail', backref='seat', lazy=True, uselist=False)
    
    def __repr__(self):
        return f'<Seat {self.seat_number} ({self.seat_class})>'


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_reference = db.Column(db.String(10), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flight_id = db.Column(db.Integer, db.ForeignKey('flight.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Reserved")  # Reserved, Confirmed, Cancelled
    total_price = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), default="Pending")  # Pending, Paid, Refunded
    
    # Relationships
    booking_details = db.relationship('BookingDetail', backref='booking', lazy=True)
    
    def __repr__(self):
        return f'<Booking {self.booking_reference}>'


class BookingDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    seat_id = db.Column(db.Integer, db.ForeignKey('seat.id'), nullable=False)
    passenger_first_name = db.Column(db.String(64), nullable=False)
    passenger_last_name = db.Column(db.String(64), nullable=False)
    passenger_dob = db.Column(db.Date, nullable=False)
    passenger_passport = db.Column(db.String(50), nullable=False)
    passenger_nationality = db.Column(db.String(50), nullable=False)
    special_requests = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    
    def __repr__(self):
        return f'<BookingDetail {self.id}>'


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default="Completed")
    
    def __repr__(self):
        return f'<Payment {self.id}>'
