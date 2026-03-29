#!/usr/bin/env python3
"""
Resource Monitor & GCP Auto-Scaler
Monitors CPU, Memory, Disk usage on local VirtualBox VM.
Triggers GCP instance creation when any metric exceeds THRESHOLD (75%).
"""

import subprocess
import time
import json
import logging
import os
from datetime import datetime

import psutil

# ── Configuration ────────────────────────────────────────────────────────────
THRESHOLD       = 75.0          # % — trigger migration above this value
CHECK_INTERVAL  = 30            # seconds between checks
GCP_PROJECT     = os.getenv("GCP_PROJECT", "your-gcp-project-id")
GCP_ZONE        = os.getenv("GCP_ZONE",    "us-central1-a")
GCP_INSTANCE    = os.getenv("GCP_INSTANCE","vm-autoscale-worker")
GCP_MACHINE     = os.getenv("GCP_MACHINE", "e2-medium")
GCP_IMAGE       = os.getenv("GCP_IMAGE",   "debian-cloud/debian-11")
METRICS_FILE    = "/var/log/vm_metrics.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/var/log/vm_monitor.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Metric Collection ─────────────────────────────────────────────────────────

def collect_metrics() -> dict:
    cpu    = psutil.cpu_percent(interval=2)
    mem    = psutil.virtual_memory().percent
    disk   = psutil.disk_usage("/").percent
    net_io = psutil.net_io_counters()
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cpu_percent":    cpu,
        "memory_percent": mem,
        "disk_percent":   disk,
        "net_bytes_sent": net_io.bytes_sent,
        "net_bytes_recv": net_io.bytes_recv,
    }

def write_metrics(metrics: dict) -> None:
    try:
        with open(METRICS_FILE, "a") as f:
            f.write(json.dumps(metrics) + "\n")
    except OSError as e:
        log.warning("Could not write metrics file: %s", e)

# ── GCP Operations ────────────────────────────────────────────────────────────

def gcp_instance_exists() -> bool:
    result = subprocess.run(
        ["gcloud", "compute", "instances", "describe", GCP_INSTANCE,
         "--zone", GCP_ZONE, "--project", GCP_PROJECT,
         "--format=value(status)"],
        capture_output=True, text=True,
    )
    return result.returncode == 0

def create_gcp_instance() -> bool:
    log.info("Creating GCP instance %s in %s …", GCP_INSTANCE, GCP_ZONE)
    result = subprocess.run(
        [
            "gcloud", "compute", "instances", "create", GCP_INSTANCE,
            "--project",      GCP_PROJECT,
            "--zone",         GCP_ZONE,
            "--machine-type", GCP_MACHINE,
            "--image-family",  "debian-11",
            "--image-project", "debian-cloud",
            "--tags",         "http-server,https-server",
            "--metadata",     "startup-script=apt-get update && apt-get install -y python3 python3-pip",
        ],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        log.info("GCP instance created successfully.")
        return True
    log.error("Failed to create GCP instance: %s", result.stderr)
    return False

def deploy_app_to_gcp() -> None:
    log.info("Deploying application to GCP instance …")
    # Get external IP
    ip_result = subprocess.run(
        ["gcloud", "compute", "instances", "describe", GCP_INSTANCE,
         "--zone", GCP_ZONE, "--project", GCP_PROJECT,
         "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"],
        capture_output=True, text=True,
    )
    ip = ip_result.stdout.strip()
    if not ip:
        log.error("Could not get GCP instance IP.")
        return

    # Copy app files
    subprocess.run(
        ["gcloud", "compute", "scp", "--recurse",
         "/opt/app", f"{GCP_INSTANCE}:/opt/",
         "--zone", GCP_ZONE, "--project", GCP_PROJECT],
        check=False,
    )
    # Start app
    subprocess.run(
        ["gcloud", "compute", "ssh", GCP_INSTANCE,
         "--zone", GCP_ZONE, "--project", GCP_PROJECT,
         "--command", "cd /opt/app && pip3 install -r requirements.txt && nohup python3 app.py &"],
        check=False,
    )
    log.info("App deployed to GCP at %s", ip)

# ── Main Loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("VM Resource Monitor started. Threshold=%.0f%%  Interval=%ds",
             THRESHOLD, CHECK_INTERVAL)
    scaled_out = False

    while True:
        metrics = collect_metrics()
        write_metrics(metrics)

        breached = [
            f"CPU={metrics['cpu_percent']:.1f}%"
            for _ in [None] if metrics["cpu_percent"] > THRESHOLD
        ] + [
            f"Memory={metrics['memory_percent']:.1f}%"
            for _ in [None] if metrics["memory_percent"] > THRESHOLD
        ] + [
            f"Disk={metrics['disk_percent']:.1f}%"
            for _ in [None] if metrics["disk_percent"] > THRESHOLD
        ]

        log.info(
            "CPU=%.1f%%  MEM=%.1f%%  DISK=%.1f%%",
            metrics["cpu_percent"],
            metrics["memory_percent"],
            metrics["disk_percent"],
        )

        if breached and not scaled_out:
            log.warning("Threshold breached: %s — triggering GCP scale-out!", ", ".join(breached))
            if not gcp_instance_exists():
                if create_gcp_instance():
                    time.sleep(60)          # wait for boot
                    deploy_app_to_gcp()
                    scaled_out = True
            else:
                log.info("GCP instance already running.")
                scaled_out = True

        elif not breached and scaled_out:
            log.info("Usage back below threshold. Scale-in could be triggered here.")
            # Optionally: delete GCP instance to save costs
            # scaled_out = False

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
