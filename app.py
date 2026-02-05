from flask import Flask, jsonify, render_template, request, redirect, url_for, abort
import sqlite3
import uuid

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
                wind_speed,
                wind_direction,
                tide_height
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
