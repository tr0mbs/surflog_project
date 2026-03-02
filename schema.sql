PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS surf_spots (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    coast TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS surf_logs (
    id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL,
    spot_id INTEGER NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    session_date TEXT NOT NULL,
    session_rating REAL,
    session_start_time TEXT,
    session_end_time TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (group_id) REFERENCES groups(id),
    FOREIGN KEY (spot_id) REFERENCES surf_spots(id)
);

CREATE TABLE IF NOT EXISTS surf_conditions (
    id INTEGER PRIMARY KEY,
    log_id INTEGER NOT NULL,
    observed_at TEXT NOT NULL,

    -- Wave (combined sea state)
    wave_height REAL,
    wave_period REAL,
    wave_direction REAL,

    -- Primary swell
    swell_height REAL,
    swell_period REAL,
    swell_direction REAL,

    -- Wind
    wind_speed REAL,
    wind_direction REAL,
    wind_gusts REAL,

    -- Tide
    tide_height REAL,

    -- Weather
    temperature REAL,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(log_id, observed_at),
    FOREIGN KEY (log_id) REFERENCES surf_logs(id)
);

CREATE INDEX IF NOT EXISTS idx_surf_logs_session_date
ON surf_logs(session_date);

CREATE INDEX IF NOT EXISTS idx_surf_conditions_log_id_observed_at
ON surf_conditions(log_id, observed_at);

-- Minimal seed data (safe to rerun)
INSERT OR IGNORE INTO groups (id, name) VALUES
    (1, 'TBay Crew');

INSERT OR IGNORE INTO surf_spots (id, name, latitude, longitude, coast) VALUES
    (1, 'Klitmoller dunes', 57.048170, 8.490684, 'North Sea'),
    (2, 'Klitmoller bay', 57.048170, 8.490684, 'North Sea'),
    (3, 'Klitmoller reef', 57.048170, 8.490684, 'North Sea'),
    (4, 'Bunkers reef', 57.040906, 8.458750, 'North Sea'),
    (5, 'Bunkers beach', 57.040906, 8.458750, 'North Sea'),
    (6, 'Bøgsted Rende', 56.982065, 8.398643, 'North Sea'),
    (7, 'Vorupør long peer', 56.962921, 8.369030, 'North Sea'),
    (8, 'Vorupør short peer', 56.962921, 8.369030, 'North Sea'),
    (9, 'Vorupør dunes', 56.962921, 8.369030, 'North Sea'),
    (10, 'Vorupør south', 56.960619, 8.353278, 'North Sea'),
    (11, 'Stenbjerg', 56.930433, 8.328362, 'North Sea'),
    (12, 'Glorious', 56.806335, 8.237610, 'North Sea'),
    (13, 'Trans Kirke', 56.499503, 8.115371, 'North Sea'),
    (14, 'Thorsminde south pier', 56.369165, 8.114056, 'North Sea'),
    (15, 'Thorsminde north', 56.383236, 8.114530, 'North Sea'),
    (16, 'Hvide Sande north', 56.000864, 8.108253, 'North Sea'),
    (17, 'Hvide Sande south', 55.994270, 8.115286, 'North Sea'),
    (18, 'Agger North', 56.725082, 8.216261, 'North Sea'),
    (19, 'Agger Kanal', 56.716328, 8.205396, 'North Sea'),
    (20, 'Fakir', 57.130057, 8.610927, 'North Sea'),
    (21, 'Hanstholm', 57.129001, 8.630737, 'North Sea'),
    (22, 'Fish Factory', 57.129001, 8.630737, 'North Sea'),
    (23, 'Fjaltring', 56.474725, 8.120245, 'North Sea');

