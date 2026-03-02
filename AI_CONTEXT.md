# Project Context – CS50 Final Project – Surf Journal
This is a learning project built as part of CS50.
This is currently a local Flask web application.

The goal is to create a simple, functional web application that:
- Stores surf sessions
- Fetches surf/weather data from Open-Meteo
- Displays 24h surf conditions next to journal entries
- Can be deployed in a simple way

This is Version 1 of the project.

## Current stack
- Python (Flask)
- SQLite
- HTML + Jinja templates
- CSS (moving from inline styles to stylesheet)
- Open-Meteo API for surf/weather data
- Git for version control
- VSCode for development
- Local development for now

## Current Priority
The priority is:

- Build a working application step by step
- Understand everything that is written
- Keep the structure simple
- Avoid premature optimization
- Avoid over-engineering
- Focus on learning fundamentals in line with CS50's scope
- Improve UI, website design and navigation

This version should NOT:
- Introduce advanced architecture
- Add service layers unless explicitly asked
- Add authentication unless explicitly asked
- Add unnecessary abstractions
- Refactor for scalability

Refactoring and architectural improvements will be part of later iterations.

## Learning Philosophy
When suggesting code:

- Prefer clarity over cleverness
- Keep logic inside routes if it helps learning
- Avoid advanced design patterns
- Explain what the code does
- Explain WHY something works
- Avoid writing large blocks without explanation
- Do not assume prior backend knowledge

This project is used to learn:
- Flask basics
- HTTP fundamentals
- APIs
- Databases (SQLite)
- HTML and templates
- Basic CSS
- Debugging
- Security fundamentals
- Git workflow

## Folder Structure
- app.py
- templates/
- static/
- surflog.db

## Coding Principles
- Prefer clarity over cleverness
- Avoid magic one-liners
- Explain reasoning
- Follow PEP8
- Use clear variable names
- Keep functions readable
- Keep routes understandable

## Description of the application
- Build a journal of surf sessions
- The journal navigation resembles that of MS OneNote
- Entries are created by users
- Currently there is only one user group, in a way that for now all entries are part of that group
- The target group are surfers/users want to contribute to a shared journal, so that they can learn from each other experiences and analyse how forecasted conditions turned out to behave in reality at various surf spots
- Current surf spots are focused on Danish west coast
- In this version there is no login and credentials, because it is not critical to know so precisely who has entered the log
- Fetch and store Open-Meteo 24h weather and wave data for the date of each entry
- Each log displays relevant information about the session, e.g. surf spot, weather, tide and wave conditions along that day, individual notes, etc.
- All log data is stored in a database
- In the journal, weather and ocean conditions in each log are to be displayed in a graph that shows the evolution of conditions hour by hour at the date of the entry

## Database Schema
sqlite> .schema
CREATE TABLE groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE surf_spots (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    coast TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE surf_logs (
    id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL,
    spot_id INTEGER NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    session_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE surf_conditions (
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

    UNIQUE(log_id, observed_at)
);

## Future goals
- Once there previous goals are reached, the aim is to improve project structure and refactor to be more efficient and modern, but especially for me to learn new and better ways of creating a web application
- Include log in, user accounts, group accounts
- Add logic to manage surf spots (add, remove, edit)
