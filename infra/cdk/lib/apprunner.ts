import { Stack } from 'aws-cdk-lib'
import * as apprunner from 'aws-cdk-lib/aws-apprunner'
import type * as ecr from 'aws-cdk-lib/aws-ecr'
import * as iam from 'aws-cdk-lib/aws-iam'
import { Construct } from 'constructs'

type Props = {
  name: string
  image: string
  repository: ecr.IRepository
  env: Record<string, string>
  secretArns: Record<string, string>
  command?: string
  healthPath: string
  minSize: number
  maxSize: number
  customDomain?: string
  cpu?: string
  memory?: string
}

/* One App Runner service from the shared API image (Section 13.2). L1 constructs keep us off the alpha package. */
export class AppRunnerService extends Construct {
  readonly name: string
  readonly serviceArn: string
  readonly serviceId: string
  readonly serviceUrl: string

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id)
    const stack = Stack.of(this)
    this.name = props.name

    const accessRole = new iam.Role(this, 'AccessRole', {
      assumedBy: new iam.ServicePrincipal('build.apprunner.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSAppRunnerServicePolicyForECRAccess')],
    })
    const instanceRole = new iam.Role(this, 'InstanceRole', { assumedBy: new iam.ServicePrincipal('tasks.apprunner.amazonaws.com') })
    instanceRole.addToPolicy(new iam.PolicyStatement({ actions: ['ssm:GetParameters', 'ssm:GetParameter'], resources: Object.values(props.secretArns) }))
    instanceRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['kms:Decrypt'],
        resources: ['*'],
        conditions: { StringEquals: { 'kms:ViaService': `ssm.${stack.region}.amazonaws.com` } },
      }),
    )

    const scaling = new apprunner.CfnAutoScalingConfiguration(this, 'Scaling', {
      autoScalingConfigurationName: `${props.name}-asc`.slice(0, 32),
      maxConcurrency: 80,
      minSize: props.minSize,
      maxSize: props.maxSize,
    })

    const service = new apprunner.CfnService(this, 'Service', {
      serviceName: props.name,
      autoScalingConfigurationArn: scaling.attrAutoScalingConfigurationArn,
      sourceConfiguration: {
        autoDeploymentsEnabled: false,
        authenticationConfiguration: { accessRoleArn: accessRole.roleArn },
        imageRepository: {
          imageIdentifier: props.image,
          imageRepositoryType: 'ECR',
          imageConfiguration: {
            port: '8080',
            startCommand: props.command,
            runtimeEnvironmentVariables: Object.entries(props.env).map(([name, value]) => ({ name, value })),
            runtimeEnvironmentSecrets: Object.entries(props.secretArns).map(([name, value]) => ({ name, value })),
          },
        },
      },
      instanceConfiguration: { cpu: props.cpu ?? '1024', memory: props.memory ?? '2048', instanceRoleArn: instanceRole.roleArn },
      healthCheckConfiguration: { protocol: 'HTTP', path: props.healthPath, interval: 10, timeout: 5, healthyThreshold: 1, unhealthyThreshold: 5 },
    })
    service.node.addDependency(accessRole)
    this.serviceArn = service.attrServiceArn
    this.serviceId = service.attrServiceId
    this.serviceUrl = service.attrServiceUrl

    // CloudFormation has no custom domain association resource; the deploy workflow associates it with the CLI
    // (aws apprunner associate-custom-domain) and the runbook lists the validation records.
    void props.customDomain
  }
}
