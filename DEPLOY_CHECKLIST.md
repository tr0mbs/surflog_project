# Deploy Checklist

Use this checklist after each production deploy.

## Pre-Deploy
- [ ] Latest commit is pushed to `main`
- [ ] Render env vars are set:
  - [ ] `SURFLOG_DB_PATH=/var/data/surflog.db`
  - [ ] `APP_TIMEZONE=Europe/Copenhagen`
  - [ ] `SECRET_KEY` (long random value)
- [ ] Render disk is attached and mounted at `/var/data`
- [ ] Pre-deploy command is set: `python init_db.py`

## Deploy Logs
- [ ] Build completes successfully
- [ ] Pre-deploy runs successfully
- [ ] Log confirms DB init path (should be `/var/data/surflog.db`)
- [ ] Gunicorn starts without errors

## Smoke Test (Web)
- [ ] `/` loads
- [ ] `/spots` loads
- [ ] `/logs/new` loads
- [ ] Create a new log successfully
- [ ] `/logs` shows the new log
- [ ] `/journal` shows the new log

## Data + API Validation
- [ ] New log includes stored weather/marine conditions
- [ ] Journal chart/timeline loads for the new log

## Persistence Check
- [ ] Trigger a manual redeploy
- [ ] Previously created log still exists after redeploy

## Incident Notes (if something fails)
- [ ] Copy traceback + deploy log lines
- [ ] Verify env vars and DB path first
- [ ] Verify DB tables in Render shell:
  - `SELECT name FROM sqlite_master WHERE type='table';`
