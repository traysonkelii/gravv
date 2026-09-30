# Runbook

## Environments
- local: Supabase CLI, `make dev`.
- prod: Supabase project `gravv-prod` (free tier for the POC), Lambda `gravv-prod-api` and `gravv-prod-worker`,
  S3 + CloudFront at `gravv.keliiconsulting.com`. Deployed from a workstation with `make infra-deploy env=prod`
  and `make site-publish env=prod`; the `deploy-prod` workflow does the same on tags `v*` once GitHub OIDC is set up.
- staging: same shape at `staging.gravv.app`, defined in `infra/cdk/cdk.json` and not deployed for the POC.

The API is a container Lambda behind a function URL, reached through the site's CloudFront distribution under
`/api/*` and `/readyz`. The worker is a second Lambda from the same image, invoked every minute by the EventBridge
rule `gravv-<env>-worker-tick`; each run drains the queue and returns (D-039).

## First deployment of an environment
Prerequisites on the workstation: AWS CLI with a profile that carries `infra/iam/gravv-deployer-policy.json`
(`export AWS_PROFILE=gravv`), Docker, pnpm, the Supabase CLI logged in.

1. Root-only account settings, once: in Billing, activate IAM user and role access to billing information (the
   budget cannot be created without it) and enable Cost Explorer.
2. Create the Supabase project. In Project Settings copy the URL, publishable key, secret key, and the transaction
   pooler connection string (port 6543). Both functions use the pooler: Lambda has no IPv6 egress and the worker no
   longer needs a session-mode connection. The JWT secret is only needed if the project issues HS256 tokens.
3. Apply migrations and set the application role passwords:
   `supabase db push --db-url "$DB_URL"`, then
   `GRAVV_API_PASSWORD=... GRAVV_WORKER_PASSWORD=... DB_URL=... infra/scripts/setup_roles.sh prod`.
   Without a local `psql`, run the same two `alter role` statements through the local stack's container:
   `docker exec -i supabase_db_gravv psql "$DB_URL" -c ...` (use the session pooler URL, port 5432, from Docker).
   Pooler usernames carry the project ref: `gravv_api.<ref>` and `gravv_worker.<ref>`.
4. DNS: create the hosted zone for the site domain
   (`aws route53 create-hosted-zone --name gravv.keliiconsulting.com --caller-reference "$(date +%s)"`) and add
   its four NS records at the parent domain's registrar as the `gravv` subdomain. Certificate validation waits on
   this delegation, so confirm `dig NS gravv.keliiconsulting.com` answers before deploying. Put the zone id in
   `infra/cdk/cdk.json`.
