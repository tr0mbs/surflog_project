import openmeteo_requests
import requests_cache
from retry_requests import retry
from datetime import date, datetime
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional


def compute_past_days(selected_date: date, today: Optional[date] = None) -> int:
    """
    Returns how many full calendar days ago the selected_date was.
    Raises ValueError if date is in the future.
    """

    if today is None:
        today = date.today()

    delta = today - selected_date

    if delta.days < 0:
        raise ValueError("Selected date cannot be in the future.")

    return delta.days


### Setup client with cache + retry
cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
retry_session = retry(cache_session, retries=3, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)


def get_surf_day(lat: float, lon: float, selected_date):
    """
    Fetches marine + weather data for one calendar day.
    Returns a list of 24 structured hourly dictionaries.
    """

    past_days = compute_past_days(selected_date)

    tz = ZoneInfo("Europe/Berlin")

    # ---- Marine API ----
    marine_url = "https://marine-api.open-meteo.com/v1/marine"

    marine_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "wave_height",
            "wave_period",
            "wave_direction",
            "swell_wave_height",
            "swell_wave_period",
            "swell_wave_direction",
            "sea_level_height_msl",
        ],
        "timezone": "Europe/Berlin",
        "past_days": past_days,
        "forecast_days": 1,
    }

    marine_response = openmeteo.weather_api(marine_url, params=marine_params)[0]
    marine_hourly = marine_response.Hourly()

    marine_start = marine_hourly.Time()
    interval = marine_hourly.Interval()

    wave_height = marine_hourly.Variables(0).ValuesAsNumpy()
    wave_period = marine_hourly.Variables(1).ValuesAsNumpy()
    wave_direction = marine_hourly.Variables(2).ValuesAsNumpy()
    swell_height = marine_hourly.Variables(3).ValuesAsNumpy()
    swell_period = marine_hourly.Variables(4).ValuesAsNumpy()
    swell_direction = marine_hourly.Variables(5).ValuesAsNumpy()
    tide_height = marine_hourly.Variables(6).ValuesAsNumpy()

    # ---- Weather API ----
    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "temperature_2m",
        ],
        "timezone": "Europe/Berlin",
        "past_days": past_days,
        "forecast_days": 1,
    }

    weather_response = openmeteo.weather_api(weather_url, params=weather_params)[0]
    weather_hourly = weather_response.Hourly()

    wind_speed = weather_hourly.Variables(0).ValuesAsNumpy()
    wind_direction = weather_hourly.Variables(1).ValuesAsNumpy()
    wind_gusts = weather_hourly.Variables(2).ValuesAsNumpy()
    temperature = weather_hourly.Variables(3).ValuesAsNumpy()

    # ---- Merge 24 Hours ----
    result = []

    for i in range(24):
        ts = marine_start + i * interval
        dt = datetime.fromtimestamp(ts, tz)

        result.append({
            "observed_at": dt.isoformat(),

            # Wave
            "wave_height": float(wave_height[i]),
            "wave_period": float(wave_period[i]),
            "wave_direction": float(wave_direction[i]),

            # Swell
            "swell_wave_height": float(swell_height[i]),
            "swell_wave_period": float(swell_period[i]),
            "swell_wave_direction": float(swell_direction[i]),

            # Wind
            "wind_speed": float(wind_speed[i]),
            "wind_direction": float(wind_direction[i]),
            "wind_gusts": float(wind_gusts[i]),

            # Tide
            "tide_height": float(tide_height[i]),

            # Weather
            "temperature": float(temperature[i]),
        })

    return result


# Test it

print("\nTesting get_surf_day()")

selected = date(2026, 2, 3)

surf_data = get_surf_day(
    lat=56.962921,
    lon=8.36903,
    selected_date=selected
)

print("Number of returned hours:", len(surf_data))
print("First entry:")
print(surf_data[0])
print("Last entry:")
print(surf_data[-1])

### Example of processing hourly data.
# tz = ZoneInfo("Europe/Berlin")
# hourly = get_surf_day.Hourly()

# start_unix = hourly.Time()
# interval = hourly.Interval()

# print("\nFirst ?? hourly timestamps:")

# for i in range(24):
#     ts = start_unix + i * interval
#     dt = datetime.fromtimestamp(ts, tz)
#     print(dt.isoformat())