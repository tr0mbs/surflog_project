from flask import Flask, jsonify, render_template, request, redirect, url_for, abort
import calendar
import math
import os
import sqlite3
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional
from werkzeug.exceptions import HTTPException
import openmeteo_requests
import requests_cache
from retry_requests import retry

app = Flask(__name__)
DB_PATH = os.getenv("SURFLOG_DB_PATH", "surflog.db")
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Copenhagen")
OPENMETEO_CACHE_SECONDS = int(os.getenv("OPENMETEO_CACHE_SECONDS", "3600"))
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")


# Ensure surf_logs has the extra fields used by the UI
def ensure_database_schema():
    conn = sqlite3.connect(DB_PATH)
    try:
        table_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'surf_logs'
            """
        ).fetchone()

        if not table_exists:
            return

        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(surf_logs)").fetchall()
        }

        if "session_rating" not in columns:
            conn.execute("ALTER TABLE surf_logs ADD COLUMN session_rating REAL")
        if "session_start_time" not in columns:
            conn.execute("ALTER TABLE surf_logs ADD COLUMN session_start_time TEXT")
        if "session_end_time" not in columns:
            conn.execute("ALTER TABLE surf_logs ADD COLUMN session_end_time TEXT")

        conn.commit()
    finally:
        conn.close()


ensure_database_schema()


# Home route to serve the main page
@app.route("/")
def index():
    return render_template("index.html")


@app.errorhandler(sqlite3.OperationalError)
def handle_database_error(error):
    app.logger.exception("Database operational error: %s", error)
    return render_template(
        "error.html",
        title="Database Error",
        message="A database issue occurred while loading this page.",
        hint="Please refresh and try again in a moment."
    ), 500


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error

    app.logger.exception("Unexpected application error: %s", error)
    return render_template(
        "error.html",
        title="Something Went Wrong",
        message="An unexpected error occurred.",
        hint="Please try again. If the issue continues, check the server logs."
    ), 500


# Setup database connection
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
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


def parse_15_min_time(value: str) -> datetime:
    parsed = datetime.strptime(value, "%H:%M")
    if parsed.minute % 15 != 0:
        raise ValueError("Time must use 15 minute increments.")
    return parsed


# Setup Open-Meteo client with caching and retry
cache_session = requests_cache.CachedSession(
    ".cache",
    expire_after=OPENMETEO_CACHE_SECONDS
)
retry_session = retry(cache_session, retries=3, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

def get_surf_day(lat: float, lon: float, selected_date):
    """
    Fetches marine + weather data for one calendar day.
    Returns a list of 24 structured hourly dictionaries.
    """

    past_days = compute_past_days(selected_date)

    tz = ZoneInfo(APP_TIMEZONE)

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
        "timezone": APP_TIMEZONE,
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
        "timezone": APP_TIMEZONE,
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
            surf_logs.session_rating,
            surf_logs.session_start_time,
            surf_logs.session_end_time,
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

        log_dict = dict(log)
        if log_dict["session_rating"] is not None:
            log_dict["session_rating"] = float(log_dict["session_rating"])

        logs_with_conditions.append({
            "log": log_dict,
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
        session_rating_raw = request.form.get("session_rating")
        session_start_time = request.form.get("session_start_time")
        session_end_time = request.form.get("session_end_time")
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
        if not session_rating_raw or not session_start_time or not session_end_time:
            conn.close()
            abort(400, "Missing session rating or session time range.")

        try:
            selected_date = date.fromisoformat(session_date)
        except ValueError:
            conn.close()
            abort(400, "Invalid session date format.")

        if selected_date > date.today():
            conn.close()
            abort(400, "Session date cannot be in the future.")

        try:
            session_rating = float(session_rating_raw)
        except ValueError:
            conn.close()
            abort(400, "Session rating must be numeric.")

        if session_rating < 0.5 or session_rating > 5:
            conn.close()
            abort(400, "Session rating must be between 0.5 and 5.")

        if (session_rating * 2) % 1 != 0:
            conn.close()
            abort(400, "Session rating must use 0.5 increments.")

        try:
            start_dt = parse_15_min_time(session_start_time)
            end_dt = parse_15_min_time(session_end_time)
        except ValueError as exc:
            conn.close()
            abort(400, str(exc))

        if end_dt <= start_dt:
            conn.close()
            abort(400, "Session end time must be after session start time.")

        try:
            cursor = conn.execute(
                """
                INSERT INTO surf_logs (
                    session_date,
                    spot_id,
                    group_id,
                    author_id,
                    author_name,
                    session_rating,
                    session_start_time,
                    session_end_time,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_date,
                    int(spot_id),
                    int(group_id),
                    author_id,
                    author_name,
                    session_rating,
                    session_start_time,
                    session_end_time,
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
        return redirect(url_for("journal"))

    # GET request
    spots = conn.execute("SELECT id, name FROM surf_spots").fetchall()
    groups = conn.execute("SELECT id, name FROM groups").fetchall()
    conn.close()

    return render_template(
        "new_log.html",
        spots=spots,
        groups=groups,
        today_iso=date.today().isoformat()
    )


# Endpoint to display surf logs in a journal format (grouped by year and month)
def build_conditions_summary(conditions):
    """
    Build a compact weather/ocean summary for one surf log.
    Returns None when no condition rows exist.
    """
    if not conditions:
        return None

    def valid_values(key):
        return [row[key] for row in conditions if row[key] is not None]

    def circular_mean_degrees(values):
        """
        Average compass directions correctly across 0/360 wrap-around.
        """
        if not values:
            return None

        sin_total = 0.0
        cos_total = 0.0

        for value in values:
            radians = math.radians(value)
            sin_total += math.sin(radians)
            cos_total += math.cos(radians)

        if sin_total == 0 and cos_total == 0:
            return None

        avg = math.degrees(math.atan2(sin_total, cos_total))
        if avg < 0:
            avg += 360
        return round(avg, 1)

    def degrees_to_cardinal(value):
        if value is None:
            return None

        directions = [
            "N", "NNE", "NE", "ENE",
            "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW",
            "W", "WNW", "NW", "NNW"
        ]
        index = int((value + 11.25) // 22.5) % 16
        return directions[index]

    wave_heights = valid_values("wave_height")
    wind_speeds = valid_values("wind_speed")
    temperatures = valid_values("temperature")
    tide_heights = valid_values("tide_height")
    swell_heights = valid_values("swell_height")
    wind_gusts = valid_values("wind_gusts")
    wind_directions = valid_values("wind_direction")
    swell_directions = valid_values("swell_direction")

    dominant_wind_direction_deg = circular_mean_degrees(wind_directions)
    dominant_swell_direction_deg = circular_mean_degrees(swell_directions)

    return {
        "wave_height_min": round(min(wave_heights), 2) if wave_heights else None,
        "wave_height_max": round(max(wave_heights), 2) if wave_heights else None,
        "wind_speed_min": round(min(wind_speeds), 2) if wind_speeds else None,
        "wind_speed_max": round(max(wind_speeds), 2) if wind_speeds else None,
        "temperature_min": round(min(temperatures), 2) if temperatures else None,
        "temperature_max": round(max(temperatures), 2) if temperatures else None,
        "tide_min": round(min(tide_heights), 2) if tide_heights else None,
        "tide_max": round(max(tide_heights), 2) if tide_heights else None,
        "swell_height_max": round(max(swell_heights), 2) if swell_heights else None,
        "gust_max": round(max(wind_gusts), 2) if wind_gusts else None,
        "dominant_wind_direction_deg": dominant_wind_direction_deg,
        "dominant_wind_direction_cardinal": degrees_to_cardinal(
            dominant_wind_direction_deg
        ),
        "dominant_swell_direction_deg": dominant_swell_direction_deg,
        "dominant_swell_direction_cardinal": degrees_to_cardinal(
            dominant_swell_direction_deg
        ),
    }


@app.route("/journal")
def journal():
    conn = get_db_connection()

    logs = conn.execute("""
        SELECT
            surf_logs.id,
            surf_logs.session_date,
            surf_logs.notes,
            surf_logs.author_name,
            surf_logs.session_rating,
            surf_logs.session_start_time,
            surf_logs.session_end_time,
            groups.name AS group_name,
            surf_spots.name AS spot_name
        FROM surf_logs
        JOIN groups ON surf_logs.group_id = groups.id
        JOIN surf_spots ON surf_logs.spot_id = surf_spots.id
        ORDER BY surf_logs.session_date DESC
    """).fetchall()

    log_ids = [log["id"] for log in logs]
    conditions_by_log = {log_id: [] for log_id in log_ids}

    if log_ids:
        placeholders = ",".join(["?"] * len(log_ids))
        condition_rows = conn.execute(
            f"""
            SELECT
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
            FROM surf_conditions
            WHERE log_id IN ({placeholders})
            ORDER BY observed_at
            """,
            log_ids
        ).fetchall()

        for row in condition_rows:
            conditions_by_log[row["log_id"]].append(dict(row))

    conn.close()

    journal_tree = {}

    for log in logs:
        session_date = datetime.fromisoformat(log["session_date"])
        year = session_date.year
        month_number = session_date.month
        month_name = calendar.month_name[month_number]

        if year not in journal_tree:
            journal_tree[year] = {}

        if month_number not in journal_tree[year]:
            journal_tree[year][month_number] = {
                "name": month_name,
                "logs": []
            }

        log_dict = dict(log)
        if log_dict["session_rating"] is not None:
            log_dict["session_rating"] = float(log_dict["session_rating"])
        log_conditions = conditions_by_log.get(log["id"], [])

        journal_tree[year][month_number]["logs"].append({
            "log": log_dict,
            "conditions": log_conditions,
            "summary": build_conditions_summary(log_conditions),
        })

    return render_template("journal.html", journal_tree=journal_tree)


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
