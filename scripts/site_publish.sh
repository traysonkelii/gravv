#!/usr/bin/env bash
# Builds the SPA and publishes it to one environment's bucket and CloudFront, reading the stack outputs.
# Usage: scripts/site_publish.sh prod    (VITE_* values come from .env.production at the repo root)
set -euo pipefail
cd "$(dirname "$0")/.."
env_name="${1:?usage: site_publish.sh <env>}"
out() { aws cloudformation describe-stacks --stack-name "gravv-$env_name" --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
bucket=$(out SiteBucketName); dist=$(out DistributionId); site=$(out SiteUrl)
(cd apps/web && pnpm build)
aws s3 sync apps/web/dist "s3://$bucket" --delete --exclude index.html --exclude "*.webmanifest" --exclude sw.js --cache-control "public, max-age=31536000, immutable"
aws s3 cp apps/web/dist/index.html "s3://$bucket/index.html" --cache-control "no-cache"
for f in sw.js manifest.webmanifest; do [[ -f "apps/web/dist/$f" ]] && aws s3 cp "apps/web/dist/$f" "s3://$bucket/$f" --cache-control "no-cache"; done
aws cloudfront create-invalidation --distribution-id "$dist" --paths "/index.html" "/" "/sw.js" "/manifest.webmanifest" >/dev/null
echo "published $site"
