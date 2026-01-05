#!/bin/bash

# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# TODO(gmechali): Decide whether we want to delete this as it is for a one time setup only.

set -e

# Usage: ./scripts/setup_apigee_sa.sh <APIGEE_PROJECT_ID> <TARGET_RUN_PROJECT_ID> <CLOUD_RUN_SERVICE_NAME>
# Example: ./scripts/setup_apigee_sa.sh datcom-apigee-dev datcom-mixer-autopush mcp-server-autopush

APIGEE_PROJECT=$1
RUN_PROJECT=$2
SERVICE_NAME=$3
SA_NAME="mcp-invoker"
SA_EMAIL="$SA_NAME@$APIGEE_PROJECT.iam.gserviceaccount.com"

if [ -z "$SERVICE_NAME" ]; then
    echo "Usage: $0 <APIGEE_PROJECT_ID> <TARGET_RUN_PROJECT_ID> <CLOUD_RUN_SERVICE_NAME>"
    echo "Example: $0 datcom-apigee-dev datcom-mixer-autopush mcp-server-autopush"
    exit 1
fi

echo "--- Setting up Apigee Access ---"
echo "Apigee Project: $APIGEE_PROJECT"
echo "Cloud Run Project: $RUN_PROJECT"
echo "Service: $SERVICE_NAME"

# 1. Create Service Account in APIGEE PROJECT
echo "Creating Service Account '$SA_EMAIL' in $APIGEE_PROJECT..."
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project "$APIGEE_PROJECT" > /dev/null 2>&1; then
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name "MCP Service Invoker for Apigee" \
        --project "$APIGEE_PROJECT"
else
    echo "Service account already exists."
fi

# Wait for propagation (IAM consistency)
echo "Waiting for Service Account propagation..."
for i in {1..12}; do
    if gcloud iam service-accounts describe "$SA_EMAIL" --project "$APIGEE_PROJECT" > /dev/null 2>&1; then
        echo "Service Account verified."
        break
    fi
    echo "Waiting for SA to be globally visible... ($i/12)"
    sleep 5
done

# 2. Grant Invoker Permission in CLOUD RUN PROJECT
echo "Granting roles/run.invoker to $SA_EMAIL on service $SERVICE_NAME..."
gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
    --project "$RUN_PROJECT" \
    --region us-central1 \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.invoker"

echo "--- Setup Complete ---"
echo "You can now use '$SA_EMAIL' in your Apigee GoogleAuthentication policy."
