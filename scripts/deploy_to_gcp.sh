#!/bin/bash
# ============================================================
# deploy_to_gcp.sh — Deploy sample app to GCP Compute Engine
# Usage: ./deploy_to_gcp.sh [instance-name] [zone] [project]
# ============================================================
set -euo pipefail

INSTANCE="${1:-vm-autoscale-worker}"
ZONE="${2:-us-central1-a}"
PROJECT="${3:-${GCP_PROJECT:-your-gcp-project-id}}"
MACHINE_TYPE="e2-medium"
APP_DIR="$(cd "$(dirname "$0")/../app" && pwd)"

echo "==> Deploying to GCP"
echo "    Instance : $INSTANCE"
echo "    Zone     : $ZONE"
echo "    Project  : $PROJECT"

# ── Create instance if it doesn't exist ──────────────────────────────────────
if ! gcloud compute instances describe "$INSTANCE" \
        --zone "$ZONE" --project "$PROJECT" &>/dev/null; then
  echo "==> Creating instance $INSTANCE …"
  gcloud compute instances create "$INSTANCE" \
    --project       "$PROJECT" \
    --zone          "$ZONE" \
    --machine-type  "$MACHINE_TYPE" \
    --image-family  debian-11 \
    --image-project debian-cloud \
    --tags          http-server,https-server \
    --metadata      startup-script='#!/bin/bash
      apt-get update -y
      apt-get install -y python3 python3-pip docker.io docker-compose
      systemctl start docker
      systemctl enable docker'
  echo "==> Waiting 60s for instance to boot …"
  sleep 60
fi

# ── Copy application files ────────────────────────────────────────────────────
echo "==> Copying app files …"
gcloud compute scp --recurse "$APP_DIR" "$INSTANCE":/opt/app \
  --zone "$ZONE" --project "$PROJECT"

# ── Start the application ─────────────────────────────────────────────────────
echo "==> Starting application …"
gcloud compute ssh "$INSTANCE" \
  --zone "$ZONE" --project "$PROJECT" \
  --command "
    cd /opt/app
    pip3 install -r requirements.txt
    pkill -f app.py || true
    nohup python3 app.py > /var/log/app.log 2>&1 &
    echo 'App started on port 8000'
  "

# ── Open firewall ─────────────────────────────────────────────────────────────
gcloud compute firewall-rules create allow-app-8000 \
  --project "$PROJECT" \
  --allow tcp:8000 \
  --target-tags http-server \
  --description "Allow sample app traffic" 2>/dev/null || true

EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE" \
  --zone "$ZONE" --project "$PROJECT" \
  --format "value(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "==> Deployment complete!"
echo "    App URL : http://${EXTERNAL_IP}:8000"
echo "    Health  : http://${EXTERNAL_IP}:8000/health"
echo "    Metrics : http://${EXTERNAL_IP}:8000/metrics"
