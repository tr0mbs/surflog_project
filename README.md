# SurfLog Project

SurfLog is a Flask-based surf journal built as a CS50x final project.
It combines user session notes with hourly marine/weather data from Open-Meteo.

## Current Scope
- Shared journal workflow (no auth yet)
- Focused on Danish surf spots
- Local SQLite database
- Deployed on Render

## Stack
- Python + Flask
- SQLite
- Jinja templates + CSS
- Open-Meteo APIs

## Local Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Initialize the database:
   - `python init_db.py`
4. Run the app:
   - `python app.py`

## Environment Variables
- `SURFLOG_DB_PATH`
  - Local default: `surflog.db`
  - Render value: `/var/data/surflog.db`
- `APP_TIMEZONE`
  - Default: `Europe/Copenhagen`
- `OPENMETEO_CACHE_SECONDS`
  - Default: `3600`
- `SECRET_KEY`
  - Set to a long random string in production

## Render Deployment
- Build command:
  - `pip install -r requirements.txt`
- Start command:
  - `gunicorn -w 2 -k gthread --threads 4 -b 0.0.0.0:$PORT app:app`
- Pre-deploy command:
  - `python init_db.py`
- Persistent disk:
  - Mount path: `/var/data`
- Required env var:
  - `SURFLOG_DB_PATH=/var/data/surflog.db`

## Notes
- Database schema is defined in `schema.sql`.
- `init_db.py` is idempotent and now fails if required tables are missing.
