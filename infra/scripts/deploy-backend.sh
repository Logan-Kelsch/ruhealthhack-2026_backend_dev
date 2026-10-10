#!/usr/bin/env bash
# Deploy a commit of the backend to the EC2 instance through SSM Run Command, then wait and
# print the result. The instance checks out the commit and runs infra/scripts/server-deploy.sh.
#
#   infra/scripts/deploy-backend.sh [git-sha]     # default: the current HEAD (must be pushed)
#
# Environment: PREFIX (default rounds-dev), AWS_REGION (default us-east-1),
# REPO_URL (default: this checkout's origin as an https URL; the repo is public).
set -euo pipefail
source "$(dirname "$0")/common.sh"

sha="${1:-$(git -C "$REPO_DIR" rev-parse HEAD)}"
repo_url="${REPO_URL:-$(git -C "$REPO_DIR" remote get-url origin | sed -E 's#^git@github.com:#https://github.com/#')}"
instance="$(output app InstanceId)"

# Only non-secret values go in the command: SSM keeps command text in its history.
commands="$(jq -n --arg sha "$sha" --arg url "$repo_url" --arg prefix "$PREFIX" --arg region "$AWS_REGION" '{commands: [
  "set -eu",
  "cloud-init status --wait >/dev/null || true",
  "cd /opt/app",
  "[ -d .git ] || sudo -u ec2-user git clone --quiet \($url) .",
  "sudo -u ec2-user git fetch --quiet origin",
  "sudo -u ec2-user git checkout --quiet --force \($sha)",
  "bash /opt/app/infra/scripts/server-deploy.sh \($prefix) \($region)"
]}')"

command_id="$(aws ssm send-command --region "$AWS_REGION" \
  --instance-ids "$instance" \
  --document-name AWS-RunShellScript \
  --comment "deploy ${sha:0:12}" \
  --timeout-seconds 600 \
  --parameters "$commands" \
  --query Command.CommandId --output text)"
echo "SSM command $command_id on $instance (commit ${sha:0:12})"

# The waiter gives up after 100 seconds; first deploys install Python, so keep waiting.
until status="$(aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$command_id" \
    --instance-id "$instance" --query Status --output text 2>/dev/null)" \
    && [[ "$status" != Pending && "$status" != InProgress && "$status" != Delayed ]]; do
  sleep 5
done
aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$command_id" \
  --instance-id "$instance" --query "[StandardOutputContent,StandardErrorContent]" --output text
echo "status: $status"
[ "$status" = Success ]
