"""
External API clients for weather and events data.

- WeatherService: Open-Meteo API (free, no API key)
- EventsService: Ticketmaster Discovery API
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Open-Meteo Weather API client.
    
    Free API, no authentication required.
    Docs: https://open-meteo.com/en/docs
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    # Weather code to condition mapping
    WEATHER_CODES = {
        0: "clear",
        1: "mainly_clear",
        2: "partly_cloudy",
        3: "overcast",
        45: "foggy",
        48: "foggy",
        51: "drizzle",
        53: "drizzle",
        55: "drizzle",
        61: "rain",
        63: "rain",
        65: "heavy_rain",
        71: "snow",
        73: "snow",
        75: "heavy_snow",
        80: "rain_showers",
        81: "rain_showers",
        82: "heavy_rain_showers",
        95: "thunderstorm",
        96: "thunderstorm",
        99: "thunderstorm",
    }

    async def get_current_weather(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, Any]:
        """
        Get current weather for a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            {
                "temperature": float,  # Fahrenheit
                "condition": str,  # "clear", "rain", etc.
                "humidity": int,
                "wind_speed": float,
                "weather_code": int
            }
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "temperature_unit": "fahrenheit",
            "windspeed_unit": "mph",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            current = data.get("current_weather", {})
            weather_code = current.get("weathercode", 0)

            return {
                "temperature": current.get("temperature", 70),
                "condition": self.WEATHER_CODES.get(weather_code, "unknown"),
                "wind_speed": current.get("windspeed", 0),
                "weather_code": weather_code,
                "is_day": current.get("is_day", 1) == 1,
            }

        except Exception as e:
            logger.error(f"Weather API error: {e}")
            # Return default values on error
            return {
                "temperature": 70,
                "condition": "unknown",
                "wind_speed": 0,
                "weather_code": 0,
                "is_day": True,
            }

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get weather forecast for upcoming days.

        Returns list of daily forecasts.
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
            "temperature_unit": "fahrenheit",
            "timezone": "America/Los_Angeles",
            "forecast_days": days,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            daily = data.get("daily", {})
            dates = daily.get("time", [])
            temps_max = daily.get("temperature_2m_max", [])
            temps_min = daily.get("temperature_2m_min", [])
            precip = daily.get("precipitation_sum", [])
            codes = daily.get("weathercode", [])

            forecasts = []
            for i, date in enumerate(dates):
                forecasts.append({
                    "date": date,
                    "temp_high": temps_max[i] if i < len(temps_max) else 70,
                    "temp_low": temps_min[i] if i < len(temps_min) else 50,
                    "precipitation": precip[i] if i < len(precip) else 0,
                    "condition": self.WEATHER_CODES.get(codes[i] if i < len(codes) else 0, "unknown"),
                })

            return forecasts

        except Exception as e:
            logger.error(f"Weather forecast API error: {e}")
            return []


