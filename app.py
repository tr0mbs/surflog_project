from flask import Flask, jsonify, render_template, request, redirect, url_for, abort
import requests
import sqlite3
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional
import openmeteo_requests
import requests_cache
from retry_requests import retry

app = Flask(__name__)
DB_PATH = "surflog.db"


# Home route to serve the main page
@app.route("/")
def index():
    return render_template("index.html")


# Setup database connection
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-like access
    return conn


# Utility function to compute how many full calendar days ago a date was
def compute_past_days(selected_date: date, today: Optional[date] = None) -> int:
    
    if today is None:
        today = date.today()

    delta = today - selected_date

    if delta.days < 0:
        raise ValueError("Selected date cannot be in the future.")

    return delta.days


# Setup Open-Meteo client with caching and retry
cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
retry_session = retry(cache_session, retries=3, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

def get_surf_day(lat: float, lon: float, selected_date):
    """
    Fetches marine + weather data for one calendar day.
    Returns a list of 24 structured hourly dictionaries.
    """

    from datetime import datetime
    from zoneinfo import ZoneInfo

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
            "swell_height": float(swell_height[i]),
            "swell_period": float(swell_period[i]),
            "swell_direction": float(swell_direction[i]),

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


# Endpoint to get all groups, i.e. Queries the DB, Converts rows into dictionaries, Returns JSON (easy to inspect in browser)
@app.route("/groups")
def get_groups():
    conn = get_db_connection()
    groups = conn.execute("SELECT * FROM groups").fetchall()
    conn.close()

    return jsonify([dict(group) for group in groups])

# Endpoint to get all surf spots and render them in a template
@app.route("/spots")
def spots():
    conn = get_db_connection()
    spots = conn.execute("SELECT * FROM surf_spots").fetchall()
    conn.close()

    return render_template(
        "spots.html",
        spots=spots
    )


# Endpoint to get all surf logs with associated conditions
@app.route("/logs")
def logs():
    conn = get_db_connection()

    logs = conn.execute("""
        SELECT
            surf_logs.id,
            surf_logs.session_date,
            surf_logs.notes,
            surf_logs.author_name,
            groups.name AS group_name,
            surf_spots.name AS spot_name
        FROM surf_logs
        JOIN groups ON surf_logs.group_id = groups.id
        JOIN surf_spots ON surf_logs.spot_id = surf_spots.id
        ORDER BY surf_logs.session_date DESC
    """).fetchall()

    logs_with_conditions = []

    for log in logs:
        conditions = conn.execute("""
            SELECT
                observed_at,
                wave_height,
                wave_period,
                wave_direction,
                swell_height,
                swell_period,
                swell_direction,
                wind_speed,
                wind_direction,
                wind_gusts,
                tide_height,
                temperature
            FROM surf_conditions
            WHERE log_id = ?
            ORDER BY observed_at
        """, (log["id"],)).fetchall()

        logs_with_conditions.append({
            "log": dict(log),
            "conditions": [dict(c) for c in conditions]
        })

    conn.close()

    return render_template(
        "logs.html",
        logs=logs_with_conditions
    )


# Endpoint to create a new surf log
@app.route("/logs/new", methods=["GET", "POST"])
def new_log():
    conn = get_db_connection()

    if request.method == "POST":
        session_date = request.form.get("session_date")
        spot_id = request.form.get("spot_id")
        group_id = request.form.get("group_id")
        author_name = request.form.get("author_name", "").strip()
        author_hint = request.form.get("author_hint")
        notes = request.form.get("notes", "").strip()

        # Display name fallback
        if not author_name:
            author_name = "Guest"

        # Stable identity strategy
        if author_hint:
            # Reuse client-provided fingerprint (best effort)
            author_id = f"legacy_{author_hint}"
        else:
            # Server-generated fallback
            author_id = f"legacy_{uuid.uuid4().hex}"

        # Fetch spot coordinates
        spot = conn.execute(
            "SELECT latitude, longitude FROM surf_spots WHERE id = ?",
            (int(spot_id),)
        ).fetchone()
        if not spot:
            conn.close()
            abort(400, "Invalid surf spot")

        # Basic validation
        if not session_date or not spot_id or not group_id:
            conn.close()
            abort(400, "Missing required fields")

        try:
            cursor = conn.execute(
                """
                INSERT INTO surf_logs (
                    session_date,
                    spot_id,
                    group_id,
                    author_id,
                    author_name,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_date,
                    int(spot_id),
                    int(group_id),
                    author_id,
                    author_name,
                    notes,
                )
            )

            conn.commit()
            log_id = cursor.lastrowid

        except Exception as e:
            conn.rollback()
            conn.close()
            raise e
        
        try:
            selected_date = date.fromisoformat(session_date)

            surf_data = get_surf_day(
                lat=spot["latitude"],
                lon=spot["longitude"],
                selected_date=selected_date
            )

            for hour in surf_data:
                data = hour.copy()
                data["log_id"] = log_id

                # Optional rounding
                for key in data:
                    if isinstance(data[key], float):
                        data[key] = round(data[key], 2)

                conn.execute(
                    """
                    INSERT OR IGNORE INTO surf_conditions (
                        log_id,
                        observed_at,
                        wave_height,
                        wave_period,
                        wave_direction,
                        swell_height,
                        swell_period,
                        swell_direction,
                        wind_speed,
                        wind_direction,
                        wind_gusts,
                        tide_height,
                        temperature
                    )
                    VALUES (
                        :log_id,
                        :observed_at,
                        :wave_height,
                        :wave_period,
                        :wave_direction,
                        :swell_height,
                        :swell_period,
                        :swell_direction,
                        :wind_speed,
                        :wind_direction,
                        :wind_gusts,
                        :tide_height,
                        :temperature
                    )
                    """,
                    data
                )

            conn.commit()

        except Exception as e:
            conn.rollback()
            print("Open-Meteo fetch failed:", e)

        conn.close()
        return redirect(url_for("logs"))

    # GET request
    spots = conn.execute("SELECT id, name FROM surf_spots").fetchall()
    groups = conn.execute("SELECT id, name FROM groups").fetchall()
    conn.close()

    return render_template(
        "new_log.html",
        spots=spots,
        groups=groups
    )


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
