#!/usr/bin/env bash
# Store the shared .env (GitHub secret APP_ENV) in SSM Parameter Store as the SecureString
# /<PREFIX>/app-env, where the instance reads it on deploy. Runs in CI.
#
# Environment: APP_ENV (file contents), PREFIX (default rounds-dev), AWS_REGION (default us-east-1).
set -euo pipefail
source "$(dirname "$0")/common.sh"

if [ -z "${APP_ENV:-}" ]; then
  echo "::warning::GitHub secret APP_ENV is not set; the instance keeps its current .env."
  exit 0
fi
path="/$PREFIX/app-env"
current="$(aws ssm get-parameter --region "$AWS_REGION" --name "$path" --with-decryption \
  --query Parameter.Value --output text 2>/dev/null || true)"
# Skip unchanged values so the parameter's version history only grows on real changes.
if [ "$current" == "$APP_ENV" ]; then
  echo "app-env unchanged"
  exit 0
fi
# Sent on stdin so the contents never appear on a command line.
jq -n --arg name "$path" --arg value "$APP_ENV" \
  '{Name: $name, Value: $value, Type: "SecureString", Overwrite: true}' \
  | aws ssm put-parameter --region "$AWS_REGION" --cli-input-json file:///dev/stdin >/dev/null
echo "app-env updated"
# Tells the workflow to redeploy the backend so the instance picks up the new .env.
echo "changed=true" >>"${GITHUB_OUTPUT:-/dev/null}"
