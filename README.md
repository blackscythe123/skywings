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
├── app.py                # Main application configuration
├── main.py               # Application entry point
├── models.py             # Database models
├── routes.py             # Application routes and logic
├── chatbot.py            # AI chatbot implementation
├── weather_monitor.py    # Weather monitoring system
├── weather_service.py    # Weather API integration
├── flight_status_updater.py # Flight status management
├── extensions.py         # Flask extensions
├── utils.py             # Utility functions
├── requirements.txt      # Python dependencies
├── static/              # Static files (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── images/
└── templates/           # HTML templates
    ├── admin/           # Admin interface templates
    ├── chatbot/         # Chatbot interface templates
    ├── user/            # User interface templates
    └── ...
```

## Installation & Setup

### Prerequisites

- Python 3.8+
- PostgreSQL (or SQLite for development)
- Node.js (for pdfkit)
- wkhtmltopdf (for PDF generation)

### Setup Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/skywings.git
   cd skywings
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the root directory with the following variables:
   ```
   DATABASE_URL=postgresql://username:password@localhost/skywings
   SESSION_SECRET=your-secret-key-here
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-email-password
   STRIPE_SECRET_KEY=your-stripe-secret-key
   STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key
   OPENROUTER_API_KEY=your-openrouter-api-key
   OPENWEATHER_API_KEY=your-openweather-api-key
   ```

5. Initialize the database:
   ```bash
   flask shell
   >>> db.create_all()
   >>> exit()
   ```

6. Run the application:
   ```bash
   python main.py
   ```

7. Access the application at `http://localhost:5500`

## Database Initialization

To populate the database with sample data, visit:
```
http://localhost:5500/init-db
```

**Note:** This route is only available in debug mode.

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
- `GET /admin/reports` - System reports
- Various CRUD endpoints for flights, users, bookings, etc.

### Chatbot API
- `POST /chatbot` - Process chatbot messages
- `POST /clear_chat` - Clear chat history
- `GET /get_chat_history` - Retrieve chat history

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
Implemented in `weather_monitor.py` and `weather_service.py`:
- Real-time weather tracking for all flight routes
- Automatic alerts for severe weather conditions
- Integration with OpenWeather API
- Proactive flight status updates based on weather

#### Flight Status Updater
Implemented in `flight_status_updater.py`:
- Automatic status updates for completed flights
- Background thread processing
- Database consistency maintenance
- Logging and error handling

### AI Chatbot Implementation

The chatbot uses the OpenRouter API with the DeepSeek model to provide intelligent flight search and booking assistance. Key features:

- Natural language processing for flight searches
- Context-aware conversations
- Database integration for real-time flight information
- Booking confirmation handling

Chatbot logic is implemented in `chatbot.py` with routes in `routes.py`.

### Payment Processing

The system uses Stripe for secure payment processing. Key features:

- Credit card payments through Stripe Checkout
- Frequent flyer discounts
- Payment verification and error handling
- Automatic receipt generation
- Secure payment session management

### Email Notification System

The application sends various automated notifications using Flask-Mail:

- Booking confirmations and e-tickets
- Weather alerts and flight status updates
- Login security notifications
- System alerts and reports

### Reporting System

The admin dashboard includes comprehensive reporting:

- Booking trends and analytics
- Revenue reports and forecasts
- Weather impact analysis
- Flight status statistics
- Flight utilization
- User growth metrics

## Deployment

For production deployment:

1. Set up a PostgreSQL database
2. Configure a production-ready WSGI server (Gunicorn, uWSGI)
3. Set up a reverse proxy (Nginx, Apache)
4. Configure production email settings
5. Set `DEBUG=False` in production

## Future Enhancements

- Mobile app integration
- Additional payment methods
- Enhanced frequent flyer program
- Real-time flight status updates
- Multi-language support

## License

For any questions or support, please contact the development team at skywings102914@gmail.com
