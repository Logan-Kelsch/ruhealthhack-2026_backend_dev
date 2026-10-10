#!/usr/bin/env bash
# Delete every app stack in reverse order, then the /<PREFIX>/ SSM parameters. The media bucket and a final RDS snapshot are left
# behind on purpose; delete them by hand once nobody needs the recordings.
# Environment: PREFIX (default rounds-dev), AWS_REGION (default us-east-1).
set -euo pipefail
source "$(dirname "$0")/common.sh"

read -r -p "Delete all $PREFIX-* stacks in $AWS_REGION? Type the prefix to confirm: " answer
[ "$answer" = "$PREFIX" ] || { echo "aborted"; exit 1; }

# The frontend bucket must be empty before CloudFormation can delete it.
if bucket="$(output edge FrontendBucketName 2>/dev/null)" && [ -n "$bucket" ] && [ "$bucket" != "None" ]; then
  aws s3 rm "s3://$bucket" --recursive
fi

# CloudFormation can't delete an IAM user that still has access keys created outside it.
if user="$(output app LaptopUserName 2>/dev/null)" && [ -n "$user" ] && [ "$user" != "None" ]; then
  for key in $(aws iam list-access-keys --user-name "$user" --query "AccessKeyMetadata[].AccessKeyId" --output text); do
    aws iam delete-access-key --user-name "$user" --access-key-id "$key"
  done
fi

for (( i=${#STACKS[@]}-1; i>=0; i-- )); do
  name="$PREFIX-${STACKS[$i]}"
  echo "==> deleting $name"
  aws cloudformation delete-stack --region "$AWS_REGION" --stack-name "$name"
  aws cloudformation wait stack-delete-complete --region "$AWS_REGION" --stack-name "$name"
done

# The shared .env copy and the deploy marker. They come back on the next CI deploy.
mapfile -t names < <(aws ssm get-parameters-by-path --region "$AWS_REGION" --path "/$PREFIX/" --recursive \
  --query "Parameters[].Name" --output text | tr '\t' '\n' | sed '/^$/d')
if [ ${#names[@]} -gt 0 ]; then
  printf '%s\n' "${names[@]}" | xargs -n 10 aws ssm delete-parameters --region "$AWS_REGION" --names >/dev/null
fi
echo "Done. The $PREFIX-github stack (CI access) is kept; delete it separately if CI is no longer needed."
