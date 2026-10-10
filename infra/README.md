# Infrastructure

Five CloudFormation stacks hold the cloud environment (PRD P-04). Each one imports values exported by the stacks before it, so they deploy in this order and delete in reverse:

| Stack (`$PREFIX-<name>`) | Template | Holds | Why it's separate |
|---|---|---|---|
| network | `cloudformation/network.yaml` | VPC, subnets, security groups, Elastic IP | Everything else attaches to it. The Elastic IP lives here so the CloudFront origin exists before the instance does. |
| data | `cloudformation/data.yaml` | RDS Postgres, media bucket | Stateful. Compute and sign-in can change without touching it. |
| edge | `cloudformation/edge.yaml` | Frontend bucket, CloudFront | Needs the Elastic IP's hostname. |
| auth | `cloudformation/auth.yaml` | Cognito user pool, groups, client | Needs the CloudFront domain for callback URLs. |
| app | `cloudformation/app.yaml` | EC2 instance, IAM role, Elastic IP association | Needs the subnet, media bucket and user pool. Safe to replace. |

A sixth stack, `$PREFIX-github` (`cloudformation/github.yaml`), gives GitHub Actions access to AWS. It is deployed by hand and CI cannot change it.

Scripts in `scripts/` read settings from the environment (`PREFIX`, default `rounds-dev`; `AWS_REGION`, default `us-east-1`):

- `deploy-stacks.sh [stack ...]`: create or update stacks in order (all five when no names are given).
- `deploy-frontend.sh`: build `frontend/`, upload it, invalidate `index.html`.
- `outputs.sh`: print every stack's outputs.
- `deploy-backend.sh [sha]`: deploy a pushed commit to the instance through SSM Run Command.
- `push-app-env.sh` (CI only): store the shared `.env` (GitHub secret `APP_ENV`) in SSM for the instance.
- `changed-parts.sh`: decide what CI deploys.
- `bootstrap-github.sh`: one-time setup of GitHub's access to AWS.
- `db-allow-me.sh`: let your current IP reach RDS.
- `teardown.sh`: empty the frontend bucket, delete the stacks in reverse order and remove the SSM parameters (asks first).

```
Browser ──HTTPS──▶ CloudFront ─┬─ /*           ──▶ S3 (React build, private, origin access control)
                               ├─ /portraits/* ──▶ EC2 :8000 (FastAPI static files, cached)
                               └─ /api/*      ──▶ EC2 :8000 (FastAPI, HTTP + WebSocket)
                                                │
  laptops (team IPs) ─▶ RDS Postgres ◀───┤──▶ Bedrock, S3 media bucket
                                                └──▶ ElevenLabs / Tavus (internet)
Cognito user pool (managed login) ── tokens ──▶ browser ──▶ /api/*
```

FastAPI serves `/portraits/<filename>` from `backend/app/data/portraits/`. CloudFront routes
`/portraits/*` to the existing backend origin with the managed `CachingOptimized` policy and
no frontend rewrite function. Changes to `cloudformation/edge.yaml` deploy through CI; to
update only the edge stack from a laptop, run `infra/scripts/deploy-stacks.sh edge`.

## What's in it and why

| Piece | Choice | Reason |
|---|---|---|
| Network | VPC, 2 public subnets, **no NAT gateway** | A NAT gateway alone is ~$32/month. EC2 is public but its security group only admits CloudFront's origin-facing prefix list. |
| API | `t3.small`, Amazon Linux 2023, Elastic IP, IMDSv2 only | Heavy work runs in Bedrock and ElevenLabs. The Elastic IP keeps the CloudFront origin stable across stop/start. |
| HTTPS | CloudFront in front of both S3 and EC2 | One origin for the browser (no CORS, secure context for the microphone) without an ALB (~$16+/month) or a domain. |
| Database | RDS Postgres 17, `db.t4g.micro` (the largest class AWS free plan accounts allow), single-AZ, 20 GB gp3, encrypted, TLS required | Publicly addressable so laptops share the one database, but only the backend and single team IPs (added by `db-allow-me.sh`) can connect. Final snapshot on delete. |
| Media | Private S3 bucket, versioned, retained on delete | Encounter audio and case images (`S3_BUCKET`). |
| Sign-in | Cognito, Essentials tier, `faculty` and `student` groups | Email + password always; Google if a client ID is given; email one-time codes if an SES identity is given. |
| Access | SSM Session Manager, optional SSH | SSH opens only when `SSH_CIDR` is set. |

Not included yet: Route 53 and ACM (no domain). Add them when the team has one.

