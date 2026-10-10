# shellcheck shell=bash disable=SC2034  # sourced; variables are used by the scripts that source it
# Shared settings for the infra scripts. Values come from the environment, never from this file.
# Sourced, not run.
PREFIX="${PREFIX:-rounds-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$INFRA_DIR/.." && pwd)"
# Deploy order. Each stack imports exports from the ones before it.
STACKS=(network data edge auth app)

# output <stack> <OutputKey>
output() {
  aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$PREFIX-$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text
}
