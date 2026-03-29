"""
Sample Flask application that exposes Prometheus metrics.
Used to simulate load and demonstrate auto-scaling.
"""
import time
import random
import threading

from flask import Flask, jsonify
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

app = Flask(__name__)

# ── Prometheus Metrics ────────────────────────────────────────────────────────
REQUEST_COUNT   = Counter("app_requests_total", "Total HTTP requests", ["method", "endpoint"])
REQUEST_LATENCY = Histogram("app_request_latency_seconds", "Request latency")
ACTIVE_USERS    = Gauge("app_active_users", "Simulated active users")

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    REQUEST_COUNT.labels(method="GET", endpoint="/").inc()
    return jsonify({"status": "ok", "message": "Sample App Running"})

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route("/load")
def generate_load():
    """Endpoint to simulate CPU load for demo purposes."""
    REQUEST_COUNT.labels(method="GET", endpoint="/load").inc()
    with REQUEST_LATENCY.time():
        # Simulate work
        total = sum(i * i for i in range(500_000))
    return jsonify({"status": "load generated", "result": total})

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

# ── Background User Simulator ─────────────────────────────────────────────────

def simulate_users():
    while True:
        ACTIVE_USERS.set(random.randint(10, 200))
        time.sleep(5)

threading.Thread(target=simulate_users, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
