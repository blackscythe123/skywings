import os       
import re
import secrets
import string
from datetime import datetime, timedelta
import threading
from venv import logger 
from flask import make_response, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import or_, and_, func
from flask import Blueprint
from extensions import db, mail  
from flask_mail import Message
from models import User, Flight, Airport, Seat, Booking, BookingDetail, Payment, Aircraft
from utils import calculate_days_before_departure, get_seat_map
import logging
from sqlalchemy.orm import aliased, joinedload
from dotenv import load_dotenv
import stripe
from urllib.parse import urlparse, urljoin
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from flask import current_app as app  
from chatbot import handle_chatbot_message

# Load environment variables
load_dotenv()

# Load Stripe and Hugging Face API keys
stripe.api_key = os.getenv("STRIPE_SECRET_KEY","sk_test_51R5td12KasUIkcLCCArTAjD95BcWlURVW6eODRhywLyq7IhTSRS6ZioGMCtJTH1CBFwcFvOT7wl3hS7YIYk5SQbE00IsBZB01M  ")
# HF_API_KEY = os.getenv("HF_API_KEY")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
routes_bp = Blueprint("routes", __name__)

# ... (other routes remain unchanged until the chatbot section) ...
@routes_bp.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if request.method == 'POST':
        user_message = request.json.get("message", "")
        response_data = handle_chatbot_message(user_message)
        return jsonify(response_data)  # Single jsonify call here
    return render_template('chatbot.html')

@routes_bp.route('/clear_chat', methods=['POST'])
def clear_chat():
    session.pop("chat_context", None)
    session.pop("chat_messages", None)
    return jsonify({"response": "Chat context and history cleared"})

@routes_bp.route('/get_chat_history', methods=['GET'])
def get_chat_history():
    messages = session.get("chat_messages", [])
    return jsonify({"messages": messages})

@routes_bp.route('/')
def index():
    from models import Airport
    
    # Fetch all airports for the search form
    airports = Airport.query.order_by(Airport.code).all()
    
    # Fetch 3 random destinations from the database
    popular_destinations = Airport.query.order_by(func.random()).limit(3).all()
    
    # Fetch images from Unsplash for each destination
    from flask import current_app
    import random
    load_dotenv()
    unsplash_access_key = current_app.config.get("UNSPLASH_ACCESS_KEY", "aA4hhwnmCSs9PX2jVYVqkwB04gRYlHibNKxMKZ3v2fE")

    if not unsplash_access_key:
        print("Unsplash Access Key not found in configuration!")
        for destination in popular_destinations:
            destination.image_url = "https://via.placeholder.com/600x300?text=No+Image+Available"
        return render_template('index.html', popular_destinations=popular_destinations, airports=airports)
    
    city_query_map = {
        'New York': 'Statue of Liberty',
        'Los Angeles': 'Hollywood Sign',
        'Miami': 'Miami Beach',
        'London': 'Big Ben',
        'Paris': 'Eiffel Tower',
        'Frankfurt': 'Frankfurt Skyline',
        'Amsterdam': 'Amsterdam Canals',
        'Madrid': 'Madrid Puerta del Sol',
        'Rome': 'Colosseum',
        'Sydney': 'Sydney Opera House',
        'Tokyo': 'Tokyo Tower',
        'Singapore': 'Marina Bay Sands',
        'Dubai': 'Burj Khalifa',
        'Chicago': 'Chicago Skyline',
        'San Francisco': 'Golden Gate Bridge'
    }
    
    for destination in popular_destinations:
        query = city_query_map.get(destination.city, f"{destination.city} landmark")
        try:
            response = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "client_id": unsplash_access_key, "per_page": 5},
                headers={"Accept-Version": "v1"}
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if results:
                # Randomly select an image from the results for variety
                destination.image_url = random.choice(results).get("urls", {}).get("regular", "https://via.placeholder.com/600x300?text=No+Image+Available")
            else:
                print(f"No images found for query: {query}")
                destination.image_url = "https://via.placeholder.com/600x300?text=No+Image+Available"
        except Exception as e:
            print(f"Error fetching image for {query}: {e}")
            destination.image_url = "https://via.placeholder.com/600x300?text=No+Image+Available"
    
    return render_template('index.html', popular_destinations=popular_destinations, airports=airports)

from flask import jsonify, request
from sqlalchemy import or_

@routes_bp.route('/api/airports', methods=['GET'])
def get_airports():
    from sqlalchemy import or_
    query = request.args.get('query', '').strip().upper()

    if not query:
        # Return all airports if query is empty
        airports = Airport.query.limit(50).all()  # Limit to 50 to avoid overwhelming the UI
    else:
        # Search for airports where the code, city, or country contains the query
        airports = Airport.query.filter(
            or_(
                Airport.code.ilike(f'%{query}%'),
                Airport.city.ilike(f'%{query}%'),
                Airport.country.ilike(f'%{query}%')
            )
        ).limit(10).all()

    # Format the response for jQuery UI Autocomplete
    suggestions = [
        {
            'label': f'{airport.code} - {airport.city}, {airport.country} ({airport.name})',
            'value': airport.code
        }
        for airport in airports
    ]
    return jsonify(suggestions)

@routes_bp.route('/search_flights', methods=['GET'])
def search_flights():
    from models import Airport, Flight
    from datetime import datetime, timedelta

    # Get the destination from the query parameters
    destination = request.args.get('destination')
    if not destination:
        return render_template('search_flights.html', flights=[], error="Please provide a destination.")

    # Find the destination airport
    destination_airport = Airport.query.filter_by(city=destination).first()
    if not destination_airport:
        return render_template('search_flights.html', flights=[], error=f"No airport found for {destination}.")

    # Define the date range: current date to 30 days from now
    from datetime import datetime
    current_date = datetime.now()  # System date as per your setup
    end_date = current_date + timedelta(days=30)  # April 24, 2025

    # Query flights:
    # - Destination matches the given airport
    # - Departure time is between current_date and end_date
    # - Status is "Scheduled" (exclude Cancelled or Completed flights)
    # - Sort by departure_time in ascending order
    flights = Flight.query.filter(
        Flight.destination_id == destination_airport.id,
        Flight.departure_time >= current_date,
        Flight.departure_time <= end_date,
        Flight.status == "Scheduled"
    ).order_by(Flight.departure_time.asc()).all()

    # Attach origin and destination airport details to each flight
    for flight in flights:
        flight.origin = Airport.query.get(flight.origin_id)
        flight.destination = destination_airport

    # If no flights are found, show a message
    if not flights:
        return render_template('search_flights.html', flights=[], error=f"No scheduled flights available to {destination} within the next 30 days.")

    return render_template('search_flights.html', flights=flights, destination=destination)

