"""
NYC Taxi Analytics — Flask Backend
Serves the dashboard at http://localhost:5000
and all API data at http://localhost:5000/api/...
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import json
import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR    = os.path.join(BASE_DIR, '..')
DB_PATH     = os.path.join(ROOT_DIR, 'data',    'nyc_taxi.db')
LOG_PATH    = os.path.join(ROOT_DIR, 'logs',    'exclusion_log.json')
STATIC_DIR  = os.path.join(ROOT_DIR, 'frontend')

app = Flask(__name__, static_folder=STATIC_DIR)
CORS(app)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def rows_to_list(rows):
    return [dict(r) for r in rows]


#  SERVE FRONTEND

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

#  API ENDPOINTS

# ── Health ────────────────────────────────────────────────────────────────────
@app.route('/api/health')
def health():
    try:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) AS n FROM fact_trips").fetchone()['n']
        conn.close()
        return jsonify({"status": "ok", "total_trips": total})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Summary (KPIs) — used by app.js /summary ─────────────────────────────────
@app.route('/api/summary')
def summary():
    conn = get_db()
    row = conn.execute("""
        SELECT
            COUNT(*)                            AS trips,
            ROUND(SUM(total_amount), 2)         AS revenue,
            ROUND(AVG(trip_distance), 2)        AS avg_distance,
            ROUND(AVG(trip_duration_min), 2)    AS avg_duration,
            ROUND(AVG(fare_amount), 2)          AS avg_fare,
            ROUND(AVG(speed_mph), 2)            AS avg_speed,
            ROUND(AVG(tip_pct), 2)              AS avg_tip_pct
        FROM fact_trips
    """).fetchone()

    # Suspicious / excluded count from the log
    suspicious = 0
    try:
        with open(LOG_PATH) as f:
            log = json.load(f)
            suspicious = log['total_raw_rows'] - log['total_loaded']
    except Exception:
        pass

    result = dict(row)
    result['suspicious_count'] = suspicious
    conn.close()
    return jsonify(result)


# ── Hourly demand ─────────────────────────────────────────────────────────────
@app.route('/api/hourly')
def hourly():
    conn = get_db()
    rows = conn.execute("""
        SELECT hour, trip_count AS trips, avg_fare, avg_speed_mph, avg_tip_pct
        FROM summary_hourly
        ORDER BY hour
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Borough stats ─────────────────────────────────────────────────────────────
@app.route('/api/boroughs')
def boroughs():
    conn = get_db()
    rows = conn.execute("""
        SELECT borough, trip_count AS trips, avg_fare, avg_speed_mph, total_revenue
        FROM summary_borough
        WHERE borough IS NOT NULL AND borough != 'Unknown'
        ORDER BY trips DESC
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Top pickup zones ──────────────────────────────────────────────────────────
@app.route('/api/top-zones')
def top_zones():
    limit = min(int(request.args.get('limit', 10)), 30)
    conn  = get_db()
    rows  = conn.execute(f"""
        SELECT zone, borough, trip_count AS pickups, avg_fare, avg_distance, avg_tip_pct
        FROM summary_top_zones
        LIMIT {limit}
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Ranked routes (top corridors scored by revenue × volume) ──────────────────
@app.route('/api/ranked-routes')
def ranked_routes():
    limit = min(int(request.args.get('limit', 10)), 25)
    conn  = get_db()
    rows  = conn.execute(f"""
        SELECT
            pu.zone || ' → ' || du.zone        AS route,
            pu.borough                          AS pickup_borough,
            du.borough                          AS dropoff_borough,
            COUNT(*)                            AS trip_count,
            ROUND(SUM(f.total_amount), 2)       AS total_revenue,
            ROUND(AVG(f.fare_amount), 2)        AS avg_fare,
            ROUND(AVG(f.trip_distance), 2)      AS avg_distance,
            ROUND(
                (COUNT(*) * 1.0 / 50000) +
                (SUM(f.total_amount) / 1000000.0),
                3
            )                                   AS score
        FROM fact_trips f
        JOIN dim_zones pu ON f.pu_location_id = pu.location_id
        JOIN dim_zones du ON f.do_location_id = du.location_id
        WHERE pu.zone != 'Unknown' AND du.zone != 'Unknown'
        GROUP BY f.pu_location_id, f.do_location_id
        ORDER BY score DESC
        LIMIT {limit}
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Daily demand ──────────────────────────────────────────────────────────────
@app.route('/api/daily')
def daily():
    conn = get_db()
    rows = conn.execute("""
        SELECT day, weekday_name, is_weekend, trip_count, avg_fare,
               total_revenue, avg_speed_mph
        FROM summary_daily
        ORDER BY date_id
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Payment breakdown ─────────────────────────────────────────────────────────
@app.route('/api/payments')
def payments():
    conn = get_db()
    rows = conn.execute("""
        SELECT payment_label, trip_count, avg_fare, avg_tip_pct, avg_distance
        FROM summary_payment
        ORDER BY trip_count DESC
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Fare distribution ─────────────────────────────────────────────────────────
@app.route('/api/fare-distribution')
def fare_distribution():
    conn = get_db()
    rows = conn.execute("""
        SELECT fare_bucket, trip_count, avg_tip_pct, avg_distance
        FROM summary_fare_buckets
        ORDER BY CASE fare_bucket
            WHEN '$0-5'   THEN 1 WHEN '$5-10'  THEN 2
            WHEN '$10-15' THEN 3 WHEN '$15-20' THEN 4
            WHEN '$20-30' THEN 5 WHEN '$30-50' THEN 6
            ELSE 7 END
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Congestion (speed by hour) ─────────────────────────────────────────────────
@app.route('/api/congestion')
def congestion():
    conn = get_db()
    rows = conn.execute("""
        SELECT hour, avg_speed, trip_count
        FROM summary_speed_hour
        ORDER BY hour
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Weekday patterns ──────────────────────────────────────────────────────────
@app.route('/api/weekday-patterns')
def weekday_patterns():
    conn = get_db()
    rows = conn.execute("""
        SELECT d.weekday_name, d.weekday, d.is_weekend,
               COUNT(*)                      AS trip_count,
               ROUND(AVG(f.fare_amount), 2)  AS avg_fare,
               ROUND(AVG(f.trip_distance),2) AS avg_distance,
               ROUND(AVG(f.speed_mph), 2)    AS avg_speed,
               ROUND(AVG(f.tip_pct), 2)      AS avg_tip_pct
        FROM fact_trips f
        JOIN dim_date d ON f.pickup_date_id = d.date_id
        GROUP BY d.weekday_name
        ORDER BY d.weekday
    """).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ── Exclusion log ─────────────────────────────────────────────────────────────
@app.route('/api/exclusion-log')
def exclusion_log():
    try:
        with open(LOG_PATH) as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"error": "Log not found"}), 404


# ── Trip explorer (filterable, paginated) ──────────────────────────────────────
@app.route('/api/trips')
def trips():
    borough      = request.args.get('borough',      default='')
    min_distance = request.args.get('min_distance', type=float, default=0)
    max_distance = request.args.get('max_distance', type=float, default=200)
    hour_min     = request.args.get('hour_min',     type=int,   default=0)
    hour_max     = request.args.get('hour_max',     type=int,   default=23)
    fare_min     = request.args.get('fare_min',     type=float, default=0)
    fare_max     = request.args.get('fare_max',     type=float, default=500)
    payment      = request.args.get('payment',      default='')
    limit        = min(int(request.args.get('limit', 50)), 200)
    page         = max(1, request.args.get('page',  type=int,   default=1))
    offset       = (page - 1) * limit

    where = ["f.trip_distance >= ?", "f.trip_distance <= ?",
             "f.pickup_hour >= ?",   "f.pickup_hour <= ?",
             "f.fare_amount >= ?",   "f.fare_amount <= ?"]
    params = [min_distance, max_distance, hour_min, hour_max, fare_min, fare_max]

    if borough:
        where.append("pu.borough = ?")
        params.append(borough)
    if payment:
        where.append("f.payment_label = ?")
        params.append(payment)

    where_sql = " AND ".join(where)
    conn = get_db()

    total = conn.execute(f"""
        SELECT COUNT(*) AS n FROM fact_trips f
        JOIN dim_zones pu ON f.pu_location_id = pu.location_id
        WHERE {where_sql}
    """, params).fetchone()['n']

    rows = conn.execute(f"""
        SELECT
            f.pickup_datetime,
            f.trip_distance,
            f.trip_duration_min     AS duration_min,
            f.fare_amount,
            f.tip_amount,
            f.total_amount,
            f.speed_mph,
            f.tip_pct,
            f.payment_label,
            f.passenger_count,
            pu.zone                 AS pickup_zone,
            pu.borough              AS pickup_borough,
            du.zone                 AS dropoff_zone,
            du.borough              AS dropoff_borough
        FROM fact_trips f
        JOIN dim_zones pu ON f.pu_location_id = pu.location_id
        JOIN dim_zones du ON f.do_location_id = du.location_id
        WHERE {where_sql}
        ORDER BY f.trip_id
        LIMIT {limit} OFFSET {offset}
    """, params).fetchall()
    conn.close()

    return jsonify({
        "total": total,
        "page":  page,
        "pages": (total + limit - 1) // limit,
        "trips": rows_to_list(rows)
    })


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print(f"\n  NYC Taxi Dashboard → http://localhost:5000")
    print(f"  Database            → {os.path.abspath(DB_PATH)}\n")
    app.run(debug=True, port=5000, host='0.0.0.0')
