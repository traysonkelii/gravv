# Runbook

## Environments
- local: Supabase CLI, `make dev`.
- staging: Supabase project `gravv-staging`, App Runner `gravv-api-staging` and `gravv-worker-staging`,
  S3 + CloudFront `staging.gravv.app`. Deploys on every merge to `main` after `ci` succeeds.
- prod: Supabase project `gravv-prod` (Pro, PITR), App Runner `gravv-api` and `gravv-worker`, `app.gravv.app`.
  Deploys on tags `v*` behind the GitHub `production` environment approval.

## First deployment of an environment
1. Create the Supabase project. In Project Settings copy the URL, publishable key, secret key, JWT secret, and the
   pooler (6543) and direct (5432) connection strings.
2. Apply migrations: `supabase db push --db-url "$DB_URL"`. Then `GRAVV_API_PASSWORD=... GRAVV_WORKER_PASSWORD=...
   DB_URL=... infra/scripts/setup_roles.sh staging`.
3. Request an ACM certificate in us-east-1 for the site domain; note its ARN and the Route 53 zone id.
4. Fill the `staging` block in `infra/cdk/cdk.json` (zone id, certificate ARN, Supabase URL, GitHub repo, alert email).
   Create the GitHub OIDC provider in the account once (`aws iam create-open-id-connect-provider --url
   https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com`) and bootstrap CDK once per
   account and region: `cd infra/cdk && pnpm exec cdk bootstrap aws://<account>/us-east-1`.
5. Put secrets in SSM before the first deploy (App Runner refuses to start with a missing parameter):
   `aws ssm put-parameter --name /gravv/staging/DATABASE_URL --type SecureString --value '...' --overwrite` for each of
   DATABASE_URL (pooler, 6543), DATABASE_URL_WORKER (direct, 5432), SUPABASE_SECRET_KEY, SUPABASE_JWT_SECRET,
   APP_ENCRYPTION_KEY, SMTP_PASSWORD. Provider API keys are not server secrets: each workspace enters its own under
   Settings, AI. To offer an operator-wide fallback key, add ANTHROPIC_API_KEY or OPENAI_API_KEY to the `SECRETS` list in
   `infra/cdk/lib/gravv-stack.ts` and to SSM.
6. Push a bootstrap image tag, then `make infra-deploy env=staging tag=<sha>` (or let the workflow do it). The
   log-based alarms need the worker log group, which App Runner creates on first start; if the first deploy fails
   on the metric filters, deploy again once the worker has logged.
7. Associate the API custom domain (`aws apprunner associate-custom-domain`, done by the workflow) and add the
   validation records it prints (`aws apprunner describe-custom-domains`) to Route 53.
8. In GitHub: environment `staging` with secret `AWS_DEPLOY_ROLE_ARN` (stack output `DeployRoleArn`),
   secret `STAGING_DB_URL`, variables `STAGING_SUPABASE_URL`, `STAGING_SUPABASE_PUBLISHABLE_KEY`, `STAGING_SITE_BUCKET`,
   `STAGING_DISTRIBUTION_ID`. Same set with the `PROD_` prefix for production.
9. Push to `main`; `deploy-staging` builds the image, deploys the stack with the new tag, publishes the SPA, and runs
   the smoke test.
10. Configure Supabase Auth: site URL `https://staging.gravv.app`, redirect URLs for `/auth/callback` and `/auth/reset`,
   JWT expiry 900 seconds, minimum password length 12, HaveIBeenPwned check on, TOTP MFA on, custom SMTP (SES).

## Rotating keys
- `APP_ENCRYPTION_KEY`: set `APP_ENCRYPTION_KEY_PREVIOUS` to the old value and `APP_ENCRYPTION_KEY` to the new one in
  SSM, roll the services, then re-save workspace AI keys (or run a rewrap script) so ciphertexts use the new key, then
  remove the previous key. Keys encrypted with a retired key fail with `DecryptError` and the capture shows the
  Settings, AI message.
- Supabase secret key or JWT secret: rotate in the Supabase dashboard, update SSM, roll both App Runner services.
- Database role passwords: `infra/scripts/setup_roles.sh <env>` with new passwords, update SSM, roll the services.

## Re-queuing a dead job
`make jobs-requeue id=<job id>` (or `uv run python -m scripts.requeue_job <id>` in `apps/api`). Check `last_error` first:
`select kind, attempts, last_error from jobs where id = '<id>'`.

## Restoring a backup
Supabase Pro keeps daily backups; prod has PITR. Restore through the dashboard into a new project for inspection,
or in place for a full rollback, then point `DATABASE_URL*` at it and roll the services. Drill quarterly: restore
the latest backup to a scratch project and run `supabase db diff` against migrations; expect no drift.

## Revoking a compromised integration
`update integrations set status = 'disabled', credentials_enc = null where id = '<id>'` as the worker role, then
revoke the grant at the provider. Phase 3 adds a `DELETE /integrations/{provider}` path for the user.

## Scaling
- API: raise `apiMax` in `infra/cdk/cdk.json` (and `maxConcurrency` in `infra/cdk/lib/apprunner.ts`).
- Worker: raise `workerMax` in `infra/cdk/cdk.json`; the claim query is safe with many workers.
- Database: Supabase compute add-ons; keep transactions short; nightly scoring is batched per workspace.

## Alarms
SNS topic `gravv-<env>-alerts` emails on: API 5xx rate above 2 percent for 5 minutes, p95 latency above 1.5 s for
10 minutes, any dead job, queue depth above 200 for 15 minutes, worker instance count below 1. Test the dead-job
alarm by inserting a job with an unknown kind and `max_attempts = 1` in staging.