@routes_bp.route('/search', methods=['POST', 'GET'])
@login_required
def search():
    flight_id = request.args.get('flight_id', type=int)
    search_params = session.get('search_params', {})

    if request.method == 'POST':
        search_params = {
            'origin': request.form.get('origin'),
            'destination': request.form.get('destination'),
            'departure_date': request.form.get('departure_date'),
            'return_date': request.form.get('return_date', ''),
            'travel_class': request.form.get('travel_class', 'Economy'),
            'passengers': int(request.form.get('passengers', 1))
        }
    elif flight_id:
        flight = Flight.query.get_or_404(flight_id)
        origin_airport = Airport.query.get(flight.origin_id)
        destination_airport = Airport.query.get(flight.destination_id)
        search_params.update({
            'origin': origin_airport.code,
            'destination': destination_airport.code,
            'departure_date': flight.departure_time.strftime('%Y-%m-%d'),
            'travel_class': search_params.get('travel_class', 'Economy'),
            'passengers': search_params.get('passengers', 1),
            'return_date': search_params.get('return_date', '')
        })
    else:
        if not search_params:
            flash('Please provide search criteria', 'danger')
            return redirect(url_for('routes.index'))

    session['search_params'] = search_params
    departure_date = datetime.strptime(search_params['departure_date'], '%Y-%m-%d').date()
    origin_airport = Airport.query.filter_by(code=search_params['origin']).first()
    destination_airport = Airport.query.filter_by(code=search_params['destination']).first()

    if not origin_airport or not destination_airport:
        flash('Invalid origin or destination airport', 'danger')
        return redirect(url_for('routes.index'))

    # Query departure flights
    departure_flights = Flight.query.filter(
        Flight.origin_id == origin_airport.id,
        Flight.destination_id == destination_airport.id,
        func.date(Flight.departure_time) == departure_date
    ).all()

    departure_flight_data = []
    for flight in departure_flights:
        days_before = calculate_days_before_departure(flight.departure_time)
        total_seats = sum(1 for s in flight.seats if s.seat_class == search_params['travel_class'])
        available_seats = sum(1 for s in flight.seats if s.seat_class == search_params['travel_class'] and not s.is_booked)
        
        if available_seats >= search_params['passengers']:
            price_per_person = flight.calculate_price(search_params['travel_class'], days_before)
            total_price = price_per_person * search_params['passengers']
            duration = flight.arrival_time - flight.departure_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            departure_flight_data.append({
                'flight': flight,
                'price_per_person': price_per_person,
                'total_price': total_price,
                'available_seats': available_seats,
                'total_seats': total_seats,
                'duration_hours': hours,
                'duration_minutes': minutes
            })

    # Handle return flights if specified
    return_flight_data = []
    if search_params.get('return_date'):
        return_date = datetime.strptime(search_params['return_date'], '%Y-%m-%d').date()
        return_flights = Flight.query.filter(
            Flight.origin_id == destination_airport.id,
            Flight.destination_id == origin_airport.id,
            func.date(Flight.departure_time) == return_date
        ).all()

        for flight in return_flights:
            days_before = calculate_days_before_departure(flight.departure_time)
            total_seats = sum(1 for s in flight.seats if s.seat_class == search_params['travel_class'])
            available_seats = sum(1 for s in flight.seats if s.seat_class == search_params['travel_class'] and not s.is_booked)
            
            if available_seats >= search_params['passengers']:
                price_per_person = flight.calculate_price(search_params['travel_class'], days_before)
                total_price = price_per_person * search_params['passengers']
                duration = flight.arrival_time - flight.departure_time
                hours, remainder = divmod(duration.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                return_flight_data.append({
                    'flight': flight,
                    'price_per_person': price_per_person,
                    'total_price': total_price,
                    'available_seats': available_seats,
                    'total_seats': total_seats,
                    'duration_hours': hours,
                    'duration_minutes': minutes
                })

    if not departure_flight_data and not return_flight_data:
        flash('No flights match your criteria. Please adjust your filters.', 'warning')
    
    return render_template(
        'search_results.html',
        origin_airport=origin_airport,
        destination_airport=destination_airport,
        departure_date=departure_date,
        return_date=search_params.get('return_date') and datetime.strptime(search_params['return_date'], '%Y-%m-%d').date(),
        travel_class=search_params['travel_class'],
        passengers=search_params['passengers'],
        departure_flights=departure_flight_data,
        return_flights=return_flight_data,
        is_round_trip=bool(search_params.get('return_date')),
        flight_id=flight_id
    )

@routes_bp.route('/book_flight/<int:flight_id>', methods=['GET'])
@login_required
def book_flight(flight_id):
    flight = Flight.query.get_or_404(flight_id)
    # Redirect to /search with the flight_id
    return redirect(url_for('routes.search', flight_id=flight_id))

# @routes_bp.route('/inject-default-data')
# def inject_default():
#     inject_default_data()
#     return jsonify({'message': 'Default data injected successfully'})
# Select seats
@routes_bp.route('/seat-selection/<flight_id>/<travel_class>/<int:passengers>', methods=['GET'])
def seat_selection(flight_id, travel_class, passengers):
    flight = Flight.query.get_or_404(flight_id)
    
    # Get the seat map
    seat_map = get_seat_map(flight, travel_class)
    
    # Get pricing info
    days_before = calculate_days_before_departure(flight.departure_time)
    price_per_seat = flight.calculate_price(travel_class, days_before)
    
    # Get previous selection from session if it exists
    selected_seats = session.get('selected_seats', {}).get(flight_id, [])
    
    return render_template(
        'seat_selection.html',
        flight=flight,
        travel_class=travel_class,
        passengers=int(passengers),
        seat_map=seat_map,
        price_per_seat=price_per_seat,
        selected_seats=selected_seats,
        origin_airport=flight.origin_airport,
        destination_airport=flight.destination_airport
    )

# Store selected seats in session
@routes_bp.route('/store-selected-seats/<flight_id>', methods=['POST'])
def store_selected_seats(flight_id):
    selected_seats = request.json.get('selected_seats', [])
    
    # Initialize or update session data
    if 'selected_seats' not in session:
        session['selected_seats'] = {}
    
    session['selected_seats'][flight_id] = selected_seats
    session.modified = True
    
    # Store the flight details in session
    flight = Flight.query.get_or_404(flight_id)
    days_before = calculate_days_before_departure(flight.departure_time)
    
    seat_pricing = {}
    for seat_id in selected_seats:
        seat = Seat.query.get(seat_id)
        if seat:
            price = flight.calculate_price(seat.seat_class, days_before)
            seat_pricing[seat_id] = price
    
    if 'seat_pricing' not in session:
        session['seat_pricing'] = {}
    
    session['seat_pricing'][flight_id] = seat_pricing
    session.modified = True
    
    return jsonify({'success': True})

# Passenger details form
@routes_bp.route('/passenger-details', methods=['GET'])
def passenger_details():
    departure_flight_id = request.args.get('departure_flight')
    return_flight_id = request.args.get('return_flight')
    
    if not departure_flight_id or 'selected_seats' not in session or departure_flight_id not in session['selected_seats']:
        flash('Please select seats for your flight first', 'danger')
        return redirect(url_for('routes.index'))
    
    departure_flight = Flight.query.get_or_404(departure_flight_id)
    return_flight = None
    if return_flight_id and return_flight_id in session.get('selected_seats', {}):
        return_flight = Flight.query.get_or_404(return_flight_id)
    
    # Get selected seats with prices
    departure_seats = []
    for seat_id in session['selected_seats'][departure_flight_id]:
        seat = Seat.query.get(seat_id)
        if seat:
            price = session.get('seat_pricing', {}).get(departure_flight_id, {}).get(str(seat_id), 0)
            departure_seats.append({'seat': seat, 'price': price})
    
    return_seats = []
    if return_flight and return_flight_id in session.get('selected_seats', {}):
        for seat_id in session['selected_seats'][return_flight_id]:
            seat = Seat.query.get(seat_id)
            if seat:
                price = session.get('seat_pricing', {}).get(return_flight_id, {}).get(str(seat_id), 0)
                return_seats.append({'seat': seat, 'price': price})
    
    # Calculate total price
    total_price = 0
    for seat_id, price in session.get('seat_pricing', {}).get(departure_flight_id, {}).items():
        total_price += price
    
    if return_flight_id:
        for seat_id, price in session.get('seat_pricing', {}).get(return_flight_id, {}).items():
            total_price += price
    
    return render_template(
        'passenger_details.html',
        departure_flight=departure_flight,
        return_flight=return_flight,
        departure_seats=departure_seats,
        return_seats=return_seats,
        total_price=total_price
    )

# Process passenger details and go to payment
@routes_bp.route('/process-passengers', methods=['POST'])
def process_passengers():
    passenger_data = {}
    
    # Get form data for each passenger
    passenger_count = int(request.form.get('passenger_count', 0))
    
    for i in range(1, passenger_count + 1):
        passenger_data[i] = {
            'first_name': request.form.get(f'first_name_{i}'),
            'last_name': request.form.get(f'last_name_{i}'),
            'dob': request.form.get(f'dob_{i}'),
            'passport': request.form.get(f'passport_{i}'),
            'nationality': request.form.get(f'nationality_{i}'),
            'special_requests': request.form.get(f'special_requests_{i}')
        }
    
    # Store in session
    session['passenger_data'] = passenger_data
    
    # Get flight IDs
    departure_flight_id = request.form.get('departure_flight_id')
    return_flight_id = request.form.get('return_flight_id')
    
    # Calculate total price
    total_price = 0
    
    # Add departure flight prices
    for seat_id, price in session.get('seat_pricing', {}).get(departure_flight_id, {}).items():
        total_price += price
    
    # Add return flight prices if applicable
    if return_flight_id:
        for seat_id, price in session.get('seat_pricing', {}).get(return_flight_id, {}).items():
            total_price += price
    
    return redirect(url_for('routes.payment', total_price=total_price))

# Payment page
@routes_bp.route('/payment', methods=['GET'])
def payment():
    total_price_str = request.args.get('total_price', '0')  # Get as string, default to '0'
    try:
        total_price = float(total_price_str)  # Convert to float
    except ValueError:
        total_price = 0  # Fallback to 0 if conversion fails
    
    print(f"Payment route - total_price type: {type(total_price)}, value: {total_price}")  # Debug
    return render_template('payment.html', total_price=total_price)  # Line 318

# Process payment and create booking
# @routes_bp.route('/process-payment', methods=['POST'])
# def process_payment():
#     if not current_user.is_authenticated:
#         flash('You need to be logged in to complete your booking', 'danger')
#         return redirect(url_for('routes.login'))
    
#     # Generate a unique booking reference
#     booking_reference = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    
#     # Get departure flight data
#     departure_flight_id = None
#     for flight_id in session.get('selected_seats', {}):
#         departure_flight_id = flight_id
#         break
    
#     if not departure_flight_id:
#         flash('No flight selected', 'danger')
#         return redirect(url_for('routes.index'))
    
#     # Calculate total price
#     total_price = 0
#     for flight_id, seats in session.get('seat_pricing', {}).items():
#         for seat_id, price in seats.items():
#             total_price += price
    
#     departure_flight = Flight.query.get(departure_flight_id)
    
#     # Create booking for departure flight
#     booking = Booking(
#         booking_reference=booking_reference,
#         user_id=current_user.id,
#         flight_id=departure_flight_id,
#         status="Confirmed",
#         total_price=total_price,
#         payment_status="Paid"
#     )
#     db.session.add(booking)
#     db.session.flush()  # Get booking ID without committing
    
#     # Add booking details for each passenger and seat
#     passenger_data = session.get('passenger_data', {})
#     seat_assignments = {}
    
#     # Assign passengers to seats
#     passenger_index = 1
#     for flight_id, seat_ids in session.get('selected_seats', {}).items():
#         for seat_id in seat_ids:
#             seat = Seat.query.get(seat_id)
            
#             # Mark seat as booked
#             seat.is_booked = True
            
#             # Get passenger data
#             passenger = passenger_data.get(str(passenger_index), {})
#             passenger_index += 1
            
#             booking_detail = BookingDetail(
#                 booking_id=booking.id,
#                 seat_id=seat_id,
#                 passenger_first_name=passenger.get('first_name', ''),
#                 passenger_last_name=passenger.get('last_name', ''),
#                 passenger_dob=datetime.strptime(passenger.get('dob', '2000-01-01'), '%Y-%m-%d').date(),
#                 passenger_passport=passenger.get('passport', ''),
#                 passenger_nationality=passenger.get('nationality', ''),
#                 special_requests=passenger.get('special_requests', ''),
#                 price=session.get('seat_pricing', {}).get(flight_id, {}).get(str(seat_id), 0)
#             )
#             db.session.add(booking_detail)
    
#     # Create payment record
#     payment = Payment(
#         booking_id=booking.id,
#         amount=total_price,
#         payment_method=request.form.get('payment_method', 'Credit Card'),
#         transaction_id='TRANS-' + ''.join(secrets.choice(string.digits) for _ in range(10)),
#         status="Completed"
#     )
#     db.session.add(payment)
    
#     # Award frequent flyer miles
#     current_user.frequent_flyer_miles += int(total_price / 10)  # 1 mile per $10 spent
    
#     # Update frequent flyer status based on miles
#     if current_user.frequent_flyer_miles >= 50000:
#         current_user.frequent_flyer_status = "Platinum"
#     elif current_user.frequent_flyer_miles >= 25000:
#         current_user.frequent_flyer_status = "Gold"
#     elif current_user.frequent_flyer_miles >= 10000:
#         current_user.frequent_flyer_status = "Silver"
    
#     # Commit all changes
#     db.session.commit()
    
#     # Clear session data
#     if 'selected_seats' in session:
#         session.pop('selected_seats')
#     if 'seat_pricing' in session:
#         session.pop('seat_pricing')
#     if 'passenger_data' in session:
#         session.pop('passenger_data')
#     if 'search_params' in session:
#         session.pop('search_params')
    
#     return redirect(url_for('routes.booking_confirmation', booking_reference=booking_reference))

# Booking confirmation page
@routes_bp.route('/booking-confirmation/<booking_reference>')
def booking_confirmation(booking_reference):
    booking = Booking.query.filter_by(booking_reference=booking_reference).first_or_404()
    
    # Security check: only allow viewing your own bookings
    if not current_user.is_authenticated or booking.user_id != current_user.id:
        flash('You do not have permission to view this booking', 'danger')
        return redirect(url_for('routes.index'))
    
    # Handle multiple bookings (e.g., round trip)
    all_bookings = request.args.get('all_bookings', booking_reference)
    booking_refs = all_bookings.split(',')
    bookings = Booking.query.filter(Booking.booking_reference.in_(booking_refs)).all()
    
    return render_template('confirmation.html', bookings=bookings, booking_references=all_bookings)

# View and manage bookings
@routes_bp.route('/my-bookings')
@login_required
def my_bookings():
    page = request.args.get('page', 1, type=int)
    booking_search = request.args.get('booking_search', '').strip()
    status = request.args.get('status', '').strip()
    sort = request.args.get('sort', 'date-asc')
    source = request.args.get('source', '').strip()
    destination = request.args.get('destination', '').strip()

    query = Booking.query.options(
        joinedload(Booking.flight).joinedload(Flight.origin_airport),
        joinedload(Booking.flight).joinedload(Flight.destination_airport),
        joinedload(Booking.booking_details).joinedload(BookingDetail.seat)
    ).filter_by(user_id=current_user.id)

    # Search by booking reference or flight number
    if booking_search:
        query = query.join(Booking.flight).filter(
            or_(
                Booking.booking_reference.ilike(f'%{booking_search}%'),
                Flight.flight_number.ilike(f'%{booking_search}%')
            )
        )
    # Filter by status
    if status:
        query = query.filter(Booking.status == status)
    # Filter by source city
    if source:
        query = query.join(Booking.flight).join(Flight.origin_airport).filter(Airport.city.ilike(f'%{source}%'))
    # Filter by destination city
    if destination:
        query = query.join(Booking.flight).join(Flight.destination_airport).filter(Airport.city.ilike(f'%{destination}%'))

    # Sorting
    if sort == 'date-asc':
        query = query.order_by(Flight.departure_time.asc())
    elif sort == 'date-desc':
        query = query.order_by(Flight.departure_time.desc())
    elif sort == 'booking-date-desc':
        query = query.order_by(Booking.booking_date.desc())
    elif sort == 'booking-date-asc':
        query = query.order_by(Booking.booking_date.asc())
    elif sort == 'price-desc':
        query = query.order_by(Booking.total_price.desc())
    elif sort == 'price-asc':
        query = query.order_by(Booking.total_price.asc())
    else:
        query = query.order_by(Booking.booking_date.desc())

    bookings_pagination = query.paginate(page=page, per_page=10)
    bookings = bookings_pagination.items
    current_time = datetime.now()
    return render_template(
        'manage_bookings.html',
        bookings=bookings,
        now=current_time,
        pagination=bookings_pagination,
        source=source,
        destination=destination
    )

# Cancel booking
@routes_bp.route('/cancel-booking/<booking_reference>', methods=['POST'])
@login_required
def cancel_booking(booking_reference):
    booking = Booking.query.filter_by(booking_reference=booking_reference).first_or_404()
    
    # Security check: only allow canceling your own bookings
    if booking.user_id != current_user.id:
        flash('You do not have permission to cancel this booking', 'danger')
        return redirect(url_for('routes.my_bookings'))
    
    # Check if it's too late to cancel (e.g., less than 24 hours before departure)
    flight = booking.flight
    if flight.departure_time - timedelta(hours=24) < datetime.utcnow():
        flash('Cannot cancel booking less than 24 hours before departure', 'danger')
        return redirect(url_for('routes.my_bookings'))
    
    # Update booking status
    booking.status = "Cancelled"
    
    # Free up the seats
    for detail in booking.booking_details:
        detail.seat.is_booked = False
    
    # Handle refund (in a real system, this would integrate with payment processor)
    # For this demo, we'll just mark the payment as refunded
    for payment in Payment.query.filter_by(booking_id=booking.id).all():
        payment.status = "Refunded"
    
    booking.payment_status = "Refunded"
    
    # If cancellation is more than 7 days before departure, provide full refund (minus booking fee)
    # Otherwise, provide partial refund
    if flight.departure_time - timedelta(days=7) > datetime.utcnow():
        refund_amount = booking.total_price * 0.9  # 90% refund (10% booking fee)
    else:
        refund_amount = booking.total_price * 0.5  # 50% refund
    
    # Create refund payment record
    refund = Payment(
        booking_id=booking.id,
        amount=-refund_amount,  # Negative amount to indicate refund
        payment_method="Refund",
        transaction_id='REFUND-' + ''.join(secrets.choice(string.digits) for _ in range(10)),
        status="Completed"
    )
    db.session.add(refund)
    
    db.session.commit()
    
    flash(f'Booking {booking_reference} has been cancelled and a refund of ${refund_amount:.2f} will be processed', 'success')
    return redirect(url_for('routes.my_bookings'))

# User login
def is_safe_url(target, host_url):
    # Resolve the target URL against the host URL
    resolved_url = urljoin(host_url, target)
    ref_url = urlparse(host_url)
    test_url = urlparse(resolved_url)
    
    # Allow empty scheme (relative URLs) or http/https
    scheme_ok = not test_url.scheme or test_url.scheme in ('http', 'https')
    # Ensure the domain matches to prevent external redirects
    domain_ok = ref_url.netloc == test_url.netloc
    
    return scheme_ok and domain_ok

@routes_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        # Capture user data before logout
        user_data = {
            'id': current_user.id,
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'email': current_user.email,
            'username': current_user.username
        }
        
        # Send logout email in background with app context
        send_email_in_background(app._get_current_object(), user_data, "logout")
        
        # Log out the user
        logout_user()
        
        # Clear chat context
        session.pop("chat_context", None)
    
    return redirect('/login')

@routes_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            # Check if password hash needs rehashing
            current_hash = user.password_hash
            new_hash = generate_password_hash(password)
            hash_parts = current_hash.split('$')
            if len(hash_parts) < 3 or hash_parts[0] != new_hash.split('$')[0] or hash_parts[1] != new_hash.split('$')[1]:
                user.set_password(password)
                db.session.commit()
                
            login_user(user, remember=remember)
            
            # Capture user data
            user_data = {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'username': user.username
            }
            
            # Send login email in background with app context
            send_email_in_background(app._get_current_object(), user_data, "login")

            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page, request.host_url):
                return redirect(next_page)
            return redirect(url_for('routes.index'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@routes_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Capture user data
        user_data = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'username': user.username
        }
        
        # Send welcome email in background with app context
        send_email_in_background(app._get_current_object(), user_data, "welcome")

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('routes.login'))
    
    return render_template('register.html')

