import { fileURLToPath } from 'node:url'
import { CfnOutput, Duration, RemovalPolicy, Stack, Tags, type StackProps } from 'aws-cdk-lib'
import * as acm from 'aws-cdk-lib/aws-certificatemanager'
import * as budgets from 'aws-cdk-lib/aws-budgets'
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront'
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins'
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch'
import * as actions from 'aws-cdk-lib/aws-cloudwatch-actions'
import * as events from 'aws-cdk-lib/aws-events'
import * as eventTargets from 'aws-cdk-lib/aws-events-targets'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as route53 from 'aws-cdk-lib/aws-route53'
import * as route53Targets from 'aws-cdk-lib/aws-route53-targets'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager'
import * as sns from 'aws-cdk-lib/aws-sns'
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions'
import type { Construct } from 'constructs'

export type EnvConfig = {
  siteDomain: string
  zoneName: string
  zoneId: string
  supabaseUrl: string
  alertEmail: string
  budgetUsd: number
  githubRepo?: string
}

type Props = StackProps & { envName: 'staging' | 'prod'; config: EnvConfig }

const API_DIR = fileURLToPath(new URL('../../../apps/api', import.meta.url))

/* Secrets live in one Secrets Manager secret named gravv/<env>, written out of band (docs/RUNBOOK.md). CloudFormation
   resolves each key at deploy time, so values never enter the template or the repo. Provider API keys are not
   listed: users bring their own keys per workspace (Settings, AI). */
const SECRET_KEYS = ['DATABASE_URL', 'DATABASE_URL_WORKER', 'SUPABASE_SECRET_KEY', 'SUPABASE_JWT_SECRET', 'APP_ENCRYPTION_KEY', 'SMTP_PASSWORD']

/* Runs when the monthly budget is exceeded: stops both functions and the worker schedule (docs/RUNBOOK.md, Cost cap). */
const KILL_SWITCH = `
import os
import boto3

def handler(event, context):
    lam = boto3.client("lambda")
    for name in os.environ["FUNCTIONS"].split(","):
        lam.put_function_concurrency(FunctionName=name, ReservedConcurrentExecutions=0)
    boto3.client("events").disable_rule(Name=os.environ["RULE"])
    print("kill switch engaged; reset per docs/RUNBOOK.md")
`

/* SPA fallback on the site behavior only: extension-less paths load the app shell. Error responses would apply to
   the API behaviors too and turn API 404s into HTML. */
const SPA_REWRITE = "function handler(event) { var r = event.request; if (r.uri.indexOf('.') === -1) { r.uri = '/index.html'; } return r; }"

