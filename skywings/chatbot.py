import json
import re
from urllib import parse
from flask import session
from openai import OpenAI
from sqlalchemy import or_, func
from models import Airport, Flight, Booking, Seat, User
from datetime import datetime, timedelta
import os

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    timeout=30.0,  # Add timeout
    default_headers={
        "HTTP-Referer": "http://localhost:5000",  # Required by OpenRouter
        "X-Title": "SkyWings Chatbot"             # Optional but recommended
    }
)
# print(os.getenv("OPENROUTER_API_KEY"))
def get_database_snapshot(search_params=None):
    """Get a filtered snapshot of the database based on search parameters"""
    snapshot = {
        "airports": [],
        "flights": [],
        "seats": []
    }
    
    # Always include all airports (they're relatively small in number)
    airports = Airport.query.all()
    snapshot["airports"] = [
        {
            "id": airport.id,
            "code": airport.code,
            "city": airport.city,
            "country": airport.country,
            "name": airport.name
        } for airport in airports
    ]
    
    # Only include flights if we have search parameters
    if search_params:
        # Base query for scheduled flights only
        flights_query = Flight.query.filter(Flight.status == "Scheduled")
        
        # Apply filters based on search parameters
        if 'origin' in search_params:
            origin_airport = Airport.query.filter(
                or_(
                    Airport.code.ilike(f"%{search_params['origin']}%"),
                    Airport.city.ilike(f"%{search_params['origin']}%"),
                    Airport.name.ilike(f"%{search_params['origin']}%")
                )
            ).first()
            if origin_airport:
                flights_query = flights_query.filter(Flight.origin_id == origin_airport.id)
        
        if 'destination' in search_params:
            dest_airport = Airport.query.filter(
                or_(
                    Airport.code.ilike(f"%{search_params['destination']}%"),
                    Airport.city.ilike(f"%{search_params['destination']}%"),
                    Airport.name.ilike(f"%{search_params['destination']}%")
                )
            ).first()
            if dest_airport:
                flights_query = flights_query.filter(Flight.destination_id == dest_airport.id)
        
        if 'departure_date' in search_params:
            try:
                departure_date = datetime.strptime(search_params['departure_date'], '%Y-%m-%d').date()
                flights_query = flights_query.filter(
                    func.date(Flight.departure_time) == departure_date
                )
            except ValueError:
                pass
        
        # Limit to 50 flights to prevent too much data
        flights = flights_query.order_by(Flight.departure_time.asc()).limit(50).all()
        
        snapshot["flights"] = [
            {
                "id": flight.id,
                "flight_number": flight.flight_number,
                "origin_id": flight.origin_id,
                "destination_id": flight.destination_id,
                "departure_time": flight.departure_time.isoformat(),
                "arrival_time": flight.arrival_time.isoformat(),
                "base_price_economy": float(flight.economy_base_price),
                "base_price_business": float(flight.business_base_price),
                "base_price_first": float(flight.first_class_base_price),
                "aircraft_id": flight.aircraft_id
            } for flight in flights
        ]
        
        # Only include seats for these flights and the requested class if specified
        if flights:
            seats_query = Seat.query.filter(
                Seat.flight_id.in_([f.id for f in flights])
            )
            
            if 'travel_class' in search_params:
                seats_query = seats_query.filter(
                    Seat.seat_class.ilike(search_params['travel_class']))
            
            # Only include available seats if we know passenger count
            if 'passengers' in search_params:
                seats_query = seats_query.filter(Seat.is_booked == False)
            
            # Limit seats to prevent too much data
            seats = seats_query.limit(200).all()
            
            snapshot["seats"] = [
                {
                    "id": seat.id,
                    "flight_id": seat.flight_id,
                    "seat_number": seat.seat_number,
                    "seat_class": seat.seat_class,
                    "is_booked": seat.is_booked
                } for seat in seats
            ]
    
    return snapshot

