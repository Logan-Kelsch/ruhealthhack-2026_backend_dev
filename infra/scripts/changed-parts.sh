#!/usr/bin/env bash
# Decide what CI must deploy for the commits between the last deployed commit and HEAD.
# Writes key=value lines to $GITHUB_OUTPUT in CI, or prints them locally:
#   stacks=<space-separated stacks CI may update>  frontend=true|false  backend=true|false
#
#   infra/scripts/changed-parts.sh <base-sha|""> [head-sha]
# An empty or unknown base means "deploy everything".
set -euo pipefail
source "$(dirname "$0")/common.sh"
out="${GITHUB_OUTPUT:-/dev/stdout}"

base="${1:-}" head="${2:-HEAD}"
# CI never updates the data stack (RDS); see infra/README.md.
ci_stacks=(network edge auth app)

if [ -z "$base" ] || ! git -C "$REPO_DIR" cat-file -e "$base^{commit}" 2>/dev/null; then
  printf 'stacks=%s\nfrontend=true\nbackend=true\n' "${ci_stacks[*]}" >>"$out"
  exit 0
fi

files="$(git -C "$REPO_DIR" diff --name-only "$base" "$head")"
stacks=()
for s in "${ci_stacks[@]}"; do
  grep -qx "infra/cloudformation/$s.yaml" <<<"$files" && stacks+=("$s")
done
frontend=false backend=false
grep -q '^frontend/' <<<"$files" && frontend=true
# A new app stack can replace the instance, which then needs the code again.
grep -qE '^(backend/|infra/scripts/server-deploy\.sh$|infra/cloudformation/app\.yaml$)' <<<"$files" && backend=true
if grep -qx infra/cloudformation/data.yaml <<<"$files"; then
  echo "::warning::infra/cloudformation/data.yaml changed; CI does not deploy it. Run infra/scripts/deploy-stacks.sh data."
fi

printf 'stacks=%s\nfrontend=%s\nbackend=%s\n' "${stacks[*]}" "$frontend" "$backend" >>"$out"
