# weather_service.py
import os
import time
import requests
import logging
from datetime import datetime, timedelta
from flask import current_app
from cachetools import TTLCache

class WeatherService:
    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "http://api.openweathermap.org/data/2.5/weather"
        self.logger = logging.getLogger(__name__)
        self.min_request_interval = 2.0  # Increased to 2 seconds
        self.last_request_time = 0
        # Cache weather data for 10 minutes (600 seconds)
        self.weather_cache = TTLCache(maxsize=1000, ttl=600)

    def _enforce_rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            # self.logger.warning(f"Rate limit hit, waiting {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def get_weather_by_coordinates(self, lat, lon):
        # Create cache key
        cache_key = f"{lat:.4f},{lon:.4f}"
        
        # Check cache first
        if cache_key in self.weather_cache:
            # self.logger.debug(f"Cache hit for coordinates {cache_key}")
            return self.weather_cache[cache_key]

        try:
            self._enforce_rate_limit()
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric"
            }
            with current_app.app_context():
                response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            weather_data = response.json()
            
            # Store in cache
            self.weather_cache[cache_key] = weather_data
            return weather_data
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                self.logger.warning("Rate limit exceeded for OpenWeather API")
                return {"cod": 429, "message": "Rate limit exceeded"}
            self.logger.error(f"HTTP error fetching weather: {str(e)}")
            return {"cod": e.response.status_code, "message": str(e)}
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching weather: {str(e)}")
            return {"cod": 500, "message": str(e)}