def extract_search_params(user_message):
    search_params = {}
    
    # Origin and Destination
    location_pattern = r'(?:from|to)\s+([A-Za-z]{3}|[A-Za-z\s]+)'
    locations = re.findall(location_pattern, user_message, re.IGNORECASE)
    if len(locations) >= 1:
        search_params['origin'] = locations[0].strip()
    if len(locations) >= 2:
        search_params['destination'] = locations[1].strip()
    
    # Date
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})|(?:on|for)\s+(\w+\s+\d{1,2}(?:\s+\d{4})?)', user_message, re.IGNORECASE)
    if date_match:
        date_str = next(d for d in date_match.groups() if d)
        try:
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d' if '-' in date_str else '%B %d %Y')
            search_params['departure_date'] = parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            pass
    
    # Travel class
    class_match = re.search(r'(Economy|Business|First\s+Class)', user_message, re.IGNORECASE)
    if class_match:
        search_params['travel_class'] = class_match.group(1)
    
    # Passengers
    passenger_match = re.search(r'(\d+)\s*(?:passenger|person|people|traveler)', user_message, re.IGNORECASE)
    if passenger_match:
        search_params['passengers'] = int(passenger_match.group(1))
    else:
        # Default to 1 passenger if not specified
        search_params['passengers'] = 1
    
    # Return date
    return_match = re.search(r'return(?:ing)?\s+(?:on)?\s*(\d{4}-\d{2}-\d{2}|(?:\w+\s+\d{1,2}(?:\s+\d{4})?))', user_message, re.IGNORECASE)
    if return_match:
        return_date_str = return_match.group(1)
        try:
            parsed_return = datetime.strptime(return_date_str, '%Y-%m-%d' if '-' in return_date_str else '%B %d %Y')
            search_params['return_date'] = parsed_return.strftime('%Y-%m-%d')
        except ValueError:
            pass
    
    return search_params if search_params else None

def call_api_with_data(user_message, db_snapshot, chat_history):
    prompt = f"""
    You are a friendly, witty flight booking assistant for SkyWings Airlines. ✈️
    The user said: '{user_message}'.
    Chat history: {json.dumps(chat_history[-3:])} (last 3 turns).
    Here's our filtered database snapshot: {json.dumps(db_snapshot, indent=2)}.

    Rules:
    1. For flight searches:
       - If origin/destination are missing, ask: "Where would you like to fly from and to?"
       - If date is missing, ask: "When would you like to travel?"
       - If class is missing, ask: "Which class - Economy, Business, or First Class?"
       - If all details are present, show flight options with prices
    
    2. For booking confirmations:
       - Verify all details are correct
       - Return JSON with booking confirmation and button to proceed
    
    3. For general questions:
       - Answer naturally with airline-related knowledge
       - Use emojis to make responses friendly
       - help as a travel guide in planning for their trip
       - Provide information about destinations, travel tips, etc.
    4. Pricing Logic:
       - Base prices are in the database
       - Apply these multipliers:
         - Days before departure:
           >60 days: 0.8x
           31-60 days: 0.9x
           15-30 days: 1.0x
           8-14 days: 1.1x
           3-7 days: 1.2x
           ≤2 days: 1.3x
         - Seat availability:
           <30% booked: 0.9x
           30-60% booked: 1.0x
           60-80% booked: 1.1x
           >80% booked: 1.2x
       - Round final price to 2 decimal places
    
    Current date: {datetime.now().strftime('%Y-%m-%d')}.
    """
    
    try:
        completion = client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=350,
            temperature=0.7
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error calling API: {str(e)}")
        return "Sorry, I'm having trouble connecting to our systems. Please try again later."

