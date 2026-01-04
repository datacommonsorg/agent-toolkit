#!/bin/bash
set -e

# Usage: ./scripts/setup_iam.sh <TARGET_PROJECT_ID>
# Example: ./scripts/setup_iam.sh datcom-mixer-autopush

TARGET_PROJECT=$1
CI_PROJECT="datcom-ci"
# The Cloud Build Service Account from datcom-ci (User provided)
CI_SA_EMAIL="879489846695@cloudbuild.gserviceaccount.com"
RUNTIME_SA_NAME="datacommons-mcp-server"
RUNTIME_SA_EMAIL="$RUNTIME_SA_NAME@$TARGET_PROJECT.iam.gserviceaccount.com"

if [ -z "$TARGET_PROJECT" ]; then
    echo "Usage: $0 <TARGET_PROJECT_ID>"
    exit 1
fi

echo "--- Setting up project: $TARGET_PROJECT ---"

# 1. Enable Cloud Run API
echo "Enabling Cloud Run API..."
gcloud services enable run.googleapis.com --project "$TARGET_PROJECT"

# 2. Create Runtime Service Account (if not exists)
echo "Creating Runtime Service Account ($RUNTIME_SA_EMAIL)..."
# Check if exists to avoid error
if ! gcloud iam service-accounts describe "$RUNTIME_SA_EMAIL" --project "$TARGET_PROJECT" > /dev/null 2>&1; then
    gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
        --display-name "DataCommons MCP Server Runtime Identity" \
        --project "$TARGET_PROJECT"
else
    echo "Service account already exists."
fi

# 3. Grant Cloud Build SA permission to deploy (Cloud Run Developer)
echo "Granting Cloud Run Developer to CI SA..."
gcloud projects add-iam-policy-binding "$TARGET_PROJECT" \
    --member="serviceAccount:$CI_SA_EMAIL" \
    --role="roles/run.developer" \
    --condition=None

# 4. Grant Cloud Build SA permission to act as the Runtime SA
# Note: We grant this at the project level for simplicity, but it can be granular per SA
echo "Granting Service Account User to CI SA..."
gcloud projects add-iam-policy-binding "$TARGET_PROJECT" \
    --member="serviceAccount:$CI_SA_EMAIL" \
    --role="roles/iam.serviceAccountUser" \
    --condition=None

# 5. Grant Cloud Build SA permission to access TEST_PYPI_TOKEN and PYPI_TOKEN secrets
echo "Granting Secret Accessor to CI SA for TEST_PYPI_TOKEN and PYPI_TOKEN..."
gcloud secrets add-iam-policy-binding test-pypi-token \
    --project="$CI_PROJECT" \
    --member="serviceAccount:$CI_SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None
gcloud secrets add-iam-policy-binding pypi-token \
    --project="$CI_PROJECT" \
    --member="serviceAccount:$CI_SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None

# 5. Grant Runtime SA permission to access secrets in TARGET project
echo "Granting Secret Accessor to Runtime SA for dc-api-key-for-mcp in $TARGET_PROJECT..."
# Note: This assumes the secret 'dc-api-key-for-mcp' already exists in the target project.
# We attempt to bind it; if it fails (secret doesn't exist), we warn but don't exit config.
gcloud secrets add-iam-policy-binding dc-api-key-for-mcp \
    --project="$TARGET_PROJECT" \
    --member="serviceAccount:$RUNTIME_SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None || echo "WARNING: Could not grant secret permission. Ensure secret 'dc-api-key-for-mcp' exists in $TARGET_PROJECT."

echo "--- Setup Complete for $TARGET_PROJECT ---"
echo "NOTE: You should now update your deployment YAML to use: --service-account $RUNTIME_SA_EMAIL"
