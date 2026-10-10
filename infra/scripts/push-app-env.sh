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
# The CLI can read its JSON input more than once; stdin cannot be replayed.
# Keep the request private and read the value from the environment, not command arguments.
umask 077
request="$(mktemp)"
trap 'rm -f "$request"' EXIT
jq -n --arg name "$path" \
  '{Name: $name, Value: env.APP_ENV, Type: "SecureString", Overwrite: true}' >"$request"
aws ssm put-parameter --region "$AWS_REGION" --cli-input-json "file://$request" >/dev/null
echo "app-env updated"
# Tells the workflow to redeploy the backend so the instance picks up the new .env.
echo "changed=true" >>"${GITHUB_OUTPUT:-/dev/null}"
