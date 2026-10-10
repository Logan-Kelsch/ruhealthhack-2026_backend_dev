#!/usr/bin/env bash
# Runs ON the EC2 instance as root, from the commit that deploy-backend.sh just checked out.
# Writes .env from SSM, installs dependencies, migrates the database and restarts the API.
#
#   bash /opt/app/infra/scripts/server-deploy.sh <prefix> <region>
set -euo pipefail
prefix="$1" region="$2"
app=/opt/app
as_app() { sudo -u ec2-user -H env PATH="/usr/local/bin:$PATH" "$@"; }

# The shared .env, minus laptop AWS credentials: on the instance boto3 must use the instance role.
umask 077
aws ssm get-parameter --region "$region" --name "/$prefix/app-env" --with-decryption \
    --query Parameter.Value --output text \
  | grep -vE '^[[:space:]]*(export[[:space:]]+)?(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|AWS_PROFILE)=' \
  > "$app/.env.new"
chown ec2-user:ec2-user "$app/.env.new"
mv "$app/.env.new" "$app/.env"

cd "$app/backend"
as_app uv sync --no-dev --quiet
as_app uv run --no-sync alembic upgrade head

systemctl enable --quiet rounds-api
systemctl restart rounds-api
port="$(systemctl show rounds-api -p Environment --value | tr ' ' '\n' | sed -n 's/^PORT=//p')"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${port:-8000}/api/health" >/dev/null; then
    echo "backend healthy at $(git -C "$app" rev-parse --short HEAD)"
    exit 0
  fi
  sleep 2
done
journalctl -u rounds-api -n 50 --no-pager
exit 1
