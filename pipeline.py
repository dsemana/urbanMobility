"""
NYC Yellow Taxi Data Pipeline
Cleans, enriches, and loads trip data into SQLite database.
Processes the data rows in chunks; excludes suspicious records with transparent logging.
"""

import pandas as pd
import numpy as np
import sqlite3
import json
import os
import sys
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
TRIP_CSV      = os.path.join(DATA_DIR, 'yellow_tripdata_2019-01.csv')
ZONE_CSV      = os.path.join(DATA_DIR, 'taxi_zone_lookup.csv')
DB_PATH       = os.path.join(DATA_DIR, 'nyc_taxi.db')
LOG_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs', 'exclusion_log.json')
CHUNK_SIZE    = 100_000

# ── Lookup maps for human-readable labels ─────────────────────────────────────
RATECODE_MAP = {1:'Standard', 2:'JFK', 3:'Newark', 4:'Nassau/Westchester', 5:'Negotiated', 6:'Group ride', 99:'Unknown'}
PAYMENT_MAP  = {1:'Credit card', 2:'Cash', 3:'No charge', 4:'Dispute', 5:'Unknown', 6:'Voided'}
VENDOR_MAP   = {1:'Creative Mobile Tech', 2:'VeriFone Inc'}

# ── Exclusion counters ─────────────────────────────────────────────────────────
exclusion_log = {
    "pipeline_run": datetime.now().isoformat(),
    "total_raw_rows": 0,
    "total_loaded": 0,
    "exclusions": {
        "wrong_year":          {"count": 0, "reason": "Pickup year not 2019 (data entry / test records)"},
        "negative_fare":       {"count": 0, "reason": "fare_amount < 0 (refund entries, not trips)"},
        "zero_distance":       {"count": 0, "reason": "trip_distance == 0 and fare > 2.50 (no-movement anomaly)"},
        "extreme_distance":    {"count": 0, "reason": "trip_distance > 100 miles (physically implausible for taxi)"},
        "extreme_fare":        {"count": 0, "reason": "fare_amount > 500 (data-entry error threshold)"},
        "negative_duration":   {"count": 0, "reason": "dropoff before pickup (timestamp error)"},
        "extreme_duration":    {"count": 0, "reason": "trip_duration > 180 min (abandoned meter / error)"},
        "zero_passengers":     {"count": 0, "reason": "passenger_count == 0 (meter test or data gap)"},
        "invalid_ratecode":    {"count": 0, "reason": "RatecodeID not in {1-6, 99}"},
    }
}


