import { App } from 'aws-cdk-lib'
import { GravvStack, type EnvConfig } from '../lib/gravv-stack.js'

const app = new App()
const envName = (app.node.tryGetContext('env') as string | undefined) ?? 'staging'
const config = app.node.tryGetContext(envName) as EnvConfig | undefined
if (!config) throw new Error(`no context for env "${envName}" in cdk.json`)

new GravvStack(app, `gravv-${envName}`, {
  envName: envName === 'prod' ? 'prod' : 'staging',
  config,
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'us-east-1' },
  description: `Gravv ${envName}: Lambda api and worker, S3 and CloudFront site, budget, alarms`,
})