def extract_flight_info(chat_history):
    flight_info = {}
    
    for msg in reversed(chat_history[-10:]):  # Look at the last 5 messages
        if msg[0] in ["Bot", "You"]:
            # Flight number
            flight_match = re.search(r'(SW|AA|UA|BA|LH|SQ|AF|JL|QF)\d+', msg[1])
            if flight_match and 'flight_number' not in flight_info:
                flight_number = flight_match.group()
                flight = Flight.query.filter_by(flight_number=flight_number).first()
                if flight:
                    flight_info.update({
                        'flight_number': flight_number,
                        'flight_id': flight.id,
                        'origin': flight.origin_airport.code,
                        'destination': flight.destination_airport.code,
                        'departure_date': flight.departure_time.strftime('%Y-%m-%d')
                    })
            
            # Origin/Destination
            location_pattern = r'(?:from|to)\s+([A-Za-z]{3}|[A-Za-z\s]+)'
            locations = re.findall(location_pattern, msg[1], re.IGNORECASE)
            if len(locations) >= 2:
                flight_info['origin'] = locations[0].strip()
                flight_info['destination'] = locations[1].strip()
            
            # Date (prioritize the most recent date mentioned)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})|(?:on|for)\s+(\w+\s+\d{1,2}(?:\s+\d{4})?)', msg[1], re.IGNORECASE)
            if date_match:
                date_str = next(d for d in date_match.groups() if d)
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d' if '-' in date_str else '%B %d %Y')
                    flight_info['departure_date'] = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    pass
            
            # Travel class
            class_match = re.search(r'(Economy|Business|First\s+Class)', msg[1], re.IGNORECASE)
            if class_match:
                flight_info['travel_class'] = class_match.group(1)
            
            # Passengers
            passenger_match = re.search(r'(\d+)\s*(?:passenger|person|people|traveler)', msg[1], re.IGNORECASE)
            if passenger_match:
                flight_info['passengers'] = int(passenger_match.group(1))
            else:
                flight_info['passengers'] = 1  # Default
    
    # Validate the flight exists on the specified date
    if 'flight_number' in flight_info and 'departure_date' in flight_info:
        flight = Flight.query.filter_by(flight_number=flight_info['flight_number']).first()
        if flight:
            flight_date = flight.departure_time.strftime('%Y-%m-%d')
            if flight_date != flight_info['departure_date']:
                # If the date doesn't match the flight's actual date, update it
                flight_info['departure_date'] = flight_date
    
    return flight_info if flight_info else None