@routes_bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html')
@routes_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        # Get form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone_number = request.form.get('phone_number')
        date_of_birth = request.form.get('date_of_birth')
        nationality = request.form.get('nationality')
        address = request.form.get('address')
        passport_number = request.form.get('passport_number')

        # Validate required fields
        if not first_name or not last_name:
            flash('First name and last name are required', 'danger')
            return redirect(url_for('routes.profile'))

        # Update user information
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.phone_number = phone_number if phone_number else None
        current_user.nationality = nationality if nationality else None
        current_user.address = address if address else None
        current_user.passport_number = passport_number if passport_number else None

        # Handle date of birth
        if date_of_birth:
            try:
                current_user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date of birth format', 'danger')
                return redirect(url_for('routes.profile'))
        else:
            current_user.date_of_birth = None

        # Commit changes to the database
        db.session.commit()
        flash('Profile updated successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating profile: {str(e)}', 'danger')

    return redirect(url_for('routes.profile'))

@routes_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('routes.profile'))

    if new_password != confirm_password:
        flash('New password and confirmation do not match.', 'danger')
        return redirect(url_for('routes.profile'))

    # Password strength validation
    if len(new_password) < 8:
        flash('New password must be at least 8 characters long.', 'danger')
        return redirect(url_for('routes.profile'))
    if not any(c.isupper() for c in new_password):
        flash('New password must contain at least one uppercase letter.', 'danger')
        return redirect(url_for('routes.profile'))
    if not any(c.isdigit() for c in new_password):
        flash('New password must contain at least one number.', 'danger')
        return redirect(url_for('routes.profile'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('Password updated successfully!', 'success')
    return redirect(url_for('routes.profile'))
@routes_bp.route('/save_preferences', methods=['POST'])
@login_required
def save_preferences():
    try:
        booking_notifications = 'booking_notifications' in request.form
        promotional_emails = 'promotional_emails' in request.form
        newsletter = 'newsletter' in request.form

        # Update user preferences
        current_user.booking_notifications = booking_notifications
        current_user.promotional_emails = promotional_emails
        current_user.newsletter = newsletter
        
        db.session.commit()
        flash('Email preferences updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating preferences: {str(e)}', 'danger')
    
    return redirect(url_for('routes.profile'))
# API for getting available seats for a flight
@routes_bp.route('/api/flight/<flight_id>/available-seats/<travel_class>')
def available_seats(flight_id, travel_class):
    flight = Flight.query.get_or_404(flight_id)
    
    # Get all seats for the flight with the specified class
    seats = Seat.query.filter_by(flight_id=flight.id, seat_class=travel_class).all()
    
    # Format seat data
    seat_data = [{
        'id': seat.id,
        'seat_number': seat.seat_number,
        'is_booked': seat.is_booked
    } for seat in seats]
    
    return jsonify(seat_data)

# Initialize database with sample data
@routes_bp.route('/init-db')
def init_db():
    # Only run this route in development mode
    if not current_app.debug:
        return jsonify({'error': 'This route is only available in debug mode'}), 403
    
    # Clear existing data
    db.drop_all()
    db.create_all()
    
    # Create airports
    airports = [
        Airport(code='JFK', name='John F. Kennedy International Airport', city='New York', country='USA'),
        Airport(code='LAX', name='Los Angeles International Airport', city='Los Angeles', country='USA'),
        Airport(code='SFO', name='San Francisco International Airport', city='San Francisco', country='USA'),
        Airport(code='ORD', name='O\'Hare International Airport', city='Chicago', country='USA'),
        Airport(code='MIA', name='Miami International Airport', city='Miami', country='USA'),
        Airport(code='LHR', name='Heathrow Airport', city='London', country='UK'),
        Airport(code='CDG', name='Charles de Gaulle Airport', city='Paris', country='France'),
        Airport(code='FRA', name='Frankfurt Airport', city='Frankfurt', country='Germany'),
        Airport(code='AMS', name='Amsterdam Airport Schiphol', city='Amsterdam', country='Netherlands'),
        Airport(code='MAD', name='Adolfo Suárez Madrid–Barajas Airport', city='Madrid', country='Spain'),
        Airport(code='FCO', name='Leonardo da Vinci International Airport', city='Rome', country='Italy'),
        Airport(code='SYD', name='Sydney Airport', city='Sydney', country='Australia'),
        Airport(code='HND', name='Haneda Airport', city='Tokyo', country='Japan'),
        Airport(code='SIN', name='Singapore Changi Airport', city='Singapore', country='Singapore'),
        Airport(code='DXB', name='Dubai International Airport', city='Dubai', country='UAE')
    ]
    db.session.add_all(airports)
    db.session.commit()
    
    # Create aircraft
    aircraft = [
        Aircraft(model='Boeing 737-800', registration='N12345', economy_seats=150, business_seats=12, first_class_seats=8),
        Aircraft(model='Airbus A320', registration='N54321', economy_seats=140, business_seats=10, first_class_seats=6),
        Aircraft(model='Boeing 777-300ER', registration='N77733', economy_seats=300, business_seats=40, first_class_seats=10),
        Aircraft(model='Airbus A380', registration='N38080', economy_seats=420, business_seats=60, first_class_seats=14)
    ]
    db.session.add_all(aircraft)
    db.session.commit()
    
    # Create flights
    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)
    next_week = now + timedelta(days=7)
    next_month = now + timedelta(days=30)
    
    flights = [
        # Domestic US flights
        Flight(flight_number='AA100', origin_id=1, destination_id=2, departure_time=tomorrow + timedelta(hours=9), 
               arrival_time=tomorrow + timedelta(hours=12), aircraft_id=1, economy_base_price=199.99, 
               business_base_price=499.99, first_class_base_price=999.99),
        
        Flight(flight_number='AA101', origin_id=2, destination_id=1, departure_time=tomorrow + timedelta(hours=15), 
               arrival_time=tomorrow + timedelta(hours=23), aircraft_id=1, economy_base_price=219.99, 
               business_base_price=519.99, first_class_base_price=1019.99),
        
        Flight(flight_number='UA200', origin_id=3, destination_id=4, departure_time=tomorrow + timedelta(hours=11), 
               arrival_time=tomorrow + timedelta(hours=17), aircraft_id=2, economy_base_price=179.99, 
               business_base_price=479.99, first_class_base_price=879.99),
        
        Flight(flight_number='UA201', origin_id=4, destination_id=3, departure_time=tomorrow + timedelta(hours=18), 
               arrival_time=tomorrow + timedelta(hours=20), aircraft_id=2, economy_base_price=189.99, 
               business_base_price=489.99, first_class_base_price=889.99),
        
        # International flights
        Flight(flight_number='BA300', origin_id=1, destination_id=6, departure_time=next_week + timedelta(hours=19), 
               arrival_time=next_week + timedelta(hours=31), aircraft_id=3, economy_base_price=599.99, 
               business_base_price=1499.99, first_class_base_price=2999.99),
        
        Flight(flight_number='BA301', origin_id=6, destination_id=1, departure_time=next_week + timedelta(hours=33), 
               arrival_time=next_week + timedelta(hours=42), aircraft_id=3, economy_base_price=629.99, 
               business_base_price=1529.99, first_class_base_price=3029.99),
        
        Flight(flight_number='LH400', origin_id=6, destination_id=8, departure_time=next_week + timedelta(hours=8), 
               arrival_time=next_week + timedelta(hours=11), aircraft_id=2, economy_base_price=249.99, 
               business_base_price=649.99, first_class_base_price=1249.99),
        
        Flight(flight_number='LH401', origin_id=8, destination_id=6, departure_time=next_week + timedelta(hours=12), 
               arrival_time=next_week + timedelta(hours=15), aircraft_id=2, economy_base_price=269.99, 
               business_base_price=669.99, first_class_base_price=1269.99),
        
        Flight(flight_number='SQ500', origin_id=14, destination_id=13, departure_time=next_month + timedelta(hours=1), 
               arrival_time=next_month + timedelta(hours=8), aircraft_id=4, economy_base_price=499.99, 
               business_base_price=1299.99, first_class_base_price=2499.99),
        
        Flight(flight_number='SQ501', origin_id=13, destination_id=14, departure_time=next_month + timedelta(hours=10), 
               arrival_time=next_month + timedelta(hours=17), aircraft_id=4, economy_base_price=519.99, 
               business_base_price=1319.99, first_class_base_price=2519.99),
        
        # Additional flights for popular destinations on March 31, 2025
        Flight(flight_number='AF102', origin_id=1, destination_id=7, departure_time=next_week + timedelta(hours=10), 
               arrival_time=next_week + timedelta(hours=18), aircraft_id=3, economy_base_price=649.99, 
               business_base_price=1599.99, first_class_base_price=3099.99),  # JFK to CDG (Paris)
        
        Flight(flight_number='JL104', origin_id=1, destination_id=13, departure_time=next_week + timedelta(hours=13), 
               arrival_time=next_week + timedelta(hours=27), aircraft_id=3, economy_base_price=799.99, 
               business_base_price=1999.99, first_class_base_price=3999.99),  # JFK to HND (Tokyo)
        
        Flight(flight_number='QF106', origin_id=1, destination_id=12, departure_time=next_week + timedelta(hours=16), 
               arrival_time=next_week + timedelta(hours=38), aircraft_id=4, economy_base_price=999.99, 
               business_base_price=2499.99, first_class_base_price=4999.99)  # JFK to SYD (Sydney)
    ]
    db.session.add_all(flights)
    db.session.commit()
    
    # Create seats for all flights
    for flight in flights:
        # Get the aircraft for this flight
        aircraft = Aircraft.query.get(flight.aircraft_id)
        
        # Create Economy seats
        for i in range(1, aircraft.economy_seats + 1):
            row = (i - 1) // 6 + 10  # Economy starts at row 10
            col = (i - 1) % 6
            col_letter = chr(65 + col)  # A, B, C, D, E, F
            seat_number = f"{row}{col_letter}"
            
            seat = Seat(
                flight_id=flight.id,
                seat_number=seat_number,
                seat_class="Economy",
                is_booked=False
            )
            db.session.add(seat)
        
        # Create Business seats
        for i in range(1, aircraft.business_seats + 1):
            row = (i - 1) // 4 + 3  # Business starts at row 3
            col = (i - 1) % 4
            col_letter = chr(65 + col)  # A, B, C, D
            seat_number = f"{row}{col_letter}"
            
            seat = Seat(
                flight_id=flight.id,
                seat_number=seat_number,
                seat_class="Business",
                is_booked=False
            )
            db.session.add(seat)
        
        # Create First Class seats
        for i in range(1, aircraft.first_class_seats + 1):
            row = (i - 1) // 2 + 1  # First Class starts at row 1
            col = (i - 1) % 2
            col_letter = chr(65 + col * 3)  # A, D (with bigger spacing)
            seat_number = f"{row}{col_letter}"
            
            seat = Seat(
                flight_id=flight.id,
                seat_number=seat_number,
                seat_class="First Class",
                is_booked=False
            )
            db.session.add(seat)
    
    db.session.commit()
    
    # Create sample users
    user1 = User(
        username="johndoe",
        email="john@example.com",
        first_name="John",
        last_name="Doe",
        date_of_birth=datetime(1985, 5, 15).date(),
        phone_number="555-123-4567",
        address="123 Main St, Anytown, USA",
        passport_number="AB123456",
        nationality="USA",
        frequent_flyer_status="Gold",
        frequent_flyer_miles=25000
    )
    user1.set_password("password123")
    
    user2 = User(
        username="janedoe",
        email="jane@example.com",
        first_name="Jane",
        last_name="Doe",
        date_of_birth=datetime(1990, 8, 21).date(),
        phone_number="555-987-6543",
        address="456 Oak Ave, Somewhere, USA",
        passport_number="CD789012",
        nationality="USA",
        frequent_flyer_status="Silver",
        frequent_flyer_miles=12000
    )
    user2.set_password("password123")
    
    db.session.add_all([user1, user2])
    db.session.commit()
    
    # Create sample bookings
    # Booking 1: John Doe books a flight to Paris (CDG, flight_id=11)
    booking1 = Booking(
        booking_reference='ABC123',
        user_id=1,  # John Doe
        flight_id=11,  # JFK to CDG (Paris)
        booking_date=now,
        status="Confirmed",
        total_price=649.99,
        payment_status="Paid"
    )
    # Booking 2: Jane Doe books a flight to Paris (CDG, flight_id=11)
    booking2 = Booking(
        booking_reference='DEF456',
        user_id=2,  # Jane Doe
        flight_id=11,  # JFK to CDG (Paris)
        booking_date=now,
        status="Confirmed",
        total_price=649.99,
        payment_status="Paid"
    )
    # Booking 3: John Doe books a flight to Tokyo (HND, flight_id=12)
    booking3 = Booking(
        booking_reference='GHI789',
        user_id=1,  # John Doe
        flight_id=12,  # JFK to HND (Tokyo)
        booking_date=now,
        status="Confirmed",
        total_price=799.99,
        payment_status="Paid"
    )
    # Booking 4: Jane Doe books a flight to Sydney (SYD, flight_id=13)
    booking4 = Booking(
        booking_reference='JKL012',
        user_id=2,  # Jane Doe
        flight_id=13,  # JFK to SYD (Sydney)
        booking_date=now,
        status="Confirmed",
        total_price=999.99,
        payment_status="Paid"
    )
    db.session.add_all([booking1, booking2, booking3, booking4])
    db.session.commit()

    # Add booking details and mark seats as booked
    # For simplicity, we'll assign the first few seats of each flight
    # Flight 11 (JFK to CDG) has 300 economy seats (aircraft_id=3), so seats 1 and 2 are economy
    booking_detail1 = BookingDetail(
        booking_id=booking1.id,
        seat_id=1,  # First seat of flight 11
        passenger_first_name="John",
        passenger_last_name="Doe",
        passenger_dob=datetime(1985, 5, 15).date(),
        passenger_passport="AB123456",
        passenger_nationality="USA",
        price=649.99
    )
    booking_detail2 = BookingDetail(
        booking_id=booking2.id,
        seat_id=2,  # Second seat of flight 11
        passenger_first_name="Jane",
        passenger_last_name="Doe",
        passenger_dob=datetime(1990, 8, 21).date(),
        passenger_passport="CD789012",
        passenger_nationality="USA",
        price=649.99
    )
    # Flight 12 (JFK to HND) has 300 economy seats (aircraft_id=3), so seat 301 is the first seat of flight 12
    booking_detail3 = BookingDetail(
        booking_id=booking3.id,
        seat_id=301,  # First seat of flight 12
        passenger_first_name="John",
        passenger_last_name="Doe",
        passenger_dob=datetime(1985, 5, 15).date(),
        passenger_passport="AB123456",
        passenger_nationality="USA",
        price=799.99
    )
    # Flight 13 (JFK to SYD) has 420 economy seats (aircraft_id=4), so seat 601 is the first seat of flight 13
    booking_detail4 = BookingDetail(
        booking_id=booking4.id,
        seat_id=601,  # First seat of flight 13
        passenger_first_name="Jane",
        passenger_last_name="Doe",
        passenger_dob=datetime(1990, 8, 21).date(),
        passenger_passport="CD789012",
        passenger_nationality="USA",
        price=999.99
    )
    db.session.add_all([booking_detail1, booking_detail2, booking_detail3, booking_detail4])
    db.session.commit()

    # Mark seats as booked
    Seat.query.get(1).is_booked = True
    Seat.query.get(2).is_booked = True
    Seat.query.get(301).is_booked = True
    Seat.query.get(601).is_booked = True
    db.session.commit()

    # Create payment records for the bookings
    payment1 = Payment(
        booking_id=booking1.id,
        amount=649.99,
        payment_method="Credit Card",
        transaction_id='TRANS-1234567890',
        status="Completed"
    )
    payment2 = Payment(
        booking_id=booking2.id,
        amount=649.99,
        payment_method="Credit Card",
        transaction_id='TRANS-1234567891',
        status="Completed"
    )
    payment3 = Payment(
        booking_id=booking3.id,
        amount=799.99,
        payment_method="Credit Card",
        transaction_id='TRANS-1234567892',
        status="Completed"
    )
    payment4 = Payment(
        booking_id=booking4.id,
        amount=999.99,
        payment_method="Credit Card",
        transaction_id='TRANS-1234567893',
        status="Completed"
    )
    db.session.add_all([payment1, payment2, payment3, payment4])
    db.session.commit()
    
    return jsonify({'message': 'Database initialized successfully'})

# Error handlers
@routes_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404, error_message="Page not found"), 404