**Rough cost (us-east-1, on-demand):** EC2 ~$15, RDS ~$24, storage and IPv4 ~$6, CloudFront and Cognito ~$0 at demo volume. About **$45/month** before Bedrock and ElevenLabs usage, so tear down after the event.

## First deploy (once, from a laptop)

Prerequisites: AWS CLI v2 signed in as your own IAM user (`aws login` or `AWS_PROFILE`), `jq`, and Bedrock model access in the region.

```bash
export PREFIX=rounds-dev AWS_REGION=us-east-1
```

1. Give GitHub access to AWS. This creates the GitHub OIDC provider, a deploy role that only `main` of this repository can assume, and the CloudFormation execution role. It prints the deploy role ARN.

   ```bash
   infra/scripts/bootstrap-github.sh
   ```

2. Create the five stacks. `DB_PASSWORD` and `COGNITO_DOMAIN_PREFIX` are needed only this first time; CloudFormation keeps them for later updates.

   ```bash
   export DB_PASSWORD="$(openssl rand -hex 16)" COGNITO_DOMAIN_PREFIX=rounds-dev-<something-unique>
   ```
   ```bash
   infra/scripts/deploy-stacks.sh
   ```

   This takes about 15–20 minutes (RDS and CloudFront are the slow parts). Keep `DB_PASSWORD`; it goes into `DATABASE_URL` in the shared `.env`.

