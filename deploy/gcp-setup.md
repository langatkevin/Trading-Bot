# Running the bot on Google Cloud (paper trading)

One small always-on VM runs the bot in Docker. Keys live in Secret Manager.

```bash
PROJECT=your-gcp-project
ZONE=us-east1-b          # close to Alpaca's US servers; e2-micro here is free-tier eligible
gcloud config set project $PROJECT
gcloud services enable compute.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com

# 1. Store PAPER keys (paste when prompted, they never touch the repo)
printf '%s' "$ALPACA_API_KEY"    | gcloud secrets create alpaca-api-key    --data-file=-
printf '%s' "$ALPACA_SECRET_KEY" | gcloud secrets create alpaca-secret-key --data-file=-

# 2. Build and push the image
gcloud artifacts repositories create bot --repository-format=docker --location=us-east1
gcloud builds submit --tag us-east1-docker.pkg.dev/$PROJECT/bot/trading-bot:latest

# 3. Service account that can only read those secrets and write logs
gcloud iam service-accounts create trading-bot
SA=trading-bot@$PROJECT.iam.gserviceaccount.com
for s in alpaca-api-key alpaca-secret-key; do
  gcloud secrets add-iam-policy-binding $s --member=serviceAccount:$SA --role=roles/secretmanager.secretAccessor
done
gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=roles/logging.logWriter
gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=roles/artifactregistry.reader

# 4. Create the VM (Container-Optimized OS) and start the bot with restart=always
gcloud compute instances create trading-bot --zone=$ZONE --machine-type=e2-micro \
  --image-family=cos-stable --image-project=cos-cloud --service-account=$SA --scopes=cloud-platform \
  --metadata-from-file=startup-script=deploy/startup.sh
```

Then set up:
- **Alerts:** Cloud Logging → Log-based alert on `severity>=ERROR` for the VM, plus one on `"risk:"` warnings.
- **Budget:** Billing → Budgets & alerts, e.g. $10/month.
- **Stop the bot fast:** `gcloud compute ssh trading-bot -- docker exec bot touch KILL_SWITCH`, or stop the VM.
