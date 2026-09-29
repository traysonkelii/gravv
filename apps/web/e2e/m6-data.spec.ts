import { expect, test } from '@playwright/test'
import { signIn } from './helpers'

test('a member exports their personal workspace and gets a download link', async ({ page }) => {
  await signIn(page, 'priya@demo.gravv.local')
  await page.goto('/app/settings/data')
  await page.getByRole('button', { name: 'Export my personal workspace' }).click()
  await expect(page.getByText('Export started')).toBeVisible()
  const row = page.locator('li', { hasText: /^personal/ }).first()
  await expect(row.getByRole('link', { name: 'Download' })).toBeVisible({ timeout: 30_000 })
  const href = await row.getByRole('link', { name: 'Download' }).getAttribute('href')
  expect(href).toMatch(/\/storage\/v1\/object\/sign\/exports\//)
  const res = await page.request.get(href!)
  expect(res.status()).toBe(200)
  expect(res.headers()['content-type']).toContain('zip')
})

test('the member analytics page has no team tab and the manager has one', async ({
  browser,
  page,
}) => {
  await signIn(page, 'priya@demo.gravv.local')
  await page.goto('/app/analytics')
  await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Team' })).toHaveCount(0)
  const ctx = await browser.newContext()
  const manager = await ctx.newPage()
  await signIn(manager, 'dan@demo.gravv.local')
  await manager.goto('/app/analytics')
  await manager.getByRole('tab', { name: 'Team' }).click()
  await expect(manager.getByRole('cell', { name: /Priya Nair/ })).toBeVisible()
  await ctx.close()
})
