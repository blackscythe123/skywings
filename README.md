# SkyWings Flight Booking System ✈️

## Project Overview

SkyWings is a comprehensive flight booking system that allows users to search, book, and manage flights with ease. The system features a user-friendly interface, AI-powered chatbot assistance, secure payment processing, weather monitoring, and robust administrative controls.

## Key Features

- **User Authentication**: Secure login, registration, and profile management
- **Flight Search & Booking**: Intuitive flight search with dynamic pricing
- **AI Chatbot**: Intelligent flight search and booking assistance
- **Seat Selection**: Interactive seat map selection
- **Payment Processing**: Secure Stripe integration with discounts
- **Booking Management**: View, modify, and cancel bookings
- **Weather Monitoring**: Real-time weather tracking and flight status updates
- **Flight Status Updates**: Automatic status management for completed flights
- **Admin Dashboard**: Comprehensive management tools for flights, users, and bookings
- **Email Notifications**: Automated notifications for bookings, weather alerts, and flight updates
- **Reporting**: Detailed analytics and reporting
- **Frequent Flyer Program**: Earn and redeem miles, automatic status updates, and admin/manual correction tools
- **Bulk Data Injection**: Scripts for large-scale test data and frequent flyer status correction

## Technology Stack

- **Backend**: Python with Flask framework
- **Database**: SQLAlchemy with PostgreSQL/SQLite
- **Frontend**: HTML, CSS, JavaScript with Bootstrap
- **AI Integration**: OpenRouter API with DeepSeek model
- **Payment Processing**: Stripe API with secure checkout
- **Weather Integration**: OpenWeather API for real-time weather data
- **Background Processing**: Thread-based task processing for status updates
- **Email**: Flask-Mail with SMTP for automated notifications
- **PDF Generation**: pdfkit and xhtml2pdf for document generation

## Project Structure

```
skywings/
├── app.py                        # Main application configuration and entry point
├── routes.py                     # Application routes and logic (user, admin, booking, payment, etc.)
├── models.py                     # Database models
├── chatbot.py                    # AI chatbot implementation and logic
├── chatbot_routes.py             # Chatbot Flask blueprint
├── extensions.py                 # Flask extensions (db, mail, etc.)
├── utils.py                      # Utility functions (pricing, seat map, etc.)
├── requirements.txt              # Python dependencies
├── large_injection.py            # Script for large-scale data injection
├── fix_frequent_flyer_status.py  # Script to fix frequent flyer status for all users
├── static/                       # Static files (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── images/
├── templates/                    # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── confirmation.html
│   ├── manage_bookings.html
│   ├── admin/
│   │   ├── users.html
│   │   ├── user_bookings.html
│   │   ├── bookings.html
│   │   ├── flights.html
│   │   ├── airports.html
│   │   ├── aircraft.html
│   │   └── ... (other admin templates)
│   └── ... (other templates)
├── README.md                     # This file
└── ... (other scripts and files)
```

## Installation & Setup

### Prerequisites

- Python 3.8+
- PostgreSQL (or SQLite for development)
- Node.js (for pdfkit)
- wkhtmltopdf (for PDF generation)

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/skywings.git
   cd skywings
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the root directory with the following variables:
   ```
   DATABASE_URL=sqlite:///flight_booking.db
   SESSION_SECRET=your-secret-key-here
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-email-password
   STRIPE_SECRET_KEY=your-stripe-secret-key
   STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key
   OPENROUTER_API_KEY=your-openrouter-api-key
   OPENWEATHER_API_KEY=your-openweather-api-key
   UNSPLASH_ACCESS_KEY=your-unsplash-access-key
   ```

5. **Initialize the database:**
   ```bash
   flask shell
   >>> from app import db
   >>> db.create_all()
   >>> exit()
   ```