@routes_bp.app_errorhandler(500)
def server_error(e):
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500
# Admin routes
# Admin dashboard
@routes_bp.route('/admin')
@login_required
def admin_dashboard():
    # Check if user is admin
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    # Get statistics for dashboard
    total_users = User.query.count()
    total_flights = Flight.query.count()
    total_bookings = Booking.query.count()
    total_airports = Airport.query.count()
    total_aircraft = Aircraft.query.count()
    
    # Calculate revenue
    revenue = db.session.query(func.sum(Booking.total_price)).scalar() or 0
    
    # Get recent bookings
    recent_bookings = Booking.query.order_by(Booking.booking_date.desc()).limit(10).all()
    
    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_flights=total_flights,
        total_bookings=total_bookings,
        total_airports=total_airports,
        total_aircraft=total_aircraft,
        revenue=revenue,
        recent_bookings=recent_bookings
    )

# Admin flight management
@routes_bp.route('/admin/flights')
@login_required
def admin_flights():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    # Get query parameters for filtering
    origin = request.args.get('origin')
    destination = request.args.get('destination')
    date_str = request.args.get('date')
    status = request.args.get('status')
    
    # Build query
    query = Flight.query
    
    if origin:
        query = query.filter(Flight.origin_id == origin)
    if destination:
        query = query.filter(Flight.destination_id == destination)
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        query = query.filter(func.date(Flight.departure_time) == date)
    if status:
        query = query.filter(Flight.status == status)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    flights_query = query.order_by(Flight.departure_time)
    flights = flights_query.paginate(page=page, per_page=per_page)
    
    # Get all airports for filter dropdown
    airports = Airport.query.order_by(Airport.code).all()
    
    next_url = url_for('routes.admin_flights', page=flights.next_num) if flights.has_next else None
    prev_url = url_for('routes.admin_flights', page=flights.prev_num) if flights.has_prev else None
    
    return render_template(
        'admin/flights.html',
        flights=flights,
        airports=airports,
        page=page,
        next_url=next_url,
        prev_url=prev_url
    )

