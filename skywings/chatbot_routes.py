from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import current_user  # Import current_user from flask_login
from models import Flight, Seat, Booking, BookingDetail, Payment, User
from datetime import datetime
import stripe
import secrets
import string
import random
from extensions import db  # Import db from chatbot.py

chatbot_routes_bp = Blueprint('chatbot_routes', __name__)

# Mock API for surprise perk
def get_surprise_perk(total_price, travel_class, destination):
    """
    Mock API call to get a surprise perk based on booking details.
    In a real scenario, this would be an HTTP request to an external API.
    """
    perks = [
        "Free lounge access at your destination airport! 🏖️",
        "One extra checked bag (up to 50 lbs) for free! 🧳",
        "A complimentary in-flight meal upgrade! 🍽️",
        "Priority boarding for your flight! 🚀",
        "A $50 voucher for your next SkyWings booking! 💸"
    ]
    # Simulate API logic: higher price, better perk
    if total_price > 2000:
        perk_index = random.randint(0, 4)  # Any perk
    elif total_price > 1000:
        perk_index = random.randint(0, 3)  # Exclude voucher
    else:
        perk_index = random.randint(0, 2)  # Basic perks
    return perks[perk_index]

@chatbot_routes_bp.route('/chatbot/seat-selection/<int:flight_id>/<travel_class>/<int:passengers>')
def chatbot_seat_selection(flight_id, travel_class, passengers):
    flight = Flight.query.get_or_404(flight_id)
    seats = Seat.query.filter_by(flight_id=flight_id, seat_class=travel_class).all()
    return render_template('seat_selection.html', flight=flight, seats=seats, travel_class=travel_class, passengers=passengers)

@chatbot_routes_bp.route('/chatbot/process-seats', methods=['POST'])
def chatbot_process_seats():
    flight_id = request.form.get('flight_id')
    seat_ids = request.form.getlist('seat_ids')
    seat_pricing = {flight_id: {}}
    for seat_id in seat_ids:
        seat = Seat.query.get(seat_id)
        if seat and not seat.is_booked:
            seat_pricing[flight_id][seat_id] = session['booking_context']['final_price'] / len(seat_ids)
    session['selected_seats'] = {flight_id: seat_ids}
    session['seat_pricing'] = seat_pricing
    session.modified = True
    return redirect(url_for('chatbot_routes.chatbot_passenger_details', departure_flight=flight_id))

@chatbot_routes_bp.route('/chatbot/passenger-details')
def chatbot_passenger_details():
    departure_flight = request.args.get('departure_flight')
    return_flight = request.args.get('return_flight')
    passengers = sum(len(seats) for flight_id, seats in session.get('selected_seats', {}).items())
    return render_template('passenger_details.html', departure_flight=departure_flight, return_flight=return_flight, passengers=passengers)

@chatbot_routes_bp.route('/chatbot/process-passengers', methods=['POST'])
def chatbot_process_passengers():
    passenger_data = {}
    for i in range(1, int(request.form.get('passengers')) + 1):
        passenger_data[str(i)] = {
            'first_name': request.form.get(f'first_name_{i}'),
            'last_name': request.form.get(f'last_name_{i}'),
            'dob': request.form.get(f'dob_{i}'),
            'passport': request.form.get(f'passport_{i}'),
            'nationality': request.form.get(f'nationality_{i}'),
            'special_requests': request.form.get(f'special_requests_{i}')
        }
    session['passenger_data'] = passenger_data
    total_price = sum(price for flight_id, seats in session.get('seat_pricing', {}).items() for seat_id, price in seats.items())
    session.modified = True
    return redirect(url_for('chatbot_routes.chatbot_payment', total_price=total_price))

@chatbot_routes_bp.route('/chatbot/payment')
def chatbot_payment():
    total_price = float(request.args.get('total_price', 0))
    if total_price <= 0:
        flash('Invalid payment amount', 'danger')
        return redirect(url_for('routes.index'))  # Redirect to the original index route

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Flight Booking via Chatbot',
                    },
                    'unit_amount': int(total_price * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('chatbot_routes.chatbot_payment_callback', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('routes.index', _external=True),
        )
        session['stripe_checkout_session_id'] = checkout_session.id
        session.modified = True
        return render_template('payment.html', checkout_session_id=checkout_session.id, public_key=current_app.config['STRIPE_PUBLIC_KEY'])
    except stripe.error.StripeError as e:
        flash(f'Payment setup failed: {str(e)}', 'danger')
        return redirect(url_for('routes.index'))

@chatbot_routes_bp.route('/chatbot/payment-callback', methods=['GET'])
def chatbot_payment_callback():
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

    # Update frequent flyer miles based on total price (earned miles, not deducted)
    current_user.frequent_flyer_miles += int(total_price / 10)
    if current_user.frequent_flyer_miles >= 50000:
        current_user.frequent_flyer_status = "Platinum"
    elif current_user.frequent_flyer_miles >= 25000:
        current_user.frequent_flyer_status = "Gold"
    elif current_user.frequent_flyer_miles >= 10000:
        current_user.frequent_flyer_status = "Silver"

    # Get the surprise perk
    flight = Flight.query.get(flight_id)
    destination = flight.destination_airport.code
    travel_class = session.get('booking_context', {}).get('class', 'Economy')
    perk = get_surprise_perk(total_price, travel_class, destination)

    db.session.commit()

    # Clear session
    session.pop('selected_seats', None)
    session.pop('seat_pricing', None)
    session.pop('passenger_data', None)
    session.pop('search_params', None)
    session.pop('stripe_checkout_session_id', None)
    session.pop('booking_context', None)

    # Add the perk to the flash message
    flash(f"Surprise! To thank you for booking with SkyWings, we’ve added a special perk: {perk} 🎁 Enjoy your trip!", 'success')

    # Redirect to the confirmation page of the first booking (departure)
    return redirect(url_for('chatbot_routes.chatbot_booking_confirmation', booking_reference=bookings[0], all_bookings=','.join(bookings)))

@chatbot_routes_bp.route('/chatbot/booking-confirmation/<booking_reference>')
def chatbot_booking_confirmation(booking_reference):
    booking = Booking.query.filter_by(booking_reference=booking_reference, user_id=current_user.id).first_or_404()
    all_bookings = request.args.get('all_bookings', booking_reference).split(',')
    bookings = [Booking.query.filter_by(booking_reference=ref, user_id=current_user.id).first() for ref in all_bookings]
    return render_template('booking_confirmation.html', bookings=bookings)