def init_db(conn):
    """Create normalized schema with indexes."""
    cur = conn.cursor()

    # Dimension: zones
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dim_zones (
        location_id   INTEGER PRIMARY KEY,
        borough       TEXT NOT NULL,
        zone          TEXT NOT NULL,
        service_zone  TEXT NOT NULL
    )""")

    # Dimension: date (enables fast time-series queries)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dim_date (
        date_id     INTEGER PRIMARY KEY,   -- YYYYMMDD
        year        INTEGER,
        month       INTEGER,
        day         INTEGER,
        weekday     INTEGER,               -- 0=Mon … 6=Sun
        weekday_name TEXT,
        is_weekend  INTEGER
    )""")

    # Dimension: time-of-day buckets
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dim_time_of_day (
        hour          INTEGER PRIMARY KEY,
        period_label  TEXT,                -- 'Late Night', 'Early Morning', …
        is_rush_hour  INTEGER
    )""")

    # Fact: trips
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fact_trips (
        trip_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id            INTEGER,
        vendor_name          TEXT,
        pickup_datetime      TEXT,
        dropoff_datetime     TEXT,
        pickup_date_id       INTEGER REFERENCES dim_date(date_id),
        pickup_hour          INTEGER REFERENCES dim_time_of_day(hour),
        passenger_count      INTEGER,
        trip_distance        REAL,
        ratecode_id          INTEGER,
        ratecode_label       TEXT,
        store_fwd_flag       TEXT,
        pu_location_id       INTEGER REFERENCES dim_zones(location_id),
        do_location_id       INTEGER REFERENCES dim_zones(location_id),
        payment_type         INTEGER,
        payment_label        TEXT,
        fare_amount          REAL,
        extra                REAL,
        mta_tax              REAL,
        tip_amount           REAL,
        tolls_amount         REAL,
        improvement_surcharge REAL,
        congestion_surcharge REAL,
        total_amount         REAL,
        -- Derived features
        trip_duration_min    REAL,         -- (dropoff - pickup) in minutes
        speed_mph            REAL,         -- distance / duration_hours
        tip_pct              REAL,         -- tip_amount / fare_amount * 100
        fare_per_mile        REAL          -- fare_amount / trip_distance
    )""")

    # Indexes for dashboard query patterns
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_pu_date   ON fact_trips(pickup_date_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_pu_hour   ON fact_trips(pickup_hour)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_pu_loc    ON fact_trips(pu_location_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_do_loc    ON fact_trips(do_location_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_payment   ON fact_trips(payment_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_distance  ON fact_trips(trip_distance)")

    conn.commit()


def load_zones(conn):
    """Insert zone dimension data."""
    zones = pd.read_csv(ZONE_CSV)
    zones.columns = ['location_id', 'borough', 'zone', 'service_zone']
    zones.to_sql('dim_zones', conn, if_exists='replace', index=False)
    print(f"Loaded {len(zones)} zones")


def populate_date_dim(conn):
    """Pre-populate dim_date for all days in January 2019."""
    import calendar
    rows = []
    for day in range(1, 32):
        dt = datetime(2019, 1, day)
        date_id = int(dt.strftime('%Y%m%d'))
        rows.append({
            'date_id': date_id,
            'year': 2019, 'month': 1, 'day': day,
            'weekday': dt.weekday(),
            'weekday_name': dt.strftime('%A'),
            'is_weekend': 1 if dt.weekday() >= 5 else 0
        })
    pd.DataFrame(rows).to_sql('dim_date', conn, if_exists='replace', index=False)
    print(f"Loaded {len(rows)} date records")


def populate_time_dim(conn):
    """Pre-populate dim_time_of_day for all 24 hours."""
    def label(h):
        if 0  <= h < 5:  return 'Late Night'
        if 5  <= h < 9:  return 'Early Morning'
        if 9  <= h < 12: return 'Morning'
        if 12 <= h < 15: return 'Early Afternoon'
        if 15 <= h < 18: return 'Afternoon'
        if 18 <= h < 21: return 'Evening'
        return 'Night'
    rush = lambda h: 1 if h in (7, 8, 9, 16, 17, 18) else 0
    rows = [{'hour': h, 'period_label': label(h), 'is_rush_hour': rush(h)} for h in range(24)]
    pd.DataFrame(rows).to_sql('dim_time_of_day', conn, if_exists='replace', index=False)
    print("Loaded 24 time-of-day records")


VALID_RATECODES = {1, 2, 3, 4, 5, 6, 99}

def clean_chunk(df):
    """Apply cleaning rules and return (clean_df, exclusion_counts)."""
    exc = {k: 0 for k in exclusion_log['exclusions']}
    original = len(df)

    # Parse timestamps
    df['tpep_pickup_datetime']  = pd.to_datetime(df['tpep_pickup_datetime'],  errors='coerce')
    df['tpep_dropoff_datetime'] = pd.to_datetime(df['tpep_dropoff_datetime'], errors='coerce')

    # Drop rows where timestamps couldn't parse
    df = df.dropna(subset=['tpep_pickup_datetime', 'tpep_dropoff_datetime'])

    # Wrong year
    mask = df['tpep_pickup_datetime'].dt.year != 2019
    exc['wrong_year'] = int(mask.sum())
    df = df[~mask]

    # Negative fare
    mask = df['fare_amount'] < 0
    exc['negative_fare'] = int(mask.sum())
    df = df[~mask]

    # Zero distance with significant fare (not standing-fee trips)
    mask = (df['trip_distance'] == 0) & (df['fare_amount'] > 2.50)
    exc['zero_distance'] = int(mask.sum())
    df = df[~mask]

    # Extreme distance
    mask = df['trip_distance'] > 100
    exc['extreme_distance'] = int(mask.sum())
    df = df[~mask]

    # Extreme fare
    mask = df['fare_amount'] > 500
    exc['extreme_fare'] = int(mask.sum())
    df = df[~mask]

    # Trip duration
    df['trip_duration_min'] = (
        (df['tpep_dropoff_datetime'] - df['tpep_pickup_datetime']).dt.total_seconds() / 60
    )
    mask = df['trip_duration_min'] < 0
    exc['negative_duration'] = int(mask.sum())
    df = df[~mask]

    mask = df['trip_duration_min'] > 180
    exc['extreme_duration'] = int(mask.sum())
    df = df[~mask]

    # Zero passengers
    mask = df['passenger_count'] == 0
    exc['zero_passengers'] = int(mask.sum())
    df = df[~mask]

    # Invalid ratecode
    mask = ~df['RatecodeID'].isin(VALID_RATECODES)
    exc['invalid_ratecode'] = int(mask.sum())
    df = df[~mask]

    # Fill missing congestion_surcharge with 0
    df['congestion_surcharge'] = df['congestion_surcharge'].fillna(0)

    return df, exc


def engineer_features(df):
    """Add derived columns for richer analysis."""
    # 1. Speed in mph (trip_distance / duration_hours) — proxy for congestion
    hours = df['trip_duration_min'] / 60
    df['speed_mph'] = np.where(hours > 0, df['trip_distance'] / hours, np.nan)
    df['speed_mph'] = df['speed_mph'].clip(upper=80)   # cap at 80 mph (physical limit)

    # 2. Tip percentage — relative generosity metric
    df['tip_pct'] = np.where(
        df['fare_amount'] > 0,
        (df['tip_amount'] / df['fare_amount'] * 100).clip(upper=200),
        0
    )

    # 3. Fare per mile — pricing efficiency (NaN when distance == 0)
    df['fare_per_mile'] = np.where(
        df['trip_distance'] > 0,
        df['fare_amount'] / df['trip_distance'],
        np.nan
    )

    return df


def transform_chunk(df):
    """Add lookup labels, date/time IDs, and rename columns for DB insertion."""
    df = df.copy()

    df['vendor_name']    = df['VendorID'].map(VENDOR_MAP).fillna('Unknown')
    df['ratecode_label'] = df['RatecodeID'].map(RATECODE_MAP).fillna('Unknown')
    df['payment_label']  = df['payment_type'].map(PAYMENT_MAP).fillna('Unknown')

    df['pickup_date_id'] = df['tpep_pickup_datetime'].dt.strftime('%Y%m%d').astype(int)
    df['pickup_hour']    = df['tpep_pickup_datetime'].dt.hour

    df['pickup_datetime']  = df['tpep_pickup_datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df['dropoff_datetime'] = df['tpep_dropoff_datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # Select and rename for final schema
    out = df.rename(columns={
        'VendorID':             'vendor_id',
        'passenger_count':      'passenger_count',
        'trip_distance':        'trip_distance',
        'RatecodeID':           'ratecode_id',
        'store_and_fwd_flag':   'store_fwd_flag',
        'PULocationID':         'pu_location_id',
        'DOLocationID':         'do_location_id',
        'payment_type':         'payment_type',
        'fare_amount':          'fare_amount',
        'extra':                'extra',
        'mta_tax':              'mta_tax',
        'tip_amount':           'tip_amount',
        'tolls_amount':         'tolls_amount',
        'improvement_surcharge':'improvement_surcharge',
        'congestion_surcharge': 'congestion_surcharge',
        'total_amount':         'total_amount',
    })

    cols = [
        'vendor_id','vendor_name','pickup_datetime','dropoff_datetime',
        'pickup_date_id','pickup_hour','passenger_count','trip_distance',
        'ratecode_id','ratecode_label','store_fwd_flag','pu_location_id','do_location_id',
        'payment_type','payment_label','fare_amount','extra','mta_tax','tip_amount',
        'tolls_amount','improvement_surcharge','congestion_surcharge','total_amount',
        'trip_duration_min','speed_mph','tip_pct','fare_per_mile'
    ]
    return out[cols]


def run_pipeline():
    print("\n═══════════════════════════════════════════")
    print("  NYC TAXI DATA PIPELINE")
    print("═══════════════════════════════════════════")

    # Remove old DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Removed existing database")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")

    print("\n[1/4] Initialising schema…")
    init_db(conn)
    load_zones(conn)
    populate_date_dim(conn)
    populate_time_dim(conn)

    print("\n[2/4] Processing trip data in chunks…")
    chunk_num   = 0
    total_raw   = 0
    total_clean = 0

    for chunk in pd.read_csv(TRIP_CSV, chunksize=CHUNK_SIZE):
        chunk_num += 1
        raw_n = len(chunk)
        total_raw += raw_n

        cleaned, exc_counts = clean_chunk(chunk)

        # Accumulate exclusion counts
        for k, v in exc_counts.items():
            exclusion_log['exclusions'][k]['count'] += v

        enriched = engineer_features(cleaned)
        final    = transform_chunk(enriched)

        final.to_sql('fact_trips', conn, if_exists='append', index=False)
        total_clean += len(final)

        pct = total_clean / max(total_raw, 1) * 100
        print(f"  Chunk {chunk_num:3d}: {raw_n:>7,} raw → {len(final):>7,} clean | "
              f"Running total: {total_clean:>9,} ({pct:.1f}%)")

        sys.stdout.flush()

    exclusion_log['total_raw_rows'] = total_raw
    exclusion_log['total_loaded']   = total_clean

    print(f"\n[3/4] Saving exclusion log…")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, 'w') as f:
        json.dump(exclusion_log, f, indent=2)
    print(f"  ✓ Log written to {LOG_PATH}")

    print(f"\n[4/4] Building summary cache…")
    build_summary_cache(conn)

    conn.close()
    print(f"\nPipeline complete!")
    print(f"   Raw rows   : {total_raw:,}")
    print(f"   Loaded rows: {total_clean:,}")
    excluded = total_raw - total_clean
    print(f"   Excluded   : {excluded:,} ({excluded/total_raw*100:.2f}%)")
    print(f"   DB path    : {DB_PATH}")


def build_summary_cache(conn):
    """Pre-compute heavy aggregates into summary tables for fast dashboard response."""
    cur = conn.cursor()

    # Hourly demand
    conn.execute("DROP TABLE IF EXISTS summary_hourly")
    conn.execute("""
    CREATE TABLE summary_hourly AS
    SELECT
        f.pickup_hour                       AS hour,
        t.period_label,
        t.is_rush_hour,
        COUNT(*)                            AS trip_count,
        ROUND(AVG(f.trip_distance),2)       AS avg_distance,
        ROUND(AVG(f.trip_duration_min),2)   AS avg_duration_min,
        ROUND(AVG(f.fare_amount),2)         AS avg_fare,
        ROUND(AVG(f.speed_mph),2)           AS avg_speed_mph,
        ROUND(AVG(f.tip_pct),2)             AS avg_tip_pct
    FROM fact_trips f
    JOIN dim_time_of_day t ON f.pickup_hour = t.hour
    GROUP BY f.pickup_hour
    ORDER BY f.pickup_hour
    """)

    # Daily demand
    conn.execute("DROP TABLE IF EXISTS summary_daily")
    conn.execute("""
    CREATE TABLE summary_daily AS
    SELECT
        d.date_id, d.day, d.weekday_name, d.is_weekend,
        COUNT(*)                            AS trip_count,
        ROUND(AVG(trip_distance),2)         AS avg_distance,
        ROUND(AVG(fare_amount),2)           AS avg_fare,
        ROUND(SUM(total_amount),2)          AS total_revenue,
        ROUND(AVG(speed_mph),2)             AS avg_speed_mph
    FROM fact_trips f
    JOIN dim_date d ON f.pickup_date_id = d.date_id
    GROUP BY d.date_id
    ORDER BY d.date_id
    """)

    # Borough-level stats
    conn.execute("DROP TABLE IF EXISTS summary_borough")
    conn.execute("""
    CREATE TABLE summary_borough AS
    SELECT
        z.borough                           AS borough,
        COUNT(*)                            AS trip_count,
        ROUND(AVG(f.trip_distance),2)       AS avg_distance,
        ROUND(AVG(f.fare_amount),2)         AS avg_fare,
        ROUND(AVG(f.tip_pct),2)             AS avg_tip_pct,
        ROUND(AVG(f.speed_mph),2)           AS avg_speed_mph,
        ROUND(SUM(f.total_amount),2)        AS total_revenue
    FROM fact_trips f
    JOIN dim_zones z ON f.pu_location_id = z.location_id
    GROUP BY z.borough
    ORDER BY trip_count DESC
    """)

    # Top pickup zones
    conn.execute("DROP TABLE IF EXISTS summary_top_zones")
    conn.execute("""
    CREATE TABLE summary_top_zones AS
    SELECT
        z.location_id, z.zone, z.borough, z.service_zone,
        COUNT(*)                            AS trip_count,
        ROUND(AVG(f.fare_amount),2)         AS avg_fare,
        ROUND(AVG(f.tip_pct),2)             AS avg_tip_pct,
        ROUND(AVG(f.trip_distance),2)       AS avg_distance
    FROM fact_trips f
    JOIN dim_zones z ON f.pu_location_id = z.location_id
    GROUP BY z.location_id
    ORDER BY trip_count DESC
    LIMIT 30
    """)

    # Payment type breakdown
    conn.execute("DROP TABLE IF EXISTS summary_payment")
    conn.execute("""
    CREATE TABLE summary_payment AS
    SELECT
        payment_label,
        COUNT(*)                            AS trip_count,
        ROUND(AVG(fare_amount),2)           AS avg_fare,
        ROUND(AVG(tip_pct),2)               AS avg_tip_pct,
        ROUND(AVG(trip_distance),2)         AS avg_distance
    FROM fact_trips
    GROUP BY payment_label
    ORDER BY trip_count DESC
    """)

    # Fare distribution buckets
    conn.execute("DROP TABLE IF EXISTS summary_fare_buckets")
    conn.execute("""
    CREATE TABLE summary_fare_buckets AS
    SELECT
        CASE
            WHEN fare_amount < 5   THEN '$0-5'
            WHEN fare_amount < 10  THEN '$5-10'
            WHEN fare_amount < 15  THEN '$10-15'
            WHEN fare_amount < 20  THEN '$15-20'
            WHEN fare_amount < 30  THEN '$20-30'
            WHEN fare_amount < 50  THEN '$30-50'
            ELSE '$50+'
        END AS fare_bucket,
        COUNT(*) AS trip_count,
        ROUND(AVG(tip_pct),2) AS avg_tip_pct,
        ROUND(AVG(trip_distance),2) AS avg_distance
    FROM fact_trips
    GROUP BY fare_bucket
    """)

    # Speed by hour (congestion analysis)
    conn.execute("DROP TABLE IF EXISTS summary_speed_hour")
    conn.execute("""
    CREATE TABLE summary_speed_hour AS
    SELECT
        pickup_hour AS hour,
        ROUND(AVG(speed_mph),2)         AS avg_speed,
        ROUND(MIN(speed_mph),2)         AS min_speed,
        ROUND(MAX(speed_mph),2)         AS max_speed,
        COUNT(*)                        AS trip_count
    FROM fact_trips
    WHERE speed_mph IS NOT NULL
    GROUP BY pickup_hour
    ORDER BY pickup_hour
    """)

    conn.commit()
    print("  ✓ Summary tables built")


if __name__ == '__main__':
    run_pipeline()