5. Bootstrap CDK once per account and region: `cd infra/cdk && pnpm exec cdk bootstrap aws://<account>/us-east-1`.
6. Write the secret before the first deploy (CloudFormation resolves it into the functions' environment):
   `aws secretsmanager create-secret --name gravv/prod --secret-string file://secret.json` where the file holds
   `DATABASE_URL`, `DATABASE_URL_WORKER` (both `postgresql+asyncpg://` through the pooler), `SUPABASE_SECRET_KEY`,
   `SUPABASE_JWT_SECRET` (may be empty), `APP_ENCRYPTION_KEY` (32 random bytes, base64), `SMTP_PASSWORD` (may be
   empty; app email is off until SES is configured). Delete the file afterwards. Provider API keys are not server
   secrets: each workspace enters its own under Settings, AI.
7. Fill the `prod` block in `infra/cdk/cdk.json`: zone id, Supabase URL, alert email, budget. Leave `githubRepo`
   unset until the GitHub OIDC provider exists in the account.
8. `make infra-deploy env=prod`. CDK builds the API image with Docker, pushes it to the bootstrap repository, and
   creates the stack. Confirm the two SNS subscription emails (alerts and budget) when they arrive.
9. Create `.env.production` at the repo root with `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, and
   `VITE_API_URL=https://gravv.keliiconsulting.com` (same origin as the site). Then `make site-publish env=prod`.
10. Configure Supabase Auth: site URL `https://gravv.keliiconsulting.com`, redirect URLs for `/auth/callback` and
    `/auth/reset`, JWT expiry 900 seconds, minimum password length 12, TOTP MFA on. The HaveIBeenPwned check
    needs the Pro plan; turn it on when the project is upgraded. All of this is one Management API call:
    `PATCH https://api.supabase.com/v1/projects/<ref>/config/auth` with the access token from `supabase login`.
    Custom SMTP is optional for one user; the built-in mailer is rate limited to a few messages an hour.
11. Smoke test: `PLAYWRIGHT_BASE_URL=https://gravv.keliiconsulting.com SMOKE_API_URL=$PLAYWRIGHT_BASE_URL
    pnpm exec playwright test e2e/smoke.spec.ts` in `apps/web`, then sign up, enter an Anthropic key under
    Settings, AI, capture a note, and watch it get processed within about a minute.

## Deploying a change
- API or worker: `make infra-deploy env=prod` (migrations first: `supabase db push --db-url "$DB_URL"`).
- Web: `make site-publish env=prod`.
- Logs: `aws logs tail /gravv/prod/api --follow` and `aws logs tail /gravv/prod/worker --follow`.

## Cost cap and kill switch
The stack creates an AWS Budget for the whole account (`budgetUsd` in `cdk.json`). Email goes out at 50 and 80
percent of actual spend and at 100 percent of forecast spend. At 100 percent of actual spend the budget publishes to
`gravv-<env>-budget`, and the `gravv-<env>-kill-switch` function sets the reserved concurrency of the api and
worker functions to zero and disables the worker rule. The site keeps serving static files; every API call fails
until the switch is reset. Budgets evaluate a few times a day, so a burst can overshoot the cap by hours of usage.

Reset after investigating:
```
aws lambda delete-function-concurrency --function-name gravv-prod-api
aws lambda delete-function-concurrency --function-name gravv-prod-worker
aws events enable-rule --name gravv-prod-worker-tick
```
Cost Explorer (Billing console) is the dashboard; every resource carries the tags `app=gravv` and `env=<env>`.

## Rotating keys
- `APP_ENCRYPTION_KEY`: put the old value in `APP_ENCRYPTION_KEY_PREVIOUS` and the new one in `APP_ENCRYPTION_KEY`
  in the secret (`aws secretsmanager put-secret-value --secret-id gravv/prod --secret-string file://secret.json`),
  redeploy with `make infra-deploy env=prod rotated=$(date +%s)` so CloudFormation re-resolves the values, re-save
  workspace AI keys (or run a rewrap script), then remove the previous key. Keys encrypted with a retired key fail
  with `DecryptError` and the capture shows the Settings, AI message.
- Supabase secret key or JWT secret: rotate in the Supabase dashboard, update the secret, redeploy with `rotated=`.
- Database role passwords: `infra/scripts/setup_roles.sh <env>` with new passwords, update the secret, redeploy.

## Re-queuing a dead job
`DATABASE_URL_WORKER=<pooler url> make jobs-requeue id=<job id>` (the variable overrides the local `.env`). Check
`last_error` first: `select kind, attempts, last_error from jobs where id = '<id>'`.

## Restoring a backup
Supabase Pro keeps daily backups; prod has PITR once upgraded. Restore through the dashboard into a new project for
inspection, or in place for a full rollback, then point `DATABASE_URL*` in the secret at it and redeploy. Drill
quarterly: restore the latest backup to a scratch project and run `supabase db diff` against migrations; expect no
drift.

## Revoking a compromised integration
`update integrations set status = 'disabled', credentials_enc = null where id = '<id>'` as the worker role, then
revoke the grant at the provider. Phase 3 adds a `DELETE /integrations/{provider}` path for the user.

## Scaling
- API: Lambda scales per request; raise `memorySize` or `timeout` in `infra/cdk/lib/gravv-stack.ts` if needed.
- Worker: shorten the rule rate or raise the function timeout; overlapping runs are safe because claims use
  `skip locked`. Move back to a long-running worker (App Runner or Fargate) when job latency of a minute is too slow.
- Database: Supabase compute add-ons; keep transactions short; nightly scoring is batched per workspace.

## Alarms
SNS topic `gravv-<env>-alerts` emails on: CloudFront 5xx rate above 2 percent for 5 minutes, any api or worker
function error in a 5 minute window, any dead job. Test the dead-job alarm by inserting a job with an unknown kind
and `max_attempts = 1`.
