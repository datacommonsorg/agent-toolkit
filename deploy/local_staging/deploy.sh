#!/bin/bash
set -e

# Configuration
# Configuration
DEPLOY_PROJECT_ID="datcom-mixer-staging"
IMAGE_PROJECT_ID="datcom-ci"
SERVICE_NAME="mcp-server-staging"
IMAGE_NAME="gcr.io/${IMAGE_PROJECT_ID}/datacommons-mcp-server:staging-local-$(date +%s)"
REGION="us-central1"
SERVICE_ACCOUNT="datacommons-mcp-server@datcom-mixer-staging.iam.gserviceaccount.com"

echo "========================================================"
echo "Deploying LOCAL changes to Staging"
echo "Build Project: ${IMAGE_PROJECT_ID}"
echo "Deploy Project: ${DEPLOY_PROJECT_ID}"
echo "Image: ${IMAGE_NAME}"
echo "========================================================"

# 1. Submit build to Cloud Build (using datcom-ci to ensure push permissions)
echo "[1/2] Building and Pushing Container Image..."
gcloud builds submit . \
  --project "${IMAGE_PROJECT_ID}" \
  --tag "${IMAGE_NAME}" \
  --file "deploy/local_staging/Dockerfile"

# 2. Deploy to Cloud Run (in datcom-mixer-staging)
echo "[2/2] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --project "${DEPLOY_PROJECT_ID}" \
  --image "${IMAGE_NAME}" \
  --region "${REGION}" \
  --platform managed \
  --no-allow-unauthenticated \
  --service-account "${SERVICE_ACCOUNT}" \
  --update-secrets=DC_API_KEY=dc-api-key-for-mcp:latest

echo "========================================================"
echo "Deployment Complete!"
echo "Service URL: $(gcloud run services describe ${SERVICE_NAME} --project ${DEPLOY_PROJECT_ID} --region ${REGION} --format 'value(status.url)')"
echo "========================================================"
