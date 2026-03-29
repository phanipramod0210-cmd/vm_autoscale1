# VM Resource Monitoring & GCP Auto-Scaling

Monitors a VirtualBox VM with Prometheus + Grafana and automatically provisions a GCP Compute Engine instance when CPU, Memory, or Disk usage exceeds **75%**.

## Quick Start

```bash
# 1. Clone repo and start monitoring stack
git clone https://github.com/your-org/vm-autoscale.git
cd vm-autoscale
docker-compose up -d

# 2. Set GCP credentials
export GCP_PROJECT="your-project-id"
gcloud auth activate-service-account --key-file=key.json

# 3. Start the auto-scaler
python3 scripts/monitor.py

# 4. (Optional) Trigger load test to demonstrate scaling
python3 scripts/load_test.py --workers 8 --duration 120
```

## Services

| Service | URL |
|---------|-----|
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| AlertManager | http://localhost:9093 |
| Sample App | http://localhost:8000 |

## Repository Structure

```
vm-autoscale/
├── docker-compose.yml
├── configs/
│   ├── prometheus.yml
│   ├── alert_rules.yml
│   └── alertmanager.yml
├── scripts/
│   ├── monitor.py        ← main auto-scaler
│   ├── deploy_to_gcp.sh
│   └── load_test.py
└── app/
    ├── app.py
    ├── Dockerfile
    └── requirements.txt
```

## Architecture

```
VirtualBox VM (Ubuntu 22.04)
  └─ Docker Compose
       ├─ Prometheus (scrapes metrics every 15s)
       ├─ Node Exporter (system metrics)
       ├─ Grafana (visualization)
       ├─ AlertManager (alert routing)
       └─ Sample Flask App

monitor.py (runs every 30s)
  └─ If CPU/MEM/DISK > 75% → gcloud create instance → deploy app
```

## Cleanup

```bash
# Delete GCP instance when done
gcloud compute instances delete vm-autoscale-worker --zone us-central1-a
```
