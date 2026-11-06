#!/bin/bash
# VM startup script: fetch keys from Secret Manager and run the bot container with auto-restart.
set -euo pipefail
PROJECT=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/project/project-id)
REGION=us-east1
TOKEN=$(curl -s -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
secret() {
  curl -s -H "Authorization: Bearer $TOKEN" \
    "https://secretmanager.googleapis.com/v1/projects/$PROJECT/secrets/$1/versions/latest:access" \
    | python3 -c 'import sys,json,base64;print(base64.b64decode(json.load(sys.stdin)["payload"]["data"]).decode())'
}
export HOME=/home/chronos
docker-credential-gcr configure-docker --registries=$REGION-docker.pkg.dev
docker rm -f bot 2>/dev/null || true
mkdir -p /var/lib/bot-state
docker run -d --name bot --restart=always --log-driver=gcplogs \
  -e ALPACA_API_KEY="$(secret alpaca-api-key)" \
  -e ALPACA_SECRET_KEY="$(secret alpaca-secret-key)" \
  -e ALPACA_PAPER=true \
  -v /var/lib/bot-state:/app/state \
  $REGION-docker.pkg.dev/$PROJECT/bot/trading-bot:latest
