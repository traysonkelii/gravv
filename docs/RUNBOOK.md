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
4. `cp infra/terraform/envs/staging/terraform.tfvars.example infra/terraform/envs/staging/terraform.tfvars` and fill it in.
   Create the state bucket `gravv-tfstate` once. `make infra-plan env=staging`, then `make infra-apply env=staging`.
5. Put secrets in SSM (names printed by `terraform output`):
   `aws ssm put-parameter --name /gravv/staging/DATABASE_URL --type SecureString --value '...' --overwrite` for each of
   DATABASE_URL (pooler, 6543), DATABASE_URL_WORKER (direct, 5432), SUPABASE_SECRET_KEY, SUPABASE_JWT_SECRET,
   APP_ENCRYPTION_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, SMTP_PASSWORD.
6. Add the App Runner custom domain validation records from `terraform output api_domain_validation` to Route 53.
7. In GitHub: environment `staging` with secret `AWS_DEPLOY_ROLE_ARN` (from `terraform output deploy_role_arn`),
   secret `STAGING_DB_URL`, variables `STAGING_SUPABASE_URL`, `STAGING_SUPABASE_PUBLISHABLE_KEY`, `STAGING_SITE_BUCKET`,
   `STAGING_DISTRIBUTION_ID`. Same set with the `PROD_` prefix for production.
8. Push to `main`; `deploy-staging` builds the image, rolls the services, publishes the SPA, and runs the smoke test.
9. Configure Supabase Auth: site URL `https://staging.gravv.app`, redirect URLs for `/auth/callback` and `/auth/reset`,
   JWT expiry 900 seconds, minimum password length 12, HaveIBeenPwned check on, TOTP MFA on, custom SMTP (SES).

## Rotating keys
- `APP_ENCRYPTION_KEY`: set `APP_ENCRYPTION_KEY_PREVIOUS` to the old value and `APP_ENCRYPTION_KEY` to the new one, roll
  the services, run `uv run python -m scripts.rewrap_credentials` (Phase 3, when integrations land), then remove the
  previous key.
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
- API: raise `max_size` and `max_concurrency` in `infra/terraform/modules/apprunner` inputs for the env.
- Worker: raise `max_size` for the worker service; the claim query is safe with many workers.
- Database: Supabase compute add-ons; keep transactions short; nightly scoring is batched per workspace.

## Alarms
SNS topic `gravv-<env>-alerts` emails on: API 5xx rate above 2 percent for 5 minutes, p95 latency above 1.5 s for
10 minutes, any dead job, queue depth above 200 for 15 minutes, worker instance count below 1. Test the dead-job
alarm by inserting a job with an unknown kind and `max_attempts = 1` in staging.
