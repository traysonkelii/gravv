import { expect, test } from '@playwright/test'

/* Post-deploy smoke: the landing page renders and the sign-in page reaches hosted Supabase. */
const base = process.env.PLAYWRIGHT_BASE_URL ?? ''

test.skip(base === '', 'PLAYWRIGHT_BASE_URL is only set for deployed environments')

test('landing and sign-in respond', async ({ page }) => {
  await page.goto(`${base}/`)
  await expect(
    page.getByRole('heading', { name: 'Know the gravity of your network' }),
  ).toBeVisible()
  await page.goto(`${base}/auth/sign-in`)
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  const health = await page.request.get(
    `${process.env.SMOKE_API_URL ?? base.replace('staging.', 'api-staging.').replace('app.', 'api.')}/readyz`,
  )
  expect(health.status()).toBe(200)
})
