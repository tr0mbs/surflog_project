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

url = "https://marine-api.open-meteo.com/v1/marine"

params = {
    "latitude": 56.962921,
    "longitude": 8.36903,
    "hourly": [
        "wave_height",
        "wave_period",
        "wave_direction",
        "sea_level_height_msl",
    ],
    "timezone": "Europe/Berlin",
    "past_days": 4,       # archived forecast
    "forecast_days": 1,   # keep response small
}

responses = openmeteo.weather_api(url, params=params)
response = responses[0]

### Basic sanity checks
print("Latitude:", response.Latitude())
print("Longitude:", response.Longitude())
print("Timezone:", response.Timezone())

hourly = response.Hourly()
print("Hourly start time (unix):", hourly.Time())
print("Hourly end time (unix):", hourly.TimeEnd())
print("Hourly interval (seconds):", hourly.Interval())
print("Number of hourly variables:", hourly.VariablesLength())

### Accessing variables by index (order is the same as requested)
# print("Wave height:", hourly.Variables(0).ValuesAsNumpy())
# print("Wave period:", hourly.Variables(1).ValuesAsNumpy())
# print("Wave direction:", hourly.Variables(2).ValuesAsNumpy())
# print("Sea level height MSL:", hourly.Variables(3).ValuesAsNumpy())

### Example of processing hourly data.
tz = ZoneInfo("Europe/Berlin")

start_unix = hourly.Time()
interval = hourly.Interval()

print("\nFirst ?? hourly timestamps:")

for i in range(24):
    ts = start_unix + i * interval
    dt = datetime.fromtimestamp(ts, tz)
    print(dt.isoformat())

### Test timestamp range and interval
# print("\nDataset span analysis:")

# start_unix = hourly.Time()
# end_unix = hourly.TimeEnd()
# interval = hourly.Interval()

# total_hours = int((end_unix - start_unix) / interval)

# print("Total hourly timestamps:", total_hours)

# first_dt = datetime.fromtimestamp(start_unix, tz)
# last_dt = datetime.fromtimestamp(end_unix - interval, tz)

# print("First timestamp:", first_dt.isoformat())
# print("Last timestamp:", last_dt.isoformat())


### Test compute_past_days() with various dates
# print("\nTesting compute_past_days()")

# today = date(2026, 2, 12)

# test_dates = [
#     date(2026, 2, 12),  # today
#     date(2026, 2, 11),   # yesterday
#     date(2026, 2, 5),   # 7 days ago
#     date(2026, 1, 11),  # 32 days ago
# ]

# for d in test_dates:
#     result = compute_past_days(d, today=today)
#     print(f"Selected: {d} -> past_days = {result}")


def get_wind_day(lat: float, lon: float, selected_date):
    """
    Fetches archived wind forecast for a specific calendar date.
    Returns a list of 24 hourly dictionaries.
    """
 
    past_days = compute_past_days(selected_date)

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "temperature_2m",  # Optional, may not be available for all dates
        ],
        "timezone": "Europe/Berlin",
        "past_days": past_days,
        "forecast_days": 1,
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    hourly = response.Hourly()

    start_unix = hourly.Time()
    interval = hourly.Interval()

    tz = ZoneInfo("Europe/Berlin")

    wind_speed = hourly.Variables(0).ValuesAsNumpy()
    wind_direction = hourly.Variables(1).ValuesAsNumpy()
    wind_gusts = hourly.Variables(2).ValuesAsNumpy()
    temperature_2m = hourly.Variables(3).ValuesAsNumpy() if hourly.VariablesLength() > 3 else None

    result = []

    for i in range(24):
        ts = start_unix + i * interval
        dt = datetime.fromtimestamp(ts, tz)

        result.append({
            "time": dt.isoformat(),
            "wind_speed_10m": float(wind_speed[i]),
            "wind_direction_10m": float(wind_direction[i]),
            "wind_gusts_10m": float(wind_gusts[i]),
            "temperature_2m": float(temperature_2m[i]) if temperature_2m is not None else None,
        })

    return result



### Basic sanity checks
# print("Latitude:", response.Latitude())
# print("Longitude:", response.Longitude())
# print("Timezone:", response.Timezone())

# hourly = response.Hourly()
# print("Hourly start time (unix):", hourly.Time())
# print("Hourly end time (unix):", hourly.TimeEnd())
# print("Hourly interval (seconds):", hourly.Interval())
# print("Number of hourly variables:", hourly.VariablesLength())


### Test get_wind_day() with a specific date
print("\nTesting get_wind_day()")

selected = date(2026, 2, 3)

wind_data = get_wind_day(
    lat=56.962921,
    lon=8.36903,
    selected_date=selected
)

print("Number of returned hours:", len(wind_data))
print("First entry:")
print(wind_data[0])
print("Last entry:")
print(wind_data[-1])