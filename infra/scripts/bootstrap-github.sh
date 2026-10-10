#!/usr/bin/env bash
# One-time setup, run from a laptop by someone with IAM rights: creates or updates the
# <PREFIX>-github stack (OIDC provider, deploy role, CloudFormation execution role) and prints
# the role ARN to store as the GitHub secret AWS_DEPLOY_ROLE_ARN.
#
# Environment: GITHUB_REPO (owner/name, default: this checkout's origin), DEPLOY_BRANCH
# (default main), GITHUB_OIDC_SUBJECT_PREFIX (otherwise resolved with gh),
# EXISTING_OIDC_PROVIDER_ARN (if the account already has one), PREFIX, AWS_REGION.
set -euo pipefail
source "$(dirname "$0")/common.sh"

repo="${GITHUB_REPO:-$(git -C "$REPO_DIR" remote get-url origin | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##')}"
# New repositories include immutable owner/repository IDs in the OIDC subject.
# Read GitHub's setting rather than constructing a name-only trust that cannot match it.
subject_prefix="${GITHUB_OIDC_SUBJECT_PREFIX:-}"
if [ -z "$subject_prefix" ]; then
  subject_prefix="$(gh api "repos/$repo/actions/oidc/customization/sub" --jq '
    if .use_default == false then error("Custom OIDC subjects require GITHUB_OIDC_SUBJECT_PREFIX")
    elif .use_immutable_subject == true then
      .sub_claim_prefix // error("GitHub did not return the immutable subject prefix")
    else "" end')"
  subject_prefix="${subject_prefix:-repo:$repo}"
fi
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$PREFIX-github" \
  --template-file "$INFRA_DIR/cloudformation/github.yaml" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    "Prefix=$PREFIX" \
    "GitHubRepo=$repo" \
    "GitHubOidcSubjectPrefix=$subject_prefix" \
    "DeployBranch=${DEPLOY_BRANCH:-main}" \
    "ExistingOidcProviderArn=${EXISTING_OIDC_PROVIDER_ARN:-}"
echo "Deploys allowed from $repo@${DEPLOY_BRANCH:-main}."
echo "Store this as the GitHub secret AWS_DEPLOY_ROLE_ARN: $(output github DeployRoleArn)"