# Add new flight
@routes_bp.route('/admin/flights/add', methods=['GET', 'POST'])
@login_required
def admin_add_flight():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    # Get all airports and aircraft for the form
    airports = Airport.query.order_by(Airport.code).all()
    aircrafts = Aircraft.query.all()
    
    if request.method == 'POST':
        flight_number = request.form.get('flight_number')
        origin_id = request.form.get('origin_id')
        destination_id = request.form.get('destination_id')
        departure_time = datetime.strptime(request.form.get('departure_time'), '%Y-%m-%dT%H:%M')
        arrival_time = datetime.strptime(request.form.get('arrival_time'), '%Y-%m-%dT%H:%M')
        aircraft_id = request.form.get('aircraft_id')
        economy_base_price = float(request.form.get('economy_base_price'))
        business_base_price = float(request.form.get('business_base_price'))
        first_class_base_price = float(request.form.get('first_class_base_price'))
        status = request.form.get('status')
        
        # Validate input
        if origin_id == destination_id:
            flash('Origin and destination cannot be the same', 'danger')
            return render_template('admin/add_edit_flight.html', airports=airports, aircrafts=aircrafts)
        
        if departure_time >= arrival_time:
            flash('Arrival time must be after departure time', 'danger')
            return render_template('admin/add_edit_flight.html', airports=airports, aircrafts=aircrafts)
        
        # Create new flight
        flight = Flight(
            flight_number=flight_number,
            origin_id=origin_id,
            destination_id=destination_id,
            departure_time=departure_time,
            arrival_time=arrival_time,
            aircraft_id=aircraft_id,
            economy_base_price=economy_base_price,
            business_base_price=business_base_price,
            first_class_base_price=first_class_base_price,
            status=status
        )
        
        db.session.add(flight)
        db.session.commit()
        
        # Generate seats for the flight
        aircraft = Aircraft.query.get(aircraft_id)
        
        # Generate Economy seats
        for i in range(1, aircraft.economy_seats + 1):
            row = (i - 1) // 6 + 1
            col = chr(65 + ((i - 1) % 6))
            seat = Seat(
                flight_id=flight.id,
                seat_number=f"{row}{col}",
                seat_class="Economy",
                is_booked=False
            )
            db.session.add(seat)
        
        # Generate Business seats
        for i in range(1, aircraft.business_seats + 1):
            row = (i - 1) // 4 + 1
            col = chr(65 + ((i - 1) % 4))
            seat = Seat(
                flight_id=flight.id,
                seat_number=f"B{row}{col}",
                seat_class="Business",
                is_booked=False
            )
            db.session.add(seat)
        
        # Generate First Class seats
        for i in range(1, aircraft.first_class_seats + 1):
            row = (i - 1) // 2 + 1
            col = chr(65 + ((i - 1) % 2))
            seat = Seat(
                flight_id=flight.id,
                seat_number=f"F{row}{col}",
                seat_class="First Class",
                is_booked=False
            )
            db.session.add(seat)
        
        db.session.commit()
        
        flash('Flight added successfully', 'success')
        return redirect(url_for('routes.admin_flights'))
    
    return render_template('admin/add_edit_flight.html', airports=airports, aircrafts=aircrafts)

