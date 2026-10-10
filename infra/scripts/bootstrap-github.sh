#!/usr/bin/env bash
# One-time setup, run from a laptop by someone with IAM rights: creates or updates the
# <PREFIX>-github stack (OIDC provider, deploy role, CloudFormation execution role) and prints
# the role ARN to store as the GitHub secret AWS_DEPLOY_ROLE_ARN.
#
# Environment: GITHUB_REPO (owner/name, default: this checkout's origin), DEPLOY_BRANCH
# (default main), EXISTING_OIDC_PROVIDER_ARN (if the account already has one), PREFIX, AWS_REGION.
set -euo pipefail
source "$(dirname "$0")/common.sh"

repo="${GITHUB_REPO:-$(git -C "$REPO_DIR" remote get-url origin | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##')}"
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$PREFIX-github" \
  --template-file "$INFRA_DIR/cloudformation/github.yaml" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    "Prefix=$PREFIX" \
    "GitHubRepo=$repo" \
    "DeployBranch=${DEPLOY_BRANCH:-main}" \
    "ExistingOidcProviderArn=${EXISTING_OIDC_PROVIDER_ARN:-}"
echo "Deploys allowed from $repo@${DEPLOY_BRANCH:-main}."
echo "Store this as the GitHub secret AWS_DEPLOY_ROLE_ARN: $(output github DeployRoleArn)"
