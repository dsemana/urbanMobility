# NYC Taxi Intelligence Dashboard
### Full-Stack Urban Mobility Analytics · January 2019 TLC Dataset

---
# AI Usage Declaration

**Project:** NYC Taxi Mobility Dashboard

---

## Where AI was used

### ✅ Understanding the assignment brief
Used AI to clarify requirements, decompose tasks, and discuss what the deliverables should cover — such as what a normalised schema means, what feature engineering involves, and what constitutes a meaningful visualisation.

### ✅ Conceptual explanations
Asked AI to explain concepts encountered during the project — for example, star schema design principles, what makes an outlier in trip data, and how Flask routing works — to deepen understanding before applying them independently.

### ✅ Interpreting data findings
Discussed patterns observed in the dataset with AI to sanity-check interpretations — for instance, whether a 45% speed drop during rush hours is realistic, or what might explain Manhattan's 90.7% trip share.

### ✅ Interpreting data findings
We used AI to find the python concepts that can be used to execute this application

---

## Where AI was not used

### ❌ Code generation
All code — the data pipeline (`pipeline.py`), the Flask API (`app.py`), and the frontend (`index.html`, `app.js`, `styles.css`) — was written entirely by the student without AI assistance.

### ❌ Database design
The relational schema — including the star schema structure, table definitions, column types, foreign key relationships, indexes, and the seven pre-aggregated summary tables — was designed independently by the student.

### ❌ System design and architecture
The three-layer architecture (data pipeline → SQLite → Flask API → browser), the ERD, and the decision to serve the frontend statically from Flask were all decisions made by the student.

### ❌ Data cleaning decisions and feature engineering
The eight exclusion rules, their thresholds, and the three derived features (`trip_duration_min`, `speed_mph`, `tip_pct`) were identified, justified, and implemented by the student.

---

## Declaration

I confirm that artificial intelligence tools were used solely as a learning aid — to clarify concepts and better understand the assignment requirements. No AI tool was used to produce, generate, or write any submitted code, database schema, system design, or written analysis. All technical work represents my own original effort.
---

## What this app does

Processes **7.49 million NYC yellow taxi trips** from January 2019 into a clean relational database, serves the data through a REST API, and visualises it in an interactive dashboard.

```

---

## Project structure

```
nyc-taxi-app/
├── README.md
├── backend/
│   ├── pipeline.py (Data cleaner)
│   └── app.py (main server)
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── data/
│   ├── yellow_tripdata_2019-01.csv
│   ├── taxi_zone_lookup.csv
│   └── nyc_taxi.db (Created by running pipeline script)
└── logs/
    └── exclusion_log.json
```

---

## Setup (do this once)

### 1. Install Python dependencies

```bash
pip install pandas numpy flask flask-cors
```

### 2. Put your data files in the data/ folder

```
data/yellow_tripdata_2019-01.csv
data/taxi_zone_lookup.csv
```

### 3. Run the pipeline

This reads all 7.67M rows, cleans them, and loads them into SQLite. Takes 5–10 minutes.

```bash
cd nyc-taxi-app
python backend/pipeline.py
```

### 4. Start the server

```bash
python backend/app.py
```

You should see:
```
  NYC Taxi Dashboard → http://localhost:5000
  Database           → .../data/nyc_taxi.db
```

Now open your browser and go to:

```
http://localhost:5000
```
---

## Testing the API — 3 ways

### Method 1: Browser (simplest)

With the Flask server running, paste any of these URLs directly into your browser address bar:

```
http://localhost:5000/api/health
http://localhost:5000/api/kpis
http://localhost:5000/api/hourly
http://localhost:5000/api/daily
http://localhost:5000/api/boroughs
http://localhost:5000/api/zones/top?limit=10
http://localhost:5000/api/payments
http://localhost:5000/api/fare-distribution
http://localhost:5000/api/congestion
http://localhost:5000/api/passengers
http://localhost:5000/api/tips-by-payment
http://localhost:5000/api/weekday-patterns
http://localhost:5000/api/corridors?limit=10
http://localhost:5000/api/ratecodes
http://localhost:5000/api/exclusion-log
```

---

## All API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Server status + total trip count |
| GET | `/api/kpis` | Headline KPI aggregates |
| GET | `/api/hourly` | Trip stats by hour of day (0–23) |
| GET | `/api/daily` | Trip stats by calendar day |
| GET | `/api/boroughs` | Borough-level aggregates |
| GET | `/api/zones/top` | Top pickup zones · `?limit=N` (max 30) |
| GET | `/api/payments` | Payment method breakdown |
| GET | `/api/fare-distribution` | Fare bucket counts |
| GET | `/api/congestion` | Avg speed by hour |
| GET | `/api/passengers` | Passenger count distribution |
| GET | `/api/tips-by-payment` | Tip rate by payment method |
| GET | `/api/weekday-patterns` | Weekday vs weekend stats |
| GET | `/api/corridors` | Top origin→destination pairs · `?limit=N` |
| GET | `/api/ratecodes` | Rate code breakdown |
| GET | `/api/exclusion-log` | Data cleaning audit log |
| GET | `/api/trips` | Filterable trip explorer (paginated) |

### Trip explorer filter parameters

| Parameter | Type | Default | Example |
|-----------|------|---------|---------|
| `hour_min` | int 0–23 | 0 | `hour_min=8` |
| `hour_max` | int 0–23 | 23 | `hour_max=9` |
| `dist_min` | float | 0 | `dist_min=1` |
| `dist_max` | float | 50 | `dist_max=5` |
| `fare_min` | float | 0 | `fare_min=10` |
| `fare_max` | float | 200 | `fare_max=50` |
| `borough` | string | (all) | `borough=Manhattan` |
| `payment` | string | (all) | `payment=Credit+card` |
| `page` | int | 1 | `page=2` |

---

## Data pipeline details

### What gets cleaned out

| Rule | Reason |
|------|--------|
| Zero passengers | Meter tests — no real trip |
| Extreme duration > 180 min | Abandoned meter |
| Zero distance with fare > $2.50 | No-movement anomaly |
| Negative fare |Refund entries |
| Wrong year (not 2019) | Data entry errors |
| Extreme distance > 100 mi | Physically implausible |
| Extreme fare > $500 | Data entry errors |
| Negative duration | Timestamp error |

---
## Video Walkthrough
https://youtu.be/tXyvgojhAOg