3. Write the shared `.env` (start from `.env.example`). Fill in:
   - `DATABASE_URL`: the data stack's `DatabaseUrlTemplate` output with the real password;
   - `S3_BUCKET`: the data stack's `MediaBucketName` output;
   - `CORS_ORIGINS`: `http://localhost:5173,<edge stack SiteUrl>`, so one file works on laptops and on the server;
   - `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: a key for the shared laptop user (below);
   - API keys (ElevenLabs, Tavus) and model IDs.

   Create the laptop key once (the user name is the app stack's `LaptopUserName` output):

   ```bash
   aws iam create-access-key --user-name "$(aws cloudformation describe-stacks --stack-name "$PREFIX-app" --query "Stacks[0].Outputs[?OutputKey=='LaptopUserName'].OutputValue" --output text)"
   ```

   Share the file with the team yourselves (a shared password-manager item is tidiest). Leave `AWS_PROFILE` empty.

4. In GitHub, under **Settings → Secrets and variables → Actions** (the repository owner or an admin must do this):

   | Kind | Name | Value |
   |---|---|---|
   | Secret | `AWS_DEPLOY_ROLE_ARN` | printed by step 1 |
   | Secret | `APP_ENV` | the whole shared `.env`, pasted as-is |
   | Variable | `DEPLOY_ENABLED` | `true` (turns the deploy job on) |
   | Variable (optional) | `PREFIX`, `AWS_REGION` | only if not `rounds-dev` / `us-east-1` |

5. Run the **Deploy** workflow from the Actions tab with "Deploy every part" ticked, or push to `main`.

Optional sign-in methods, set before `infra/scripts/deploy-stacks.sh auth`:
- **Google:** create an OAuth client (Web application) in Google Cloud Console. Add the auth stack output `GoogleRedirectUri` as an authorized redirect URI, then set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
- **Email one-time codes:** verify an email identity in Amazon SES in the same region, then set `SES_IDENTITY_ARN` and `SES_FROM_ADDRESS`. While SES is in sandbox mode it only delivers to verified addresses.

## Continuous deployment

`.github/workflows/deploy.yml` runs on every push to `main`:

1. **Test:** backend `pytest`, `cfn-lint`, and the frontend type check and build (once `frontend/` exists). A failure stops the deploy.
2. **Sign in:** `aws-actions/configure-aws-credentials` exchanges GitHub's OIDC token for one-hour credentials for the deploy role. No AWS keys are stored in GitHub.
3. **Work out what changed** since the commit in the SSM parameter `/$PREFIX/deployed-sha`. Diffing against the last deployed commit, rather than the previous push, means a deploy that failed or was skipped is picked up by the next one.
4. **Store the shared `.env`:** the `APP_ENV` secret is written to SSM Parameter Store as the SecureString `/$PREFIX/app-env`. If it changed, the backend is redeployed even when no code changed.
5. **Deploy what changed:**
   - `infra/cloudformation/{network,edge,auth,app}.yaml` → those stacks;
   - `frontend/**` → build, S3 upload, CloudFront invalidation;
   - `backend/**`, `app.yaml` or `server-deploy.sh` → the backend.
6. **Record** the commit in `/$PREFIX/deployed-sha`.

Only one deploy runs at a time. After changing the `APP_ENV` secret, run the workflow by hand (secret changes don't trigger a run); it notices the change and redeploys the backend. Tick "Deploy every part" to redeploy everything.

**What CI cannot do:** update the data stack (RDS and the media bucket) or the github stack. The deploy role's policy denies both, so a bad push can't replace the database or widen CI's own access. When `data.yaml` changes, the run shows a warning; deploy it from a laptop:

```bash
infra/scripts/deploy-stacks.sh data
```

**How the backend is deployed:** `deploy-backend.sh` sends an SSM Run Command to the instance. The instance checks out the commit from GitHub (the repository is public), then `server-deploy.sh`:
- writes `/opt/app/.env` from `/$PREFIX/app-env`, dropping any `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` or `AWS_PROFILE` lines so the instance always uses its own role;
- runs `uv sync` and `alembic upgrade head`;
- restarts the `rounds-api` systemd service;
- waits for `/api/health`.

The command carries only the commit, repository URL, prefix and region; the `.env` contents never appear in SSM command history.

Watch the service or get a shell:

```bash
aws ssm start-session --target "$(aws cloudformation describe-stacks --stack-name "$PREFIX-app" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text)"
```
```bash
sudo journalctl -u rounds-api -f
```

## Local development

1. Get the shared `.env` from the team and save it as `.env` in the repo root. It carries the shared laptop AWS key, so Bedrock and the media bucket work with no AWS setup.
2. Let your laptop reach the database (see below).

**About the laptop key.** It belongs to the IAM user `LaptopUser` in the app stack. That user has one policy, `AppPermissions`, which is the same policy the server's role uses: Bedrock model calls, the media bucket, and reading and grouping Cognito users. Nothing else, so a leaked key can't create resources, touch IAM or run up EC2 bills.
- **Never commit `.env`.** It's git-ignored, and GitHub push protection should block AWS keys, but the repo is public, so check `git status` before `git add .`.
- **If the key leaks** (or AWS emails about it), delete it with `aws iam delete-access-key`, create a new one, and re-share the `.env` and the `APP_ENV` secret.
- **After the event,** delete the key. `teardown.sh` does this automatically.
- **New AWS service in the app?** Add it to `AppPermissions` in `cloudformation/app.yaml`; the server and laptops both get it on the next deploy.

When anyone changes a key, update the shared copy and the `APP_ENV` secret together, then run the Deploy workflow by hand.

## The database

There is one database, `rounds`, used by both the deployed app and every laptop, so everyone sees the same cases and encounters. Things to keep in mind:

- **Migrations are shared.** Running `alembic upgrade head` from a branch changes the database for the live app too. Only add migrations that are safe for `main`'s code, and keep them moving forward.
- **Test data shows up in the demo.** Clean up anything you create by hand before the event.
- **Backups:** RDS keeps one day of automatic backups, and deleting the data stack takes a final snapshot.

RDS only accepts connections from the backend and from team IPs. Add your current IP, and again whenever your network changes (event Wi-Fi, hotspot, home):

```bash
infra/scripts/db-allow-me.sh
```

This replaces your previous rule, so you only ever have one. Remove it when you're done with `db-allow-me.sh --remove`.

## Tear down

```bash
infra/scripts/teardown.sh
```

This leaves two things behind on purpose: the media bucket and a final RDS snapshot. Delete both by hand once nobody needs the recordings. Set `DEPLOY_ENABLED` to `false` first, or every push to `main` will fail at the deploy step.

## Validate changes

Every pull request and push to `main` runs two checks in the `infra-checks` job. A deploy only runs if both pass.

1. **cfn-lint:** templates are valid CloudFormation (resource types, property names and types, references).
2. **CloudFormation Guard** (`guard/rules.guard`): templates keep the security choices recorded in their `must` metadata. For example:
   - buckets are encrypted, private and TLS-only;
   - RDS is encrypted and snapshotted on delete;
   - no security group allows ingress from `0.0.0.0/0`;
   - instances require IMDSv2;
   - no IAM statement allows `*`, and no admin-level AWS policies are attached;
   - `AppPermissions` (shared with laptops) stays limited to application services;
   - the GitHub role is pinned to one repo and branch;
   - CloudFront is HTTPS-only.

Run both locally before pushing. Get cfn-guard from its [releases page](https://github.com/aws-cloudformation/cloudformation-guard/releases); CI uses 3.2.1.

```bash
uvx cfn-lint infra/cloudformation/*.yaml
```
```bash
cfn-guard validate --data infra/cloudformation --rules infra/guard --show-summary fail
```

If a rule blocks a change you really want, change the rule in the same pull request and say why. Don't work around it in the template.
