from datetime import datetime

def calculate_days_before_departure(departure_time):
    """Calculate the number of days before the flight departure."""
    now = datetime.utcnow()
    diff = departure_time - now
    return max(0, diff.days)

def get_seat_map(flight, travel_class):
    """Generate a seat map for the flight and travel class."""
    # Get all seats for the flight and class
    seats = flight.seats
    
    # Filter seats by class
    class_seats = [seat for seat in seats if seat.seat_class == travel_class]
    
    # Sort seats by row and column
    sorted_seats = sorted(class_seats, key=lambda s: (
        int(''.join(filter(str.isdigit, s.seat_number))),  # Extract row number
        ''.join(filter(str.isalpha, s.seat_number))        # Extract column letter
    ))
    
    # Group seats by row
    seat_map = {}
    for seat in sorted_seats:
        # Extract row number
        row = ''.join(filter(str.isdigit, seat.seat_number))
        if row not in seat_map:
            seat_map[row] = []
        
        seat_map[row].append(seat)
    
    return seat_map

def generate_booking_reference():
    """Generate a 6-character alphanumeric booking reference."""
    import secrets
    import string
    
    # Use uppercase letters and digits for clarity
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(6))