def handle_chatbot_message(user_message):
    user_message = user_message.strip()
    if "chat_messages" not in session:
        session["chat_messages"] = []
    chat_history = session["chat_messages"]
    
    def add_to_session(sender, text):
        session["chat_messages"].append([sender, text])
        session.modified = True

    # Extract search parameters from the message
    search_params = extract_search_params(user_message)
    
    # Set default travel class to Economy unless specified
    if not search_params or 'travel_class' not in search_params:
        if search_params is None:
            search_params = {}
        search_params['travel_class'] = 'Economy'
    
    # Get a filtered database snapshot based on the search parameters
    db_snapshot = get_database_snapshot(search_params)
    
    # Handle greeting or initial message
    if not chat_history or user_message.lower() in ['hi', 'hello', 'hey']:
        add_to_session("You", user_message)
        response = (
            "Hey there! ✈️ Ready to take off with SkyWings Airlines? Where would you like to fly today? "
            "Just say something like:\n"
            "*\"I'd like to fly from New York to London on April 5th in Economy class\"*\n\n"
            "Or ask me anything about our flights and services! 😊\n\n"
            "(Pro tip: I can help you book to amazing destinations like Tokyo 🇯🇵, Paris 🇫🇷, or Dubai 🇦🇪)"
        )
        add_to_session("Bot", response)
        return {"response": response}

    # Handle explicit booking confirmation
    if any(keyword in user_message.lower() for keyword in ['book', 'confirm', 'yes', 'proceed']):
        flight_info = extract_flight_info(chat_history)
        
        # Ensure default travel class is Economy if not specified
        if flight_info and 'travel_class' not in flight_info:
            flight_info['travel_class'] = 'Economy'
        
        # Check if we have sufficient data for booking
        required_fields = ['origin', 'destination', 'departure_date', 'flight_id']
        if flight_info and all(field in flight_info and flight_info[field] for field in required_fields):
            # Sufficient data present, proceed with booking confirmation
            flight_info.setdefault('passengers', 1)
            
            add_to_session("You", user_message)
            
            session['search_params'] = {
                'origin': flight_info.get('origin'),
                'destination': flight_info.get('destination'),
                'departure_date': flight_info.get('departure_date'),
                'return_date': flight_info.get('return_date', ''),
                'travel_class': flight_info.get('travel_class'),
                'passengers': flight_info.get('passengers')
            }
            
            origin_airport = Airport.query.filter_by(code=flight_info.get('origin')).first()
            dest_airport = Airport.query.filter_by(code=flight_info.get('destination')).first()
            
            origin_city = origin_airport.city if origin_airport else flight_info.get('origin')
            dest_city = dest_airport.city if dest_airport else flight_info.get('destination')
            
            response_text = (
                f"Awesome! I'll book {flight_info.get('flight_number', 'your flight')} "
                f"from {origin_city} ({flight_info.get('origin')}) "
                f"to {dest_city} ({flight_info.get('destination')}) "
                f"on {flight_info.get('departure_date')} for {flight_info.get('passengers')} "
                f"in {flight_info.get('travel_class')} class. ✈️"
            )
            
            return {
                "response": response_text,
                "button": {
                    "label": "Continue Booking",
                    "url": f"/search?flight_id={flight_info.get('flight_id')}"
                }
            }
        else:
            # Insufficient data, prompt for missing details or correct date
            missing_fields = [field for field in required_fields if not flight_info or field not in flight_info or not flight_info[field]]
            add_to_session("You", user_message)
            
            if 'origin' in missing_fields:
                response = "Where would you like to fly from? Please tell me the origin airport or city! 🛫"
            elif 'destination' in missing_fields:
                response = "Where are you flying to? Please specify your destination! 🛬"
            elif 'departure_date' in missing_fields:
                response = "When would you like to travel? Please give me a date (e.g., April 5th or 2025-04-05)! 📅"
            else:
                # If flight_id is missing, check date validity against database
                if flight_info and 'departure_date' in flight_info:
                    requested_date = datetime.strptime(flight_info['departure_date'], '%Y-%m-%d').date()
                    available_flights = [
                        f for f in db_snapshot.get('flights', [])
                        if flight_info.get('origin') and flight_info.get('destination') and
                           f['origin_id'] == Airport.query.filter_by(code=flight_info['origin']).first().id and
                           f['destination_id'] == Airport.query.filter_by(code=flight_info['destination']).first().id
                    ]
                    available_dates = sorted(set(datetime.fromisoformat(f['departure_time']).strftime('%Y-%m-%d') for f in available_flights))
                    
                    if available_flights and flight_info['departure_date'] not in available_dates:
                        response = (
                            f"Sorry, we don’t have flights from {flight_info.get('origin')} to {flight_info.get('destination')} "
                            f"on {flight_info['departure_date']}. Here are some available dates: "
                            f"{', '.join(available_dates[:3])}. Which date works for you? 📅"
                        )
                    else:
                        response = call_api_with_data(user_message, db_snapshot, chat_history)
                else:
                    response = call_api_with_data(user_message, db_snapshot, chat_history)
            
            add_to_session("Bot", response)
            return {"response": response}

    # Handle flight search requests
    if any(keyword in user_message.lower() for keyword in ['search', 'find', 'look for', 'flights']):
        flight_info = extract_flight_info(chat_history)
        
        # Set default travel class if not specified
        if flight_info and 'travel_class' not in flight_info:
            flight_info['travel_class'] = 'Economy'
        
        if not flight_info or not all(k in flight_info for k in ['passengers', 'travel_class']):
            response = call_api_with_data(user_message, db_snapshot, chat_history)
            add_to_session("You", user_message)
            add_to_session("Bot", response)
            return {"response": response}
        
        if search_params and search_params.get('origin') and search_params.get('destination'):
            add_to_session("You", user_message)
            session['search_params'] = search_params
            
            origin_airport = Airport.query.filter(
                or_(Airport.code.ilike(f"%{search_params['origin']}%"), 
                    Airport.city.ilike(f"%{search_params['origin']}%"))
            ).first()
            
            destination_airport = Airport.query.filter(
                or_(Airport.code.ilike(f"%{search_params['destination']}%"), 
                    Airport.city.ilike(f"%{search_params['destination']}%"))
            ).first()
            
            if origin_airport and destination_airport:
                # Validate departure date against available flights
                matching_flights = [
                    f for f in db_snapshot.get('flights', [])
                    if f['origin_id'] == origin_airport.id and f['destination_id'] == destination_airport.id
                ]
                
                if search_params.get('departure_date'):
                    requested_date = datetime.strptime(search_params['departure_date'], '%Y-%m-%d').date()
                    available_dates = sorted(set(datetime.fromisoformat(f['departure_time']).strftime('%Y-%m-%d') for f in matching_flights))
                    
                    if matching_flights and search_params['departure_date'] not in available_dates:
                        response = (
                            f"Sorry, no flights from {origin_airport.code} to {destination_airport.code} "
                            f"on {search_params['departure_date']}. Available dates are: "
                            f"{', '.join(available_dates[:3])}. Pick one or ask me to search again! 📅"
                        )
                        add_to_session("Bot", response)
                        return {"response": response}
                
                response_text = (
                    f"Found flights from {origin_airport.city} ({origin_airport.code}) "
                    f"to {destination_airport.city} ({destination_airport.code}) "
                    f"on {search_params.get('departure_date', 'your selected date')}. "
                    "Here are your options:"
                )
                
                if matching_flights:
                    flight_options = []
                    for flight in matching_flights[:3]:
                        origin = next(a for a in db_snapshot['airports'] if a['id'] == flight['origin_id'])
                        dest = next(a for a in db_snapshot['airports'] if a['id'] == flight['destination_id'])
                        
                        departure_date = datetime.fromisoformat(flight['departure_time']).date()
                        days_before = (departure_date - datetime.now().date()).days
                        
                        price_multiplier = (
                            0.8 if days_before > 60 else
                            0.9 if days_before > 30 else
                            1.0 if days_before > 14 else
                            1.1 if days_before > 7 else
                            1.2 if days_before > 2 else
                            1.3
                        )
                        
                        base_price = flight[f'base_price_{search_params["travel_class"].lower().replace(" ", "_")}']
                        price = round(base_price * price_multiplier, 2)
                        
                        flight_options.append(
                            f"{flight['flight_number']}: {origin['code']}→{dest['code']} "
                            f"at {datetime.fromisoformat(flight['departure_time']).strftime('%H:%M')} "
                            f"for ${price} {search_params['travel_class']}"
                        )
                    
                    response_text += "\n" + "\n".join(flight_options)
                    
                    return {
                        "response": response_text,
                        "button": {
                            "label": "View All Flights",
                            "url": (
                                f"/search?origin={origin_airport.code}&"
                                f"destination={destination_airport.code}&"
                                f"departure_date={search_params.get('departure_date', '')}&"
                                f"travel_class={search_params.get('travel_class')}&"
                                f"passengers={search_params.get('passengers', 1)}"
                            )
                        }
                    }
                else:
                    available_dates = sorted(set(datetime.fromisoformat(f['departure_time']).strftime('%Y-%m-%d') for f in db_snapshot.get('flights', [])))
                    response = (
                        f"Sorry, no flights match your criteria right now. "
                        f"Try these dates instead: {', '.join(available_dates[:3])}. 📅"
                    )
                    return {"response": response}
            else:
                return {"response": "Oops, couldn't find those airports. Try again? 🛫"}

    # Default AI response for all other queries
    response = call_api_with_data(user_message, db_snapshot, chat_history)
    
    try:
        clean_response = response.replace('```json', '').replace('```', '').strip()
        response_json = json.loads(clean_response)
        
        if isinstance(response_json, dict) and 'text' in response_json:
            add_to_session("You", user_message)
            add_to_session("Bot", response_json['text'])
            
            if 'button' in response_json:
                return {
                    "response": response_json['text'],
                    "button": response_json['button']
                }
            return {"response": response_json['text']}
    except json.JSONDecodeError:
        add_to_session("You", user_message)
        add_to_session("Bot", response)
        return {"response": response}