# Edit flight
@routes_bp.route('/admin/flights/edit/<flight_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_flight(flight_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    # Get flight
    flight = Flight.query.get_or_404(flight_id)
    
    # Get all airports and aircraft for the form
    airports = Airport.query.order_by(Airport.code).all()
    aircrafts = Aircraft.query.all()
    
    if request.method == 'POST':
        flight.flight_number = request.form.get('flight_number')
        flight.origin_id = request.form.get('origin_id')
        flight.destination_id = request.form.get('destination_id')
        flight.departure_time = datetime.strptime(request.form.get('departure_time'), '%Y-%m-%dT%H:%M')
        flight.arrival_time = datetime.strptime(request.form.get('arrival_time'), '%Y-%m-%dT%H:%M')
        flight.aircraft_id = request.form.get('aircraft_id')
        flight.economy_base_price = float(request.form.get('economy_base_price'))
        flight.business_base_price = float(request.form.get('business_base_price'))
        flight.first_class_base_price = float(request.form.get('first_class_base_price'))
        new_status = request.form.get('status')
        old_status = flight.status
        flight.status = new_status
        
        # Send email notifications if status changed to Postponed or Cancelled
        if new_status in ['Postponed', 'Cancelled'] and old_status != new_status:
            try:
                subject = f'Flight Status Update - {flight.flight_number}'
                sender = app.config['MAIL_DEFAULT_SENDER']
                
                # Limit to first 5 bookings for testing
                for booking in flight.bookings[:5]:
                    if new_status == 'Postponed':
                        message = f"""Dear {booking.user.first_name},

Your flight {flight.flight_number} has been postponed by the airline.

Booking Reference: {booking.booking_reference}
Original Departure: {flight.departure_time}

We will continue to monitor the situation and update you on any changes.

We apologize for any inconvenience caused.

Best regards,
SkyWings Team"""
                    else:  # Cancelled
                        message = f"""Dear {booking.user.first_name},

We regret to inform you that your flight {flight.flight_number} has been cancelled by the airline.

Booking Reference: {booking.booking_reference}
A full refund will be processed within 3-5 business days.

We sincerely apologize for any inconvenience caused.

Best regards,
SkyWings Team"""
                    
                    msg = Message(
                        subject=subject,
                        sender=sender,
                        recipients=[booking.user.email],
                        body=message
                    )
                    mail.send(msg)
            except Exception as e:
                logger.error(f'Failed to send status change notification: {str(e)}')
                pass  # Do not retry on failure

        # Validate input
        if flight.origin_id == flight.destination_id:
            flash('Origin and destination cannot be the same', 'danger')
            return render_template('admin/add_edit_flight.html', flight=flight, airports=airports, aircrafts=aircrafts)
        
        if flight.departure_time >= flight.arrival_time:
            flash('Arrival time must be after departure time', 'danger')
            return render_template('admin/add_edit_flight.html', flight=flight, airports=airports, aircrafts=aircrafts)
        
        db.session.commit()
        flash('Flight updated successfully', 'success')
        return redirect(url_for('routes.admin_flights'))
    
    # Return template for GET request
    return render_template('admin/add_edit_flight.html', flight=flight, airports=airports, aircrafts=aircrafts)

# Delete flight
@routes_bp.route('/admin/flights/delete/<flight_id>', methods=['POST'])
@login_required
def admin_delete_flight(flight_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    flight = Flight.query.get_or_404(flight_id)
    
    # Check if flight has bookings
    if flight.bookings:
        flash('Cannot delete flight with existing bookings', 'danger')
        return redirect(url_for('routes.admin_flights'))
    
    # Delete all seats first
    Seat.query.filter_by(flight_id=flight.id).delete()
    
    # Delete flight
    db.session.delete(flight)
    db.session.commit()
    
    flash('Flight deleted successfully', 'success')
    return redirect(url_for('routes.admin_flights'))

# Admin user management
@routes_bp.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    # Get query parameters for filtering
    status = request.args.get('status')
    role = request.args.get('role')
    join_date_str = request.args.get('join_date')
    min_miles = request.args.get('min_miles')
    
    # Build query
    query = User.query
    
    if status:
        query = query.filter(User.frequent_flyer_status == status)
    if role:
        is_admin = role == 'admin'
        query = query.filter(User.is_admin == is_admin)
    if join_date_str:
        join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date()
        query = query.filter(func.date(User.date_joined) >= join_date)
    if min_miles:
        query = query.filter(User.frequent_flyer_miles >= min_miles)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    users_query = query.order_by(User.date_joined.desc())
    users = users_query.paginate(page=page, per_page=per_page)
    
    next_url = url_for('routes.admin_users', page=users.next_num) if users.has_next else None
    prev_url = url_for('routes.admin_users', page=users.prev_num) if users.has_prev else None
    
    return render_template(
        'admin/users.html',
        users=users,
        page=page,
        next_url=next_url,
        prev_url=prev_url
    )

# Toggle admin status
@routes_bp.route('/admin/users/toggle-admin/<user_id>', methods=['POST'])
@login_required
def admin_toggle_admin(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Don't allow self-demotion
    if user.id == current_user.id:
        flash('You cannot change your own admin status', 'danger')
        return redirect(url_for('routes.admin_users'))
    
    # Toggle admin status
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = 'granted' if user.is_admin else 'revoked'
    flash(f'Admin privileges {status} for {user.first_name} {user.last_name}', 'success')
    return redirect(url_for('routes.admin_users'))

# Update frequent flyer status
@routes_bp.route('/admin/users/update-ff-status/<user_id>', methods=['POST'])
@login_required
def admin_update_ff_status(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    user = User.query.get_or_404(user_id)
    
    user.frequent_flyer_status = request.form.get('ff_status')
    user.frequent_flyer_miles = int(request.form.get('ff_miles'))
    
    db.session.commit()
    
    flash(f'Frequent flyer status updated for {user.first_name} {user.last_name}', 'success')
    return redirect(url_for('routes.admin_users'))

# Admin booking management
@routes_bp.route('/admin/bookings')
@login_required
def admin_bookings():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    # Get query parameters for filtering
    flight = request.args.get('flight')
    status = request.args.get('status')
    payment = request.args.get('payment')
    date_str = request.args.get('date')
    
    # Build query
    query = Booking.query
    
    if flight:
        flight_obj = Flight.query.filter(Flight.flight_number == flight).first()
        if flight_obj:
            query = query.filter(Booking.flight_id == flight_obj.id)
    if status:
        query = query.filter(Booking.status == status)
    if payment:
        query = query.filter(Booking.payment_status == payment)
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        query = query.filter(func.date(Booking.booking_date) == date)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    bookings_query = query.order_by(Booking.booking_date.desc())
    bookings = bookings_query.paginate(page=page, per_page=per_page)
    
    next_url = url_for('routes.admin_bookings', page=bookings.next_num) if bookings.has_next else None
    prev_url = url_for('routes.admin_bookings', page=bookings.prev_num) if bookings.has_prev else None
    
    return render_template(
        'admin/bookings.html',
        bookings=bookings,
        page=page,
        next_url=next_url,
        prev_url=prev_url
    )

# View booking details
@routes_bp.route('/admin/bookings/<booking_id>')
@login_required
def admin_booking_details(booking_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    return render_template(
        'admin/booking_details.html',
        booking=booking
    )

# Update booking status
@routes_bp.route('/admin/bookings/update-status/<booking_id>', methods=['POST'])
@login_required
def admin_update_booking_status(booking_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    booking.status = request.form.get('booking_status')
    
    # If status is changed to Cancelled, free up the seats
    if booking.status == "Cancelled":
        for detail in booking.booking_details:
            seat = detail.seat
            seat.is_booked = False
    
    db.session.commit()
    
    flash(f'Booking status updated to {booking.status}', 'success')
    return redirect(url_for('routes.admin_bookings'))

# Update payment status
@routes_bp.route('/admin/bookings/update-payment/<booking_id>', methods=['POST'])
@login_required
def admin_update_payment_status(booking_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    booking.payment_status = request.form.get('payment_status')
    
    db.session.commit()
    
    flash(f'Payment status updated to {booking.payment_status}', 'success')
    return redirect(url_for('routes.admin_bookings'))

# Cancel booking
@routes_bp.route('/admin/bookings/cancel/<booking_id>', methods=['POST'])
@login_required
def admin_cancel_booking(booking_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    # Mark booking as cancelled
    booking.status = "Cancelled"
    
    # Free up seats
    for detail in booking.booking_details:
        seat = detail.seat
        seat.is_booked = False
    
    # Process refund if checked
    if request.form.get('process_refund'):
        booking.payment_status = "Refunded"
    
    db.session.commit()
    
    flash(f'Booking {booking.booking_reference} has been cancelled', 'success')
    return redirect(url_for('routes.admin_bookings'))

# Admin airports
@routes_bp.route('/admin/airports')
@login_required
def admin_airports():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))

    # Pagination, sorting, and search
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'code')
    order = request.args.get('order', 'asc')

    query = Airport.query

    if search:
        query = query.filter(
            or_(
                Airport.code.ilike(f'%{search}%'),
                Airport.city.ilike(f'%{search}%'),
                Airport.country.ilike(f'%{search}%'),
                Airport.name.ilike(f'%{search}%')
            )
        )

    # Sorting
    sort_column = getattr(Airport, sort, Airport.code)
    if order == 'desc':
        sort_column = sort_column.desc()
    else:
        sort_column = sort_column.asc()
    query = query.order_by(sort_column)

    airports = query.paginate(page=page, per_page=per_page)

    return render_template(
        'admin/airports.html',
        airports=airports
    )

# Admin aircraft
@routes_bp.route('/admin/aircraft')
@login_required
def admin_aircraft():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    # Add sorting if needed
    sort = request.args.get('sort', 'model')
    order = request.args.get('order', 'asc')
    sort_column = getattr(Aircraft, sort, Aircraft.model)
    if order == 'desc':
        sort_column = sort_column.desc()
    else:
        sort_column = sort_column.asc()
    query = Aircraft.query.order_by(sort_column)
    aircraft = query.paginate(page=page, per_page=per_page)
    return render_template(
        'admin/aircraft.html',
        aircraft=aircraft
    )
# Manage flight seats
@routes_bp.route('/admin/flights/<flight_id>/seats', methods=['GET', 'POST'])
@login_required
def admin_flight_seats(flight_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    flight = Flight.query.get_or_404(flight_id)
    
    # Get all seats for this flight
    seats = Seat.query.filter_by(flight_id=flight.id).order_by(Seat.seat_number).all()
    
    if request.method == 'POST':
        # Handle seat updates (e.g., marking as booked/unbooked)
        for seat in seats:
            is_booked = request.form.get(f'seat_{seat.id}')
            seat.is_booked = bool(is_booked == 'on')
        db.session.commit()
        flash('Seat statuses updated successfully', 'success')
        return redirect(url_for('routes.admin_flight_seats', flight_id=flight_id))
    
    # Group seats by class for display
    seat_classes = {}
    for seat in seats:
        if seat.seat_class not in seat_classes:
            seat_classes[seat.seat_class] = []
        seat_classes[seat.seat_class].append(seat)
    
    return render_template(
        'admin/flight_seats.html',
        flight=flight,
        seat_classes=seat_classes
    )
# View bookings for a specific flight
@routes_bp.route('/admin/flights/<flight_id>/bookings')
@login_required
def admin_flight_bookings(flight_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    flight = Flight.query.get_or_404(flight_id)
    
    # Get all bookings for this flight
    bookings = Booking.query.filter_by(flight_id=flight.id).order_by(Booking.booking_date.desc()).all()
    
    return render_template(
        'admin/flight_bookings.html',
        flight=flight,
        bookings=bookings
    )
# Add new airport
@routes_bp.route('/admin/airports/add', methods=['GET', 'POST'])
@login_required
def admin_add_airport():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        city = request.form.get('city')
        country = request.form.get('country')
        
        # Validation
        if not code or len(code) != 3:
            flash('Airport code must be exactly 3 characters', 'danger')
            return render_template('admin/add_airport.html')
        
        if Airport.query.filter_by(code=code).first():
            flash('Airport code already exists', 'danger')
            return render_template('admin/add_airport.html')
        
        # Create new airport
        airport = Airport(code=code.upper(), name=name, city=city, country=country)
        db.session.add(airport)
        db.session.commit()
        
        flash('Airport added successfully', 'success')
        return redirect(url_for('routes.admin_airports'))
    
    return render_template('admin/add_airport.html')
# Edit airport
@routes_bp.route('/admin/airports/edit/<airport_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_airport(airport_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    airport = Airport.query.get_or_404(airport_id)
    
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        city = request.form.get('city')
        country = request.form.get('country')
        
        if not code or len(code) != 3:
            flash('Airport code must be exactly 3 characters', 'danger')
            return render_template('admin/edit_airport.html', airport=airport)
        
        existing_airport = Airport.query.filter(Airport.code == code, Airport.id != airport.id).first()
        if existing_airport:
            flash('Airport code already exists', 'danger')
            return render_template('admin/edit_airport.html', airport=airport)
        
        airport.code = code.upper()
        airport.name = name
        airport.city = city
        airport.country = country
        db.session.commit()
        
        flash('Airport updated successfully', 'success')
        return redirect(url_for('routes.admin_airports'))
    
    return render_template('admin/edit_airport.html', airport=airport)

# Delete airport
@routes_bp.route('/admin/airports/delete/<airport_id>', methods=['POST'])
@login_required
def admin_delete_airport(airport_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    airport = Airport.query.get_or_404(airport_id)
    
    if airport.departing_flights or airport.arriving_flights:
        flash('Cannot delete airport with associated flights', 'danger')
        return redirect(url_for('routes.admin_airports'))
    
    db.session.delete(airport)
    db.session.commit()
    
    flash('Airport deleted successfully', 'success')
    return redirect(url_for('routes.admin_airports'))
@routes_bp.route('/admin/aircraft/add', methods=['GET', 'POST'])
@login_required
def admin_add_aircraft():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    if request.method == 'POST':
        model = request.form.get('model')
        capacity = request.form.get('capacity')
        
        if not model or not capacity:
            flash('All fields are required', 'danger')
            return render_template('admin/add_aircraft.html')
        
        capacity = int(capacity)
        if capacity <= 0:
            flash('Capacity must be a positive number', 'danger')
            return render_template('admin/add_aircraft.html')
        
        aircraft = Aircraft(model=model, capacity=capacity)
        db.session.add(aircraft)
        db.session.commit()
        
        flash('Aircraft added successfully', 'success')
        return redirect(url_for('routes.admin_aircraft'))
    
    return render_template('admin/add_aircraft.html')
@routes_bp.route('/admin/aircraft/edit/<aircraft_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_aircraft(aircraft_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    aircraft = Aircraft.query.get_or_404(aircraft_id)
    
    if request.method == 'POST':
        model = request.form.get('model')
        capacity = request.form.get('capacity')
        
        if not model or not capacity:
            flash('All fields are required', 'danger')
            return render_template('admin/edit_aircraft.html', aircraft=aircraft)
        
        capacity = int(capacity)
        if capacity <= 0:
            flash('Capacity must be a positive number', 'danger')
            return render_template('admin/edit_aircraft.html', aircraft=aircraft)
        
        aircraft.model = model
        aircraft.capacity = capacity
        db.session.commit()
        
        flash('Aircraft updated successfully', 'success')
        return redirect(url_for('routes.admin_aircraft'))
    
    return render_template('admin/edit_aircraft.html', aircraft=aircraft)
@routes_bp.route('/admin/aircraft/delete/<aircraft_id>', methods=['POST'])
@login_required
def admin_delete_aircraft(aircraft_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    aircraft = Aircraft.query.get_or_404(aircraft_id)
    if Flight.query.filter_by(aircraft_id=aircraft.id).first():
        flash('Cannot delete aircraft with scheduled flights', 'danger')
    else:
        db.session.delete(aircraft)
        db.session.commit()
        flash('Aircraft deleted successfully', 'success')
    
    return redirect(url_for('routes.admin_aircraft'))
@routes_bp.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
def admin_add_user():
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        is_admin = request.form.get('is_admin') == 'on'  # Checkbox
        
        # Validation
        if not all([username, email, password, first_name, last_name]):
            flash('All fields are required', 'danger')
            return render_template('admin/add_user.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
            return render_template('admin/add_user.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('admin/add_user.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('User added successfully', 'success')
        return redirect(url_for('routes.admin_users'))
    
    return render_template('admin/add_user.html')
@routes_bp.route('/admin/users/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        is_admin = request.form.get('is_admin') == 'on'  # Checkbox
        
        # Validation
        if not all([username, email, first_name, last_name]):
            flash('All fields are required', 'danger')
            return render_template('admin/edit_user.html', user=user)
        
        if User.query.filter(and_(User.username == username, User.id != user.id)).first():
            flash('Username already taken', 'danger')
            return render_template('admin/edit_user.html', user=user)
        
        if User.query.filter(and_(User.email == email, User.id != user.id)).first():
            flash('Email already registered', 'danger')
            return render_template('admin/edit_user.html', user=user)
        
        # Update user details
        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_admin = is_admin
        
        db.session.commit()
        
        flash('User updated successfully', 'success')
        return redirect(url_for('routes.admin_users'))
    
    return render_template('admin/edit_user.html', user=user)
@routes_bp.route('/admin/users/bookings/<user_id>')
@login_required
def admin_user_bookings(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    user = User.query.get_or_404(user_id)
    # Pagination and sorting
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'date-desc')
    query = Booking.query.filter_by(user_id=user.id)
    if sort == 'date-desc':
        query = query.order_by(Booking.booking_date.desc())
    elif sort == 'date-asc':
        query = query.order_by(Booking.booking_date.asc())
    elif sort == 'price-desc':
        query = query.order_by(Booking.total_price.desc())
    elif sort == 'price-asc':
        query = query.order_by(Booking.total_price.asc())
    elif sort == 'status':
        query = query.order_by(Booking.status.asc())
    elif sort == 'payment':
        query = query.order_by(Booking.payment_status.asc())
    else:
        query = query.order_by(Booking.booking_date.desc())
    bookings = query.paginate(page=page, per_page=20)
    return render_template('admin/user_bookings.html', user=user, bookings=bookings, sort=sort)

@routes_bp.route('/admin/users/delete/<user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access the admin area', 'danger')
        return redirect(url_for('routes.index'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('routes.admin_users'))
    
    # Check for bookings
    if user.bookings:
        flash('Cannot delete user with existing bookings', 'danger')
        return redirect(url_for('routes.admin_users'))
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {user.username} deleted successfully', 'success')
    return redirect(url_for('routes.admin_users'))




@routes_bp.route('/admin/reports', methods=['GET'])
def admin_reports():
    # Get the date filter from the request
    date_filter = request.args.get('date_filter', 'last_30_days')
    current_date = datetime(2025, 3, 24)  # Current date as per your setup

    # Determine the start date based on the filter
    if date_filter == 'last_7_days':
        start_date = current_date - timedelta(days=7)
    elif date_filter == 'last_30_days':
        start_date = current_date - timedelta(days=30)
    elif date_filter == 'last_90_days':
        start_date = current_date - timedelta(days=90)
    else:  # all_time
        start_date = datetime(2000, 1, 1)  # A date far in the past to include all data

    # Summary Cards Data
    # Total Users
    total_users = User.query.count()
    admin_users = User.query.filter_by(is_admin=True).count()
    regular_users = total_users - admin_users

    # Total Bookings
    total_bookings = Booking.query.count()
    reserved_bookings = Booking.query.filter_by(status="Reserved").count()
    confirmed_bookings = Booking.query.filter_by(status="Confirmed").count()
    cancelled_bookings = Booking.query.filter_by(status="Cancelled").count()

    # Total Flights
    total_flights = Flight.query.count()
    scheduled_flights = Flight.query.filter_by(status="Scheduled").count()
    departed_flights = Flight.query.filter(Flight.status.in_(["Completed", "Cancelled"])).count()

    # Total Revenue (from confirmed bookings)
    total_revenue = db.session.query(db.func.sum(Booking.total_price))\
        .filter(Booking.status == "Confirmed").scalar() or 0

    # Frequent Flyer Stats
    ff_stats = db.session.query(User.frequent_flyer_status, db.func.count(User.id))\
        .group_by(User.frequent_flyer_status).all()

    # Booking Trends Over Time
    booking_trends = db.session.query(
        db.func.date(Booking.booking_date),
        Booking.status,
        db.func.count(Booking.id)
    )\
        .filter(Booking.booking_date >= start_date, Booking.booking_date <= current_date)\
        .group_by(db.func.date(Booking.booking_date), Booking.status)\
        .order_by(db.func.date(Booking.booking_date)).all()

    # Process booking trends data
    booking_dates = sorted(set(str(bt[0]) for bt in booking_trends))
    reserved_data = [0] * len(booking_dates)
    confirmed_data = [0] * len(booking_dates)
    cancelled_data = [0] * len(booking_dates)

    for date, status, count in booking_trends:
        date_idx = booking_dates.index(str(date))
        if status == "Reserved":
            reserved_data[date_idx] = count
        elif status == "Confirmed":
            confirmed_data[date_idx] = count
        elif status == "Cancelled":
            cancelled_data[date_idx] = count

    # Revenue Trends (Completed Payments)
    revenue_trends = db.session.query(db.func.date(Payment.payment_date), db.func.sum(Payment.amount))\
        .filter(Payment.status.in_(["Completed", "Paid"]), 
                Payment.payment_date >= start_date, 
                Payment.payment_date <= current_date)\
        .group_by(db.func.date(Payment.payment_date))\
        .order_by(db.func.date(Payment.payment_date)).all()
    revenue_trends_labels = [str(rt[0]) for rt in revenue_trends]
    revenue_trends_data = [rt[1] for rt in revenue_trends]

    # Refunded Trends (Refunded Payments)
    refunded_trends = db.session.query(db.func.date(Payment.payment_date), db.func.sum(Payment.amount))\
        .filter(Payment.status == "Refunded", 
                Payment.payment_date >= start_date, 
                Payment.payment_date <= current_date)\
        .group_by(db.func.date(Payment.payment_date))\
        .order_by(db.func.date(Payment.payment_date)).all()
    refunded_trends_labels = [str(rt[0]) for rt in refunded_trends]
    refunded_trends_data = [rt[1] for rt in refunded_trends]

    # Align labels for both revenue and refunded datasets
    all_dates = sorted(set(revenue_trends_labels + refunded_trends_labels))
    revenue_data_aligned = [0] * len(all_dates)
    refunded_data_aligned = [0] * len(all_dates)

    for i, date in enumerate(all_dates):
        if date in revenue_trends_labels:
            revenue_data_aligned[i] = revenue_trends_data[revenue_trends_labels.index(date)]
        if date in refunded_trends_labels:
            refunded_data_aligned[i] = refunded_trends_data[refunded_trends_labels.index(date)]

    # Top Destinations by Bookings
    top_destinations = db.session.query(
        Airport.city,
        db.func.count(Booking.id)
    )\
        .join(Flight, Flight.destination_id == Airport.id)\
        .join(Booking, Booking.flight_id == Flight.id)\
        .filter(Booking.booking_date >= start_date, Booking.booking_date <= current_date)\
        .group_by(Airport.city)\
        .order_by(db.func.count(Booking.id).desc())\
        .limit(5).all()
    top_destinations_labels = [td[0] for td in top_destinations]
    top_destinations_data = [td[1] for td in top_destinations]

    # Flight Utilization (Top 5 Flights) - Fixed Query
    # Create aliases for the Airport table to distinguish between origin and destination
    OriginAirport = aliased(Airport, name='origin_airport')
    DestAirport = aliased(Airport, name='dest_airport')

    flight_utilization = db.session.query(
        Flight.id,
        Flight.flight_number,
        OriginAirport.code.label('origin_code'),
        DestAirport.code.label('dest_code'),
        db.func.count(Seat.id).filter(Seat.is_booked == True) * 100.0 / db.func.count(Seat.id)
    )\
        .join(Seat, Seat.flight_id == Flight.id)\
        .join(OriginAirport, Flight.origin_id == OriginAirport.id, isouter=True)\
        .join(DestAirport, Flight.destination_id == DestAirport.id, isouter=True)\
        .filter(Flight.departure_time >= start_date, Flight.departure_time <= current_date)\
        .group_by(Flight.id, Flight.flight_number, OriginAirport.code, DestAirport.code)\
        .order_by(db.func.count(Seat.id).filter(Seat.is_booked == True).desc())\
        .limit(5).all()
    flight_ids = [fu[0] for fu in flight_utilization]
    flight_utilization_labels = [f"{fu[1]} ({fu[2]} → {fu[3]})" for fu in flight_utilization]
    flight_utilization_data = [round(fu[4], 2) for fu in flight_utilization if fu[4] is not None]

    # Increase in Users Over Time
    user_growth = db.session.query(db.func.date(User.date_joined), db.func.count(User.id))\
        .filter(User.date_joined >= start_date, User.date_joined <= current_date)\
        .group_by(db.func.date(User.date_joined))\
        .order_by(db.func.date(User.date_joined)).all()
    user_growth_labels = [str(ug[0]) for ug in user_growth]
    user_growth_data = [ug[1] for ug in user_growth]

    # Revenue Breakdown by Seat Class
    revenue_by_class = db.session.query(Seat.seat_class, db.func.sum(BookingDetail.price))\
        .join(BookingDetail, BookingDetail.seat_id == Seat.id)\
        .join(Booking, Booking.id == BookingDetail.booking_id)\
        .filter(Booking.status == "Confirmed", 
                Booking.booking_date >= start_date, 
                Booking.booking_date <= current_date)\
        .group_by(Seat.seat_class).all()
    revenue_by_class_labels = [r[0] for r in revenue_by_class]
    revenue_by_class_data = [r[1] for r in revenue_by_class]

    # Top Users by Bookings
    top_users = db.session.query(User, db.func.count(Booking.id).label('booking_count'))\
        .join(Booking, Booking.user_id == User.id)\
        .filter(Booking.booking_date >= start_date, Booking.booking_date <= current_date)\
        .group_by(User.id)\
        .order_by(db.func.count(Booking.id).desc())\
        .limit(10).all()

    # Render the template with all data
    return render_template('admin/reports.html',
                           total_users=total_users,
                           admin_users=admin_users,
                           regular_users=regular_users,
                           total_bookings=total_bookings,
                           reserved_bookings=reserved_bookings,
                           confirmed_bookings=confirmed_bookings,
                           cancelled_bookings=cancelled_bookings,
                           total_flights=total_flights,
                           scheduled_flights=scheduled_flights,
                           departed_flights=departed_flights,
                           total_revenue=total_revenue,
                           ff_stats=dict(ff_stats),
                           booking_trends_labels=booking_dates,
                           reserved_data=reserved_data,
                           confirmed_data=confirmed_data,
                           cancelled_data=cancelled_data,
                           revenue_trends_labels=all_dates,
                           revenue_trends_data=revenue_data_aligned,
                           refunded_trends_data=refunded_data_aligned,
                           top_destinations_labels=top_destinations_labels,
                           top_destinations_data=top_destinations_data,
                           flight_ids=flight_ids,
                           flight_utilization_labels=flight_utilization_labels,
                           flight_utilization_data=flight_utilization_data,
                           user_growth_labels=user_growth_labels,
                           user_growth_data=user_growth_data,
                           revenue_by_class_labels=revenue_by_class_labels,
                           revenue_by_class_data=revenue_by_class_data,
                           top_users=top_users,
                           date_filter=date_filter)
@routes_bp.route('/admin/user/<int:user_id>')
@login_required
def user_profile(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('routes.index'))
    
    user = User.query.get_or_404(user_id)
    # Add pagination and sorting for bookings
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'date-desc')
    query = Booking.query.filter_by(user_id=user.id)
    if sort == 'date-desc':
        query = query.order_by(Booking.booking_date.desc())
    elif sort == 'date-asc':
        query = query.order_by(Booking.booking_date.asc())
    elif sort == 'price-desc':
        query = query.order_by(Booking.total_price.desc())
    elif sort == 'price-asc':
        query = query.order_by(Booking.total_price.asc())
    elif sort == 'status':
        query = query.order_by(Booking.status.asc())
    elif sort == 'payment':
        query = query.order_by(Booking.payment_status.asc())
    else:
        query = query.order_by(Booking.booking_date.desc())
    bookings = query.paginate(page=page, per_page=20)
    return render_template('admin/user_bookings.html', user=user, bookings=bookings, sort=sort)

@routes_bp.route('/process-payment', methods=['POST'])
def process_payment():
    if not current_user.is_authenticated:
        flash('You need to be logged in to complete your booking', 'danger')
        return redirect(url_for('routes.login'))

    if 'selected_seats' not in session or not session['selected_seats']:
        flash('No seats selected. Please start your booking again.', 'danger')
        return redirect(url_for('routes.index'))

    # Calculate base total price from selected seats
    total_price = 0
    for flight_id, seats in session.get('seat_pricing', {}).items():
        for seat_id, price in seats.items():
            total_price += price

    if total_price <= 0:
        flash('Invalid payment amount', 'danger')
        return redirect(url_for('routes.index'))

    # Apply frequent flyer discount if applicable
    if current_user.is_authenticated and current_user.frequent_flyer_status != 'Standard':
        if current_user.frequent_flyer_status == 'Platinum':
            discount = total_price * 0.15  # 15% discount
        elif current_user.frequent_flyer_status == 'Gold':
            discount = total_price * 0.10  # 10% discount
        else:  # Silver
            discount = total_price * 0.05  # 5% discount
        
        discounted_price = total_price - discount
    else:
        discounted_price = total_price

    try:
        # Create Stripe checkout session with discounted price
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Flight Booking - SkyWings',
                    },
                    'unit_amount': int(discounted_price * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('routes.payment_callback', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('routes.index', _external=True),
            metadata={
                'user_id': current_user.id,
                'original_price': str(total_price),
                'discounted_price': str(discounted_price),
                'discount_amount': str(discount) if 'discount' in locals() else '0',
            }
        )
    except stripe.error.InvalidRequestError as e:
        flash(f'Invalid payment request: {str(e)}', 'danger')
        return redirect(url_for('routes.index'))
    except Exception as e:
        flash(f'Payment processing error: {str(e)}', 'danger')
        return redirect(url_for('routes.index'))

    # Store checkout session ID and pricing info in session
    session['stripe_checkout_session_id'] = checkout_session.id
    session['booking_total'] = total_price
    session['discounted_price'] = discounted_price
    session['discount_amount'] = discount if 'discount' in locals() else 0

    return redirect(checkout_session.url)

@routes_bp.route('/payment-callback', methods=['GET'])
def payment_callback():
    session_id = request.args.get('session_id')
    if not session_id or session_id != session.get('stripe_checkout_session_id'):
        flash('Invalid payment session', 'danger')
        return redirect(url_for('routes.index'))

    # Verify the payment
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        if checkout_session.payment_status != 'paid':
            flash('Payment was not successful. Please try again.', 'danger')
            return redirect(url_for('routes.index'))
    except stripe.error.StripeError as e:
        flash(f'Payment verification failed: {str(e)}', 'danger')
        return redirect(url_for('routes.index'))

    # Calculate total price
    total_price = sum(price for flight_id, seats in session.get('seat_pricing', {}).items() for seat_id, price in seats.items())

    # Create bookings for each flight (departure and return if applicable)
    bookings = []
    passenger_data = session.get('passenger_data', {})
    passenger_index = 1

    for flight_id, seat_ids in session.get('selected_seats', {}).items():
        booking_reference = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        flight_price = sum(session.get('seat_pricing', {}).get(flight_id, {}).get(str(seat_id), 0) for seat_id in seat_ids)

        # Create booking for this flight
        booking = Booking(
            booking_reference=booking_reference,
            user_id=current_user.id,
            flight_id=flight_id,
            status="Confirmed",
            total_price=flight_price,
            payment_status="Paid"
        )
        db.session.add(booking)
        db.session.flush()

        # Add booking details for each seat
        for seat_id in seat_ids:
            seat = Seat.query.get(seat_id)
            seat.is_booked = True
            passenger = passenger_data.get(str(passenger_index), {})
            booking_detail = BookingDetail(
                booking_id=booking.id,
                seat_id=seat_id,
                passenger_first_name=passenger.get('first_name', ''),
                passenger_last_name=passenger.get('last_name', ''),
                passenger_dob=datetime.strptime(passenger.get('dob', '2000-01-01'), '%Y-%m-%d').date(),
                passenger_passport=passenger.get('passport', ''),
                passenger_nationality=passenger.get('nationality', ''),
                special_requests=passenger.get('special_requests', ''),
                price=session.get('seat_pricing', {}).get(flight_id, {}).get(str(seat_id), 0)
            )
            db.session.add(booking_detail)
            passenger_index += 1

        # Create payment record for this booking
        payment = Payment(
            booking_id=booking.id,
            amount=flight_price,
            payment_method="Stripe",
            transaction_id=checkout_session.payment_intent,
            status="Completed"
        )
        db.session.add(payment)
        bookings.append(booking_reference)

    # Update frequent flyer miles based on total price
    current_user.frequent_flyer_miles += int(total_price / 10)
    if current_user.frequent_flyer_miles >= 50000:
        current_user.frequent_flyer_status = "Platinum"
    elif current_user.frequent_flyer_miles >= 25000:
        current_user.frequent_flyer_status = "Gold"
    elif current_user.frequent_flyer_miles >= 10000:
        current_user.frequent_flyer_status = "Silver"

    db.session.commit()

    # Clear session
    session.pop('selected_seats', None)
    session.pop('seat_pricing', None)
    session.pop('passenger_data', None)
    session.pop('search_params', None)
    session.pop('stripe_checkout_session_id', None)

    # Redirect to the confirmation page of the first booking (departure)
    return redirect(url_for('routes.booking_confirmation', booking_reference=bookings[0], all_bookings=','.join(bookings)))

import pdfkit
import os
import requests
from flask_mail import Message
from flask import render_template, make_response, url_for
from io import BytesIO

@routes_bp.route('/email-confirmation/<booking_references>')
def email_confirmation(booking_references):
    if not current_user.is_authenticated:
        flash('You need to be logged in to email your booking confirmation', 'danger')
        return redirect(url_for('routes.login'))

    booking_refs = booking_references.split(',')
    bookings = Booking.query.filter(Booking.booking_reference.in_(booking_refs)).all()

    # Security check
    for booking in bookings:
        if booking.user_id != current_user.id:
            flash('You do not have permission to email this booking', 'danger')
            return redirect(url_for('routes.index'))

    # Generate the HTML content for PDF
    html = render_template('confirmation_pdf.html', bookings=bookings)

    # Generate PDF using pdfkit
    try:
        pdf = pdfkit.from_string(html, False)  # `False` returns a bytes object
    except Exception as e:
        flash(f'Failed to generate PDF: {str(e)}', 'danger')
        return redirect(url_for('routes.booking_confirmation', booking_reference=booking_refs[0], all_bookings=booking_references))

    # Generate email content using OpenAI (same as before)
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        flash('OpenRouter API key is not configured.', 'danger')
        return redirect(url_for('routes.booking_confirmation', booking_reference=booking_refs[0], all_bookings=booking_references))

    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }

    # Prompt for OpenAI to generate email body
    prompt = f"""
    Generate a professional and concise email confirmation for a flight booking. Include the following details for each booking:

    {', '.join([f"Booking Reference: {booking.booking_reference}, Flight: {booking.flight.flight_number}, From: {booking.flight.origin_airport.city}, {booking.flight.destination_airport.city}, Departure: {booking.flight.departure_time.strftime('%Y-%m-%d %H:%M')}, Arrival: {booking.flight.arrival_time.strftime('%Y-%m-%d %H:%M')}, Price: ${booking.total_price:.2f}, Status: {booking.status}" for booking in bookings])}
    
    - First Name: {current_user.first_name}
    - Last Name: {current_user.last_name}
    - Email: {current_user.email}
    - Username: {current_user.username}
    
    The email should have:
    - A subject line like "Flight Booking Confirmation - [Booking References]"
    - A greeting addressing the user by first name (use "Dear [First Name]")
    - A brief introduction thanking the user for their booking
    - A clear list of all booking details
    - Contact information for support (e.g., skywings102914@gmail.com, +91 8220318626)
    - General policies such as check-in time, boarding time, and baggage policies
    
    Ensure the tone is professional, polite, and customer-friendly.
    """

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": "deepseek/deepseek-chat-v3-0324:free",  
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7
            }
        )

        response.raise_for_status()
        ai_response = response.json()
        email_content = ai_response['choices'][0]['message']['content'].strip()
        clean_email_content = re.sub(r'[*#]', '', email_content)
        # Extract subject and body
        lines = clean_email_content.split('\n')
        subject = lines[0].replace("Subject: ", "").strip()
        body = '\n'.join(lines[1:]).strip()

        # Send email with PDF attachment
        msg = Message(subject, recipients=[current_user.email])
        msg.html = f"""
        <html>
            <body>
                <p>{body.replace('\n', '<br>')}</p>
                <p>Best regards,<br>The SkyWings Team<br>Support: skywings102914@gmail.com | +91 8220318626</p>
            </body>
        </html>
        """


        # Attach PDF
        msg.attach(f"booking_{booking_references}.pdf", "application/pdf", pdf)

        mail.send(msg)
        flash('Booking confirmation emailed successfully with attachment!', 'success')

    except requests.exceptions.RequestException as e:
        flash(f'Failed to generate email content: {str(e)}', 'danger')
    except Exception as e:
        flash(f'Failed to send email: {str(e)}', 'danger')

    return redirect(url_for('routes.booking_confirmation', booking_reference=booking_refs[0], all_bookings=booking_references))

from xhtml2pdf import pisa
from io import BytesIO

def generate_pdf(html):
    pdf = BytesIO()
    pisa.CreatePDF(BytesIO(html.encode("utf-8")), dest=pdf)
    pdf.seek(0)
    return pdf

import pdfkit
from flask import render_template, make_response

@routes_bp.route('/download-confirmation/<booking_references>')
def download_confirmation(booking_references):
    booking_refs = booking_references.split(',')
    bookings = Booking.query.filter(Booking.booking_reference.in_(booking_refs)).all()
    
    html = render_template('confirmation_pdf.html', bookings=bookings)
    
    # Convert HTML to PDF
    pdf = pdfkit.from_string(html, False)
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=booking_{booking_references}.pdf'
    
    return response

@routes_bp.route('/boarding-pass')
def boarding_pass():
    booking_ref = request.args.get('ref')
    
    # Fetch booking with all related data
    booking = Booking.query.filter_by(booking_reference=booking_ref)\
                          .join(Flight)\
                          .join(BookingDetail)\
                          .join(Seat)\
                          .first_or_404()
    
    return render_template('boarding_pass.html',
                         booking=booking,
                         passenger=booking.booking_details[0])  

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from requests.exceptions import RequestException, ConnectionError

def send_email_in_background(app, user_data, email_type):
    def send_email():
        with app.app_context():
            @retry(retry=retry_if_exception_type((RequestException, ConnectionError)),
                   stop=stop_after_attempt(3),
                   wait=wait_fixed(2))
            def send_with_retry():
                try:
                    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
                    if not openrouter_api_key:
                        logging.error('OpenRouter API key is not configured.')
                        return

                    headers = {
                        "Authorization": f"Bearer {openrouter_api_key}",
                        "Content-Type": "application/json"
                    }

                    if email_type == "login":
                        subject_prefix = "Successful Login to SkyWings"
                        prompt = f"""
                        Generate a professional and informative email to notify a user that they have successfully logged into the SkyWings flight booking platform. The user's details are:
                        - First Name: {user_data['first_name']}
                        - Last Name: {user_data['last_name']}
                        - Email: {user_data['email']}
                        - Username: {user_data['username']}
                        The email should have:
                        - A subject line like "{subject_prefix}"
                        - A greeting addressing the user by first name (e.g., "Dear [First Name]")
                        - A brief message confirming the successful login, including the date and time of login ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                        - A reminder to contact support if the login was not initiated by them (e.g., skywings102914@gmail.com, +91 8220318626)
                        - A closing remark with best wishes
                        Ensure the tone is professional, secure, and reassuring.
                        """
                    elif email_type == "welcome":
                        subject_prefix = "Welcome to SkyWings - Your Journey Begins!"
                        prompt = f"""
                        Generate a professional and welcoming email for a new user who has just registered on a flight booking platform (SkyWings). The user's details are:
                        - First Name: {user_data['first_name']}
                        - Last Name: {user_data['last_name']}
                        - Email: {user_data['email']}
                        - Username: {user_data['username']}
                        The email should have:
                        - A subject line like "{subject_prefix}"
                        - A greeting addressing the user by first name (e.g., "Dear [First Name]")
                        - A warm welcome message, mentioning their registration and the benefits of using SkyWings (e.g., easy flight bookings, frequent flyer programs)
                        - Instructions on how to log in and set up their profile
                        - Contact information for support (e.g., skywings102914@gmail.com, +91 8220318626)
                        - A closing remark with best wishes
                        Ensure the tone is friendly, professional, and encouraging.
                        """
                    elif email_type == "logout":
                        subject_prefix = "Successful Logout from SkyWings"
                        prompt = f"""
                        Generate a professional and informative email to notify a user that they have successfully logged out of the SkyWings flight booking platform. The user's details are:
                        - First Name: {user_data['first_name']}
                        - Last Name: {user_data['last_name']}
                        - Email: {user_data['email']}
                        - Username: {user_data['username']}
                        The email should have:
                        - A subject line like "{subject_prefix}"
                        - A greeting addressing the user by first name (e.g., "Dear [First Name]")
                        - A brief message confirming the successful logout, including the date and time of logout ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                        - A reminder to contact support if they did not initiate the logout (e.g., skywings102914@gmail.com, +91 8220318626)
                        - A closing remark with best wishes
                        Ensure the tone is professional, secure, and reassuring.
                        """
                    else:
                        raise ValueError("Invalid email type")

                    response = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json={
                            "model": "deepseek/deepseek-chat-v3-0324:free",
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 1000,
                            "temperature": 0.7
                        }
                    )
                    response.raise_for_status()
                    ai_response = response.json()
                    email_content = ai_response['choices'][0]['message']['content'].strip()

                    clean_email_content = re.sub(r'[*#]', '', email_content)
                    lines = clean_email_content.split('\n')
                    subject = lines[0].replace("Subject: ", "").strip()
                    body = '\n'.join(lines[1:]).strip()

                    msg = Message(subject, recipients=[user_data['email']])
                    msg.html = f"""
                    <html>
                        <body>
                            <p>{body.replace('\n', '<br>')}</p>
                            <p>Best regards,<br>The SkyWings Team<br>Support: skywings102914@gmail.com | +91 8220318626</p>
                        </body>
                    </html>
                    """
                    with mail.connect() as conn:
                        conn.send(msg)

                except (RequestException, ConnectionError) as e:
                    logging.error(f"Network error sending {email_type} email for user {user_data['id']}: {str(e)}")
                    raise
                except Exception as e:
                    logging.error(f"Error sending {email_type} email for user {user_data['id']}: {str(e)}")

            send_with_retry()

    thread = threading.Thread(target=send_email)
    thread.daemon = True
    thread.start()