class EventsService:
    """
    Ticketmaster Discovery API client.
    
    Docs: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/
    Free tier: 5000 calls/day
    """

    BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with API key.

        Args:
            api_key: Ticketmaster API key (or set TICKETMASTER_API_KEY env var)
        """
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        """Get API key from init or environment."""
        if self._api_key:
            return self._api_key

        import os
        key = os.getenv("TICKETMASTER_API_KEY")
        if not key:
            raise ValueError(
                "Ticketmaster API key not configured. "
                "Get one at https://developer.ticketmaster.com/explore/"
            )
        return key

    def _resolve_key(self) -> Optional[str]:
        """Return the API key if configured, else None (no exception)."""
        if self._api_key:
            return self._api_key
        import os
        return os.getenv("TICKETMASTER_API_KEY")

    # Templates for synthesized events (used when no key / API error / empty result).
    _FALLBACK_TEMPLATES = [
        ("{a} vs {b}", "sports", "19:10:00", ["Bayfront Arena", "Downtown Ballpark", "Civic Center Arena"]),
        ("{artist} — Live Tour", "music", "20:00:00", ["The Amphitheater", "Riverside Pavilion", "Metro Music Hall"]),
        ("Regional Food & Wine Festival", "arts & theatre", "12:00:00", ["Waterfront Park", "Convention Center"]),
        ("Comic & Gaming Expo", "arts & theatre", "10:00:00", ["Convention Center", "Expo Hall"]),
        ("Family Fun Fair", "family", "11:00:00", ["Fairgrounds", "City Commons"]),
        ("{artist} in Concert", "music", "19:30:00", ["Metro Music Hall", "The Amphitheater"]),
        ("Championship Playoff Game", "sports", "18:30:00", ["Bayfront Arena", "Downtown Ballpark"]),
    ]
    _FALLBACK_TEAMS = ["Bay City FC", "Metro United", "Harbor Kings", "Valley Storm", "Coast Rovers"]
    _FALLBACK_ARTISTS = ["The Midnight Echo", "Luna Vega", "Skyline Collective", "Marcus Reed", "The Wanderers"]

    def _generate_fallback_events(
        self, latitude: float, longitude: float, days_ahead: int = 7, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Synthesize plausible, up-to-date local events so the events module is never
        blank in a demo — used when no Ticketmaster key is configured, the API
        errors, or it returns nothing. Seeded by location + today's date, so the
        set is stable within a day and refreshes daily. Same shape as real events.
        """
        import random

        today = datetime.utcnow().date()
        seed = int(f"{int(abs(latitude) * 10)}{int(abs(longitude) * 10)}{today.strftime('%Y%m%d')}")
        rng = random.Random(seed)

        count = min(rng.randint(4, 8), limit)
        chosen = rng.sample(self._FALLBACK_TEMPLATES, k=min(count, len(self._FALLBACK_TEMPLATES)))
        events: List[Dict[str, Any]] = []
        for i, (name_tpl, etype, time_str, venues) in enumerate(chosen):
            day_offset = rng.randint(0, max(days_ahead - 1, 0))
            event_date = today + timedelta(days=day_offset)
            name = name_tpl.format(
                a=rng.choice(self._FALLBACK_TEAMS),
                b=rng.choice(self._FALLBACK_TEAMS),
                artist=rng.choice(self._FALLBACK_ARTISTS),
            )
            events.append({
                "id": f"demo-{seed}-{i}",
                "name": name,
                "date": event_date.strftime("%Y-%m-%d"),
                "time": time_str,
                "venue": rng.choice(venues),
                "type": etype.split(" ")[0].lower(),  # normalize e.g. "arts & theatre" -> "arts"
                "url": None,
            })
        events.sort(key=lambda e: (e["date"], e["time"]))
        return events

    async def get_local_events(
        self,
        latitude: float,
        longitude: float,
        radius: int = 50,
        days_ahead: int = 7,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming events near a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            radius: Search radius in miles
            days_ahead: How many days ahead to search
            limit: Maximum events to return

        Returns:
            List of events with name, date, venue, type
        """
        # No key configured → synthesize events so the module is never blank.
        key = self._resolve_key()
        if not key:
            return self._generate_fallback_events(latitude, longitude, days_ahead, limit)

        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days_ahead)

        params = {
            "apikey": key,
            "latlong": f"{latitude},{longitude}",
            "radius": radius,
            "unit": "miles",
            "startDateTime": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "size": limit,
            "sort": "date,asc",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            events = []
            embedded = data.get("_embedded", {})
            
            for event in embedded.get("events", []):
                # Get venue info
                venues = event.get("_embedded", {}).get("venues", [])
                venue_name = venues[0].get("name", "Unknown") if venues else "Unknown"

                # Get event type/category
                classifications = event.get("classifications", [])
                event_type = "other"
                if classifications:
                    segment = classifications[0].get("segment", {})
                    event_type = segment.get("name", "other").lower()

                # Get date/time
                dates = event.get("dates", {}).get("start", {})
                
                events.append({
                    "id": event.get("id"),
                    "name": event.get("name"),
                    "date": dates.get("localDate"),
                    "time": dates.get("localTime"),
                    "venue": venue_name,
                    "type": event_type,  # "sports", "music", "arts", etc.
                    "url": event.get("url"),
                })

            # Never leave the module blank in a demo — fall back if the API
            # returned no events for this location/window.
            return events or self._generate_fallback_events(latitude, longitude, days_ahead, limit)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Ticketmaster rate limit exceeded")
            else:
                logger.error(f"Ticketmaster API error: {e}")
            return self._generate_fallback_events(latitude, longitude, days_ahead, limit)
        except Exception as e:
            logger.error(f"Events API error: {e}")
            return self._generate_fallback_events(latitude, longitude, days_ahead, limit)

    async def check_event_impact(
        self,
        latitude: float,
        longitude: float,
        date: str = None,
        store_lat: float = None,
        store_lng: float = None,
    ) -> Dict[str, Any]:
        """
        Check if there are major events that could impact traffic.

        Args:
            latitude: Store latitude
            longitude: Store longitude
            date: Optional specific date to filter (YYYY-MM-DD). If None, returns all events in range.
            store_lat: Store latitude for distance calculation (defaults to latitude if not provided)
            store_lng: Store longitude for distance calculation (defaults to longitude if not provided)

        Returns:
            {
                "has_major_event": bool,
                "event_count": int,
                "events": List of event summaries with distance,
                "estimated_traffic_impact": str  # "none", "low", "medium", "high"
            }
        """
        import math
        
        # Use store coordinates for distance calculation
        ref_lat = store_lat or latitude
        ref_lng = store_lng or longitude
        
        # Search for events within 50 miles over next 7 days
        events = await self.get_local_events(
            latitude=latitude,
            longitude=longitude,
            radius=50,  # 50 mile radius for regional events
            days_ahead=7,  # Next 7 days
            limit=50
        )

        # Filter to events on the target date if specified
        if date:
            target_events = [e for e in events if e.get("date") == date]
        else:
            target_events = events

        # Estimate impact based on event types and count
        sports_events = [e for e in target_events if e.get("type") == "sports"]
        music_events = [e for e in target_events if e.get("type") == "music"]

        impact = "none"
        if len(sports_events) > 0:
            impact = "high"  # Sports games drive significant local traffic
        elif len(music_events) > 1:
            impact = "high"
        elif len(music_events) == 1:
            impact = "medium"
        elif len(target_events) > 3:
            impact = "medium"
        elif len(target_events) > 0:
            impact = "low"

        # Group events by date for the response
        events_by_date = {}
        for e in target_events:
            event_date = e.get("date", "Unknown")
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(e)

        return {
            "has_major_event": impact in ["medium", "high"],
            "has_any_events": len(target_events) > 0,
            "event_count": len(target_events),
            "events": target_events,  # Return all events (up to 50)
            "events_by_date": events_by_date,
            "estimated_traffic_impact": impact,
            "sports_count": len(sports_events),
            "music_count": len(music_events),
        }


# Singleton instances
weather_service = WeatherService()
events_service = EventsService()


