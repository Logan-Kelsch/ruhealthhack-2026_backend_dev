#!/usr/bin/env bash
# Print the outputs of every stack that exists.
# Environment: PREFIX (default rounds-dev), AWS_REGION (default us-east-1).
set -euo pipefail
source "$(dirname "$0")/common.sh"

for stack in "${STACKS[@]}"; do
  echo "==> $PREFIX-$stack"
  aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$PREFIX-$stack" \
    --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table 2>/dev/null \
    || echo "(not deployed)"
done