export class GravvStack extends Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props)
    const { envName, config } = props
    Tags.of(this).add('app', 'gravv')
    Tags.of(this).add('env', envName)
    const siteUrl = `https://${config.siteDomain}`

    const secret = secretsmanager.Secret.fromSecretNameV2(this, 'Secrets', `gravv/${envName}`)
    const environment: Record<string, string> = {
      APP_ENV: envName === 'prod' ? 'production' : 'staging',
      SUPABASE_URL: config.supabaseUrl,
      CORS_ORIGINS: siteUrl,
      WEB_URL: siteUrl,
      LLM_PROVIDER: 'anthropic',
      TRANSCRIPTION_PROVIDER: 'openai',
      LOG_LEVEL: 'INFO',
      SMTP_HOST: `email-smtp.${this.region}.amazonaws.com`,
      SMTP_PORT: '587',
      SMTP_TLS: 'true',
      SMTP_FROM: 'Gravv <no-reply@gravv.app>',
      STORAGE_BUCKET_VOICE: 'voice-notes',
      STORAGE_BUCKET_EXPORTS: 'exports',
      STORAGE_BUCKET_AVATARS: 'avatars',
      // Bumped on secret rotation so CloudFormation re-resolves the dynamic references (make infra-deploy rotated=...).
      SECRETS_ROTATED: (this.node.tryGetContext('rotated') as string | undefined) ?? '',
      ...Object.fromEntries(SECRET_KEYS.map((key) => [key, secret.secretValueFromJson(key).unsafeUnwrap()])),
    }

    // Compute (D-039): two container Lambdas from the one API image, which CDK builds and publishes as an asset.
    const fn = (id: string, handler: string, timeout: Duration) => {
      const logGroup = new logs.LogGroup(this, `${id}Logs`, {
        logGroupName: `/gravv/${envName}/${handler}`,
        retention: envName === 'prod' ? logs.RetentionDays.THREE_MONTHS : logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
      })
      const f = new lambda.DockerImageFunction(this, id, {
        functionName: `gravv-${envName}-${handler}`,
        code: lambda.DockerImageCode.fromImageAsset(API_DIR, { cmd: ['python', '-m', 'awslambdaric', `app.lambda_handlers.${handler}`] }),
        memorySize: 1024,
        timeout,
        environment,
        logGroup,
      })
      return { fn: f, logGroup }
    }
    const api = fn('Api', 'api', Duration.seconds(30))
    const worker = fn('Worker', 'worker', Duration.minutes(5))
    // ponytail: public function URL; the API's own token checks and rate limit guard it. CloudFront OAC would need
    // the SPA to send x-amz-content-sha256 on every request with a body; add that if direct access becomes a concern.
    const apiUrl = api.fn.addFunctionUrl({ authType: lambda.FunctionUrlAuthType.NONE })
    const tick = new events.Rule(this, 'WorkerTick', {
      ruleName: `gravv-${envName}-worker-tick`,
      schedule: events.Schedule.rate(Duration.minutes(1)),
      targets: [new eventTargets.LambdaFunction(worker.fn, { retryAttempts: 0 })],
    })

    // Static site: private bucket, CloudFront with OAC, security headers with CSP, SPA fallback, API under /api.
    const bucket = new s3.Bucket(this, 'SiteBucket', {
      // Deterministic name so the deployer policy (infra/iam) can scope s3:* to gravv-site-*; the account id keeps it unique.
      bucketName: `gravv-site-${envName}-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
    })
    const headers = new cloudfront.ResponseHeadersPolicy(this, 'SecurityHeaders', {
      securityHeadersBehavior: {
        strictTransportSecurity: { accessControlMaxAge: Duration.days(730), includeSubdomains: true, preload: true, override: true },
        contentTypeOptions: { override: true },
        frameOptions: { frameOption: cloudfront.HeadersFrameOption.DENY, override: true },
        referrerPolicy: { referrerPolicy: cloudfront.HeadersReferrerPolicy.NO_REFERRER, override: true },
        contentSecurityPolicy: {
          contentSecurityPolicy: [
            "default-src 'self'",
            `connect-src 'self' ${config.supabaseUrl}`,
            `img-src 'self' data: blob: ${config.supabaseUrl}`,
            `media-src blob: ${config.supabaseUrl}`,
            "font-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "worker-src 'self'",
            "frame-ancestors 'none'",
          ].join('; '),
          override: true,
        },
      },
    })
    const zone = route53.HostedZone.fromHostedZoneAttributes(this, 'Zone', { hostedZoneId: config.zoneId, zoneName: config.zoneName })
    const certificate = new acm.Certificate(this, 'SiteCertificate', {
      domainName: config.siteDomain,
      validation: acm.CertificateValidation.fromDns(zone),
    })
    const spaRewrite = new cloudfront.Function(this, 'SpaRewrite', {
      functionName: `gravv-${envName}-spa-rewrite`,
      runtime: cloudfront.FunctionRuntime.JS_2_0,
      code: cloudfront.FunctionCode.fromInline(SPA_REWRITE),
    })
    const apiBehavior: cloudfront.BehaviorOptions = {
      origin: new origins.FunctionUrlOrigin(apiUrl, { readTimeout: Duration.seconds(60) }),
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    }
    const distribution = new cloudfront.Distribution(this, 'Site', {
      defaultRootObject: 'index.html',
      domainNames: [config.siteDomain],
      certificate,
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        responseHeadersPolicy: headers,
        compress: true,
        functionAssociations: [{ function: spaRewrite, eventType: cloudfront.FunctionEventType.VIEWER_REQUEST }],
      },
      additionalBehaviors: { '/api/*': apiBehavior, '/readyz': apiBehavior },
    })
    const target = route53.RecordTarget.fromAlias(new route53Targets.CloudFrontTarget(distribution))
    new route53.ARecord(this, 'SiteAlias', { zone, recordName: config.siteDomain, target })
    new route53.AaaaRecord(this, 'SiteAliasV6', { zone, recordName: config.siteDomain, target })

    // GitHub Actions deploys through OIDC and the CDK bootstrap roles; no long-lived keys. Optional for a POC
    // deployed from a workstation.
    if (config.githubRepo) {
      const provider = iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(
        this,
        'GitHub',
        `arn:aws:iam::${this.account}:oidc-provider/token.actions.githubusercontent.com`,
      )
      const deployRole = new iam.Role(this, 'DeployRole', {
        roleName: `gravv-${envName}-github-deploy`,
        assumedBy: new iam.WebIdentityPrincipal(provider.openIdConnectProviderArn, {
          StringEquals: { 'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com' },
          StringLike: {
            'token.actions.githubusercontent.com:sub': [
              `repo:${config.githubRepo}:environment:${envName === 'prod' ? 'production' : 'staging'}`,
              `repo:${config.githubRepo}:ref:refs/heads/main`,
              `repo:${config.githubRepo}:ref:refs/tags/v*`,
            ],
          },
        }),
      })
      bucket.grantReadWrite(deployRole)
      bucket.grantDelete(deployRole)
      deployRole.addToPolicy(new iam.PolicyStatement({ actions: ['cloudfront:CreateInvalidation'], resources: [distribution.distributionArn] }))
      deployRole.addToPolicy(
        new iam.PolicyStatement({ actions: ['sts:AssumeRole'], resources: [`arn:aws:iam::${this.account}:role/cdk-*`] }),
      )
      new CfnOutput(this, 'DeployRoleArn', { value: deployRole.roleArn })
    }

    // Alarms (Section 13.7 as amended by D-039).
    const alerts = new sns.Topic(this, 'Alerts', { topicName: `gravv-${envName}-alerts` })
    alerts.addSubscription(new subscriptions.EmailSubscription(config.alertEmail))
    const alarm = (a: cloudwatch.Alarm) => a.addAlarmAction(new actions.SnsAction(alerts))
    alarm(
      new cloudwatch.Alarm(this, 'Site5xx', {
        alarmName: `gravv-${envName}-5xx-rate`,
        metric: distribution.metric5xxErrorRate({ period: Duration.minutes(1) }),
        threshold: 2,
        evaluationPeriods: 5,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      }),
    )
    for (const [id, f] of [
      ['ApiErrors', api.fn],
      ['WorkerErrors', worker.fn],
    ] as const) {
      alarm(
        new cloudwatch.Alarm(this, id, {
          alarmName: `gravv-${envName}-${f.functionName}-errors`,
          metric: f.metricErrors({ period: Duration.minutes(5) }),
          threshold: 1,
          evaluationPeriods: 1,
          treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        }),
      )
    }
    const deadJobs = new logs.MetricFilter(this, 'DeadJobs', {
      logGroup: worker.logGroup,
      filterPattern: logs.FilterPattern.stringValue('$.event', '=', 'job_dead'),
      metricNamespace: `Gravv/${envName}`,
      metricName: 'jobs_dead_total',
      metricValue: '1',
    })
    alarm(
      new cloudwatch.Alarm(this, 'DeadJob', {
        alarmName: `gravv-${envName}-dead-job`,
        metric: deadJobs.metric({ statistic: 'Sum', period: Duration.minutes(5) }),
        threshold: 1,
        evaluationPeriods: 1,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      }),
    )

    // Cost cap: a monthly budget for the whole account. Email at 50 and 80 percent actual and 100 percent forecast;
    // at 100 percent actual the kill switch stops the app until it is reset by hand.
    const killSwitch = new lambda.Function(this, 'KillSwitch', {
      functionName: `gravv-${envName}-kill-switch`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromInline(KILL_SWITCH),
      environment: { FUNCTIONS: `${api.fn.functionName},${worker.fn.functionName}`, RULE: tick.ruleName },
      timeout: Duration.seconds(30),
    })
    killSwitch.addToRolePolicy(new iam.PolicyStatement({ actions: ['lambda:PutFunctionConcurrency'], resources: [api.fn.functionArn, worker.fn.functionArn] }))
    killSwitch.addToRolePolicy(new iam.PolicyStatement({ actions: ['events:DisableRule'], resources: [tick.ruleArn] }))
    const budgetTopic = new sns.Topic(this, 'BudgetTopic', { topicName: `gravv-${envName}-budget` })
    budgetTopic.grantPublish(new iam.ServicePrincipal('budgets.amazonaws.com'))
    budgetTopic.addSubscription(new subscriptions.EmailSubscription(config.alertEmail))
    budgetTopic.addSubscription(new subscriptions.LambdaSubscription(killSwitch))
    const notify = (threshold: number, notificationType: 'ACTUAL' | 'FORECASTED', subscriber: budgets.CfnBudget.SubscriberProperty) => ({
      notification: { notificationType, comparisonOperator: 'GREATER_THAN', threshold, thresholdType: 'PERCENTAGE' },
      subscribers: [subscriber],
    })
    const email = { subscriptionType: 'EMAIL', address: config.alertEmail }
    new budgets.CfnBudget(this, 'Budget', {
      budget: {
        budgetName: `gravv-${envName}-monthly`,
        budgetType: 'COST',
        timeUnit: 'MONTHLY',
        budgetLimit: { amount: config.budgetUsd, unit: 'USD' },
      },
      notificationsWithSubscribers: [
        notify(50, 'ACTUAL', email),
        notify(80, 'ACTUAL', email),
        notify(100, 'FORECASTED', email),
        notify(100, 'ACTUAL', { subscriptionType: 'SNS', address: budgetTopic.topicArn }),
      ],
    })

    new CfnOutput(this, 'SiteUrl', { value: siteUrl })
    new CfnOutput(this, 'ApiFunctionUrl', { value: apiUrl.url })
    new CfnOutput(this, 'SiteBucketName', { value: bucket.bucketName })
    new CfnOutput(this, 'DistributionId', { value: distribution.distributionId })
    new CfnOutput(this, 'SecretName', { value: `gravv/${envName}` })
  }
}
