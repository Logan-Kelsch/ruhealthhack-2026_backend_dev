#!/usr/bin/env bash
# Let your laptop reach RDS: replaces your previous rule in the dev-access security group with
# your current public IP (/32). Re-run whenever your network changes.
#
#   infra/scripts/db-allow-me.sh            # allow this machine's current IP
#   infra/scripts/db-allow-me.sh --remove   # remove your rule
#
# Rules are labelled "dev:<your IAM user>", so each person only ever has one.
# Environment: PREFIX (default rounds-dev), AWS_REGION (default us-east-1).
set -euo pipefail
source "$(dirname "$0")/common.sh"

sg="$(output network DbDevAccessSecurityGroupId)"
who="$(aws sts get-caller-identity --query Arn --output text | sed 's#.*/##')"
label="dev:$who"

# Drop this person's old rules first.
mapfile -t old < <(aws ec2 describe-security-group-rules --region "$AWS_REGION" \
  --filters "Name=group-id,Values=$sg" \
  --query "SecurityGroupRules[?!IsEgress && Description=='$label'].SecurityGroupRuleId" --output text | tr '\t' '\n' | sed '/^$/d')
if [ ${#old[@]} -gt 0 ]; then
  aws ec2 revoke-security-group-ingress --region "$AWS_REGION" --group-id "$sg" \
    --security-group-rule-ids "${old[@]}" >/dev/null
fi

if [ "${1:-}" = "--remove" ]; then
  echo "Removed Postgres access for $label."
  exit 0
fi

ip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
[[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || { echo "could not read your public IPv4 address" >&2; exit 1; }
aws ec2 authorize-security-group-ingress --region "$AWS_REGION" --group-id "$sg" \
  --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,IpRanges=[{CidrIp=$ip/32,Description=$label}]" >/dev/null
echo "Postgres now reachable from $ip ($label)."