6. **Run the application:**
   ```bash
   python app.py
   ```
   Access the application at [http://localhost:5500](http://localhost:5500)

## Database Initialization

To populate the database with sample data, visit:
```
http://localhost:5500/init-db
```
Or run:
```bash
python large_injection.py
```
To fix frequent flyer status for all users:
```bash
python fix_frequent_flyer_status.py
```

## Key API Endpoints

### Flight Search
- `GET /search` - Flight search interface
- `GET /api/airports` - Airport autocomplete API
- `GET /api/flight/<flight_id>/available-seats/<travel_class>` - Available seats API

### Booking Flow
- `POST /store-selected-seats/<flight_id>` - Store selected seats
- `GET /passenger-details` - Passenger information form
- `POST /process-passengers` - Process passenger details
- `POST /process-payment` - Process payment via Stripe

### User Management
- `POST /login` - User login
- `POST /register` - User registration
- `POST /change_password` - Password change
- `POST /save_preferences` - Save user preferences

### Admin Endpoints
- `GET /admin` - Admin dashboard
- `GET /admin/users` - Manage users (search, filter, sort, edit, delete, update frequent flyer status)
- `GET /admin/flights` - Manage flights
- `GET /admin/bookings` - Manage bookings
- `GET /admin/airports` - Manage airports
- `GET /admin/aircraft` - Manage aircraft
- `GET /admin/reports` - System reports and analytics

### Chatbot API
- `POST /chatbot` - Process chatbot messages
- `POST /clear_chat` - Clear chat history
- `GET /get_chat_history` - Retrieve chat history

## Frequent Flyer Program

- **Automatic Status Update:** User status (Standard, Silver, Gold, Platinum) is updated automatically based on miles after each booking.
- **Admin Correction:** Admins can manually update user status and miles from the admin panel.
- **Batch Fix:** Use `fix_frequent_flyer_status.py` to correct all user statuses in bulk.

## Configuration Options

Key configuration options in `app.py`:

```python
# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///flight_booking.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Session configuration
app.config['SESSION_TYPE'] = 'filesystem'  
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Email configuration
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
)

# Payment configuration
app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY')
app.config['STRIPE_PUBLISHABLE_KEY'] = os.getenv('STRIPE_PUBLISHABLE_KEY')

# Weather monitoring configuration
app.config['OPENWEATHER_API_KEY'] = os.getenv('OPENWEATHER_API_KEY')
app.config['WEATHER_CHECK_INTERVAL'] = 300  # 5 minutes
```

## System Components

### Background Services

#### Weather Monitoring System
- Real-time weather tracking for all flight routes
- Automatic alerts for severe weather conditions
- Integration with OpenWeather API
- Proactive flight status updates based on weather

#### Flight Status Updater
- Automatic status updates for completed flights
- Background thread processing
- Database consistency maintenance
- Logging and error handling

### AI Chatbot Implementation

- Natural language processing for flight searches
- Context-aware conversations
- Database integration for real-time flight information
- Booking confirmation handling
- Chatbot logic in `chatbot.py` and `chatbot_routes.py`

### Payment Processing

- Stripe for secure payment processing
- Credit card payments through Stripe Checkout
- Frequent flyer discounts
- Payment verification and error handling
- Automatic receipt generation

### Email Notification System

- Booking confirmations and e-tickets
- Weather alerts and flight status updates
- Login/logout security notifications
- System alerts and reports

### Reporting System

- Booking trends and analytics
- Revenue reports and forecasts
- Weather impact analysis
- Flight status statistics
- Flight utilization
- User growth metrics

## Development & Contribution

- Use feature branches for new features or bug fixes.
- Run `python large_injection.py` for large-scale test data.
- Use `python fix_frequent_flyer_status.py` to batch-correct frequent flyer statuses.
- Use `git status` and `git add` to stage only the files you want to commit.

## Deployment

For production deployment:

1. Set up a PostgreSQL database
2. Configure a production-ready WSGI server (Gunicorn, uWSGI)
3. Set up a reverse proxy (Nginx, Apache)
4. Configure production email settings
5. Set `DEBUG=False` in production

## License

For any questions or support, please contact the development team at skywings102914@gmail.com
