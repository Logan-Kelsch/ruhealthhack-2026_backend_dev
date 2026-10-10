#!/usr/bin/env bash
# Build frontend/ and upload it to the edge stack's bucket, then invalidate index.html.
# Environment: PREFIX (default rounds-dev), AWS_REGION (default us-east-1).
set -euo pipefail
source "$(dirname "$0")/common.sh"

(cd "$REPO_DIR/frontend" && npm ci && npm run build)
bucket="$(output edge FrontendBucketName)"
dist="$(output edge DistributionId)"
# Hashed assets can be cached for a long time; index.html must always be revalidated.
aws s3 sync "$REPO_DIR/frontend/dist" "s3://$bucket" --delete --exclude index.html \
  --cache-control "public,max-age=31536000,immutable"
aws s3 cp "$REPO_DIR/frontend/dist/index.html" "s3://$bucket/index.html" \
  --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id "$dist" --paths "/index.html" >/dev/null
echo "Deployed to $(output edge SiteUrl)"
