#!/usr/bin/env bash
# Create or update CloudFormation stacks in dependency order.
#
#   infra/scripts/deploy-stacks.sh              # all five: network data edge auth app
#   infra/scripts/deploy-stacks.sh auth app     # only these, still in dependency order
#
# Environment: PREFIX (default rounds-dev), AWS_REGION (default us-east-1).
#   data: DB_PASSWORD           auth: COGNITO_DOMAIN_PREFIX, GOOGLE_CLIENT_ID,
#   network: SSH_CIDR                 GOOGLE_CLIENT_SECRET, SES_IDENTITY_ARN, SES_FROM_ADDRESS
#   app: KEY_NAME, INSTANCE_TYPE
# A variable that is unset keeps the stack's current value, so updates (and CI) only need
# DB_PASSWORD and COGNITO_DOMAIN_PREFIX the first time. Set a variable to "" to clear it.
set -euo pipefail
source "$(dirname "$0")/common.sh"

exists() {
  aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$PREFIX-$1" >/dev/null 2>&1
}

# Print Key=value for each variable that is set (even to ""), skipping unset ones.
pass() {
  local key="$1" var="$2"
  if [ -n "${!var+x}" ]; then echo "$key=${!var}"; fi
}

params() {
  echo "Prefix=$PREFIX"
  case "$1" in
    network) pass SshCidr SSH_CIDR ;;
    data) pass DBPassword DB_PASSWORD ;;
    auth)
      pass CognitoDomainPrefix COGNITO_DOMAIN_PREFIX
      pass GoogleClientId GOOGLE_CLIENT_ID
      pass GoogleClientSecret GOOGLE_CLIENT_SECRET
      pass SesIdentityArn SES_IDENTITY_ARN
      pass SesFromAddress SES_FROM_ADDRESS
      ;;
    app)
      pass KeyName KEY_NAME
      pass InstanceType INSTANCE_TYPE
      ;;
  esac
}

wanted=("$@")
[ ${#wanted[@]} -eq 0 ] && wanted=("${STACKS[@]}")
for w in "${wanted[@]}"; do
  [[ " ${STACKS[*]} " == *" $w "* ]] || { echo "unknown stack: $w (expected: ${STACKS[*]})" >&2; exit 1; }
done

# Required values only matter on first create; params() runs in a subshell, so check here.
if [[ " ${wanted[*]} " == *" data "* ]] && ! exists data; then : "${DB_PASSWORD:?set DB_PASSWORD for the first data deploy}"; fi
if [[ " ${wanted[*]} " == *" auth "* ]] && ! exists auth; then : "${COGNITO_DOMAIN_PREFIX:?set COGNITO_DOMAIN_PREFIX for the first auth deploy}"; fi

# Use the CloudFormation execution role from the github stack when it exists.
role_args=()
role_arn="$(output github ExecutionRoleArn 2>/dev/null || true)"
if [ -n "$role_arn" ] && [ "$role_arn" != None ]; then role_args=(--role-arn "$role_arn"); fi

for stack in "${STACKS[@]}"; do
  [[ " ${wanted[*]} " == *" $stack "* ]] || continue
  echo "==> $PREFIX-$stack"
  mapfile -t overrides < <(params "$stack")
  aws cloudformation deploy \
    --region "$AWS_REGION" \
    --stack-name "$PREFIX-$stack" \
    --template-file "$INFRA_DIR/cloudformation/$stack.yaml" \
    --capabilities CAPABILITY_IAM \
    --no-fail-on-empty-changeset \
    "${role_args[@]}" \
    --parameter-overrides "${overrides[@]}"
done
