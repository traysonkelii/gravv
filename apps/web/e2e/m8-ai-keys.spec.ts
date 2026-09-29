import { expect, test } from '@playwright/test'
import { signIn } from './helpers'

test('an owner adds, replaces, and removes a workspace AI key; a member only sees the status', async ({
  browser,
  page,
}) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/settings/ai')
  const anthropic = page.getByRole('region', { name: 'Anthropic' })
  await expect(anthropic.getByText('Not configured')).toBeVisible()
  await anthropic.getByLabel('API key').fill('sk-ant-api03-' + 'q'.repeat(40))
  await anthropic.getByRole('button', { name: 'Save without verifying' }).click()
  await expect(page.getByText('Key saved')).toBeVisible()
  await expect(anthropic.getByText('Configured, ends in qqqq')).toBeVisible()
  await expect(page.getByText('anthropic (workspace key)')).toBeVisible()
  const ctx = await browser.newContext()
  const member = await ctx.newPage()
  await signIn(member, 'priya@demo.gravv.local')
  await member.goto('/app/settings/ai')
  await expect(member.getByText('anthropic (workspace key)')).toBeVisible()
  await expect(member.getByText('Only admins can add or change keys.')).toBeVisible()
  await expect(member.getByRole('button', { name: 'Verify and save key' })).toHaveCount(0)
  await ctx.close()

  await anthropic.getByRole('button', { name: 'Remove key' }).click()
  await expect(page.getByText('Key removed')).toBeVisible()
  await expect(anthropic.getByText('Not configured')).toBeVisible()
})
