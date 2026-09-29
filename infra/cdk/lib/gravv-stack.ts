import { CfnOutput, Duration, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib'
import * as acm from 'aws-cdk-lib/aws-certificatemanager'
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront'
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins'
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch'
import * as actions from 'aws-cdk-lib/aws-cloudwatch-actions'
import * as ecr from 'aws-cdk-lib/aws-ecr'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as route53 from 'aws-cdk-lib/aws-route53'
import * as targets from 'aws-cdk-lib/aws-route53-targets'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as sns from 'aws-cdk-lib/aws-sns'
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions'
import type { Construct } from 'constructs'
import { AppRunnerService } from './apprunner.js'

export type EnvConfig = {
  siteDomain: string
  apiDomain: string
  zoneName: string
  zoneId: string
  certificateArn: string
  supabaseUrl: string
  githubRepo: string
  alertEmail: string
  workerMax: number
  apiMax: number
}

type Props = StackProps & { envName: 'staging' | 'prod'; config: EnvConfig; imageTag: string }

/* Secrets live in SSM SecureString parameters written out of band (docs/RUNBOOK.md). Only names are declared.
   Provider API keys are not listed: users bring their own keys per workspace (Settings, AI). */
const SECRETS = ['DATABASE_URL', 'DATABASE_URL_WORKER', 'SUPABASE_SECRET_KEY', 'SUPABASE_JWT_SECRET', 'APP_ENCRYPTION_KEY', 'SMTP_PASSWORD']

export class GravvStack extends Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props)
    const { envName, config, imageTag } = props
    const suffix = envName === 'prod' ? '' : '-staging'

    const repo = new ecr.Repository(this, 'ApiRepository', {
      repositoryName: `gravv-api${suffix}`,
      imageTagMutability: ecr.TagMutability.IMMUTABLE,
      imageScanOnPush: true,
      lifecycleRules: [{ maxImageCount: 30 }],
      removalPolicy: RemovalPolicy.RETAIN,
    })
    const image = `${repo.repositoryUri}:${imageTag}`

    const secretArns = Object.fromEntries(
      SECRETS.map((name) => [name, this.formatArn({ service: 'ssm', resource: 'parameter', resourceName: `gravv/${envName}/${name}` })]),
    )
    const commonEnv: Record<string, string> = {
      APP_ENV: envName === 'prod' ? 'production' : 'staging',
      SUPABASE_URL: config.supabaseUrl,
      CORS_ORIGINS: `https://${config.siteDomain}`,
      WEB_URL: `https://${config.siteDomain}`,
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
    }

    const api = new AppRunnerService(this, 'Api', {
      name: `gravv-api${suffix}`,
      image,
      repository: repo,
      env: commonEnv,
      secretArns,
      healthPath: '/readyz',
      minSize: 1,
      maxSize: config.apiMax,
      customDomain: config.apiDomain,
    })
    const worker = new AppRunnerService(this, 'Worker', {
      name: `gravv-worker${suffix}`,
      image,
      repository: repo,
      env: commonEnv,
      secretArns,
      command: 'python -m app.worker',
      healthPath: '/healthz',
      minSize: 1,
      maxSize: config.workerMax,
    })

    // Static site: private bucket, CloudFront with OAC, security headers with CSP, SPA fallback.
    const bucket = new s3.Bucket(this, 'SiteBucket', {
      bucketName: `gravv-site-${envName}`,
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
            `connect-src 'self' https://${config.apiDomain} ${config.supabaseUrl}`,
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
    const certificate = acm.Certificate.fromCertificateArn(this, 'SiteCertificate', config.certificateArn)
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
      },
      errorResponses: [
        { httpStatus: 403, responseHttpStatus: 200, responsePagePath: '/index.html', ttl: Duration.seconds(0) },
        { httpStatus: 404, responseHttpStatus: 200, responsePagePath: '/index.html', ttl: Duration.seconds(0) },
      ],
    })
    const zone = route53.HostedZone.fromHostedZoneAttributes(this, 'Zone', { hostedZoneId: config.zoneId, zoneName: config.zoneName })
    new route53.ARecord(this, 'SiteAlias', {
      zone,
      recordName: config.siteDomain,
      target: route53.RecordTarget.fromAlias(new targets.CloudFrontTarget(distribution)),
    })

    // GitHub Actions deploys through OIDC and the CDK bootstrap roles; no long-lived keys.
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
    repo.grantPullPush(deployRole)
    bucket.grantReadWrite(deployRole)
    bucket.grantDelete(deployRole)
    deployRole.addToPolicy(new iam.PolicyStatement({ actions: ['cloudfront:CreateInvalidation'], resources: [distribution.distributionArn] }))
    deployRole.addToPolicy(
      new iam.PolicyStatement({ actions: ['sts:AssumeRole'], resources: [`arn:aws:iam::${this.account}:role/cdk-*`] }),
    )

    // Alarms (Section 13.7).
    const topic = new sns.Topic(this, 'Alerts', { topicName: `gravv-${envName}-alerts` })
    topic.addSubscription(new subscriptions.EmailSubscription(config.alertEmail))
    const alarm = (a: cloudwatch.Alarm) => a.addAlarmAction(new actions.SnsAction(topic))
    const apiDims = { ServiceName: api.name, ServiceID: api.serviceId }
    const errors = new cloudwatch.Metric({ namespace: 'AWS/AppRunner', metricName: '5xxStatusResponses', dimensionsMap: apiDims, statistic: 'Sum', period: Duration.minutes(1) })
    const requests = new cloudwatch.Metric({ namespace: 'AWS/AppRunner', metricName: 'Requests', dimensionsMap: apiDims, statistic: 'Sum', period: Duration.minutes(1) })
    alarm(
      new cloudwatch.Alarm(this, 'Api5xx', {
        alarmName: `gravv-${envName}-api-5xx-rate`,
        metric: new cloudwatch.MathExpression({ expression: '100 * errors / MAX([requests, 1])', usingMetrics: { errors, requests }, period: Duration.minutes(1) }),
        threshold: 2,
        evaluationPeriods: 5,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      }),
    )
    alarm(
      new cloudwatch.Alarm(this, 'ApiLatency', {
        alarmName: `gravv-${envName}-api-p95-latency`,
        metric: new cloudwatch.Metric({ namespace: 'AWS/AppRunner', metricName: 'RequestLatency', dimensionsMap: apiDims, statistic: 'p95', period: Duration.minutes(1) }),
        threshold: 1500,
        evaluationPeriods: 10,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      }),
    )
    // Custom metrics from structured log lines. App Runner creates the log group on first start, so this part of the
    // stack applies on the second deploy (docs/RUNBOOK.md).
    const workerLogs = logs.LogGroup.fromLogGroupName(this, 'WorkerLogs', `/aws/apprunner/${worker.name}/${worker.serviceId}/application`)
    const deadJobs = new logs.MetricFilter(this, 'DeadJobs', {
      logGroup: workerLogs,
      filterPattern: logs.FilterPattern.stringValue('$.event', '=', 'job_dead'),
      metricNamespace: `Gravv/${envName}`,
      metricName: 'jobs_dead_total',
      metricValue: '1',
    })
    const queueDepth = new logs.MetricFilter(this, 'QueueDepth', {
      logGroup: workerLogs,
      filterPattern: logs.FilterPattern.stringValue('$.event', '=', 'jobs_queue_depth'),
      metricNamespace: `Gravv/${envName}`,
      metricName: 'jobs_queue_depth',
      metricValue: '$.jobs_queue_depth',
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
    alarm(
      new cloudwatch.Alarm(this, 'QueueDepthHigh', {
        alarmName: `gravv-${envName}-queue-depth`,
        metric: queueDepth.metric({ statistic: 'Maximum', period: Duration.minutes(1) }),
        threshold: 200,
        evaluationPeriods: 15,
        treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      }),
    )
    alarm(
      new cloudwatch.Alarm(this, 'WorkerUnhealthy', {
        alarmName: `gravv-${envName}-worker-unhealthy`,
        metric: new cloudwatch.Metric({ namespace: 'AWS/AppRunner', metricName: 'ActiveInstances', dimensionsMap: { ServiceName: worker.name, ServiceID: worker.serviceId }, statistic: 'Minimum', period: Duration.minutes(1) }),
        threshold: 1,
        evaluationPeriods: 3,
        comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
        treatMissingData: cloudwatch.TreatMissingData.BREACHING,
      }),
    )

    new CfnOutput(this, 'ApiUrl', { value: api.serviceUrl })
    new CfnOutput(this, 'EcrRepositoryUri', { value: repo.repositoryUri })
    new CfnOutput(this, 'SiteBucketName', { value: bucket.bucketName })
    new CfnOutput(this, 'DistributionId', { value: distribution.distributionId })
    new CfnOutput(this, 'DeployRoleArn', { value: deployRole.roleArn })
    new CfnOutput(this, 'SecretParameterPrefix', { value: `/gravv/${envName}/` })
  }
}
