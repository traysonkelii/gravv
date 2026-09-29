import { expect, test } from '@playwright/test'
import { signIn } from './helpers'

test('Home shows the stat row, due contacts, and insights from seeded data', async ({ page }) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/home')
  await expect(
    page.getByRole('heading', { name: /Good (morning|afternoon|evening), Sarah\./ }),
  ).toBeVisible()
  const main = page.getByRole('main')
  await expect(main.getByText(/^Contacts/)).toBeVisible()
  await expect(main.getByText(/^Average gravity/)).toBeVisible()
  await expect(main.getByText(/^Due this week/)).toBeVisible()
  await expect(main.getByText(/^Pipeline/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Due next' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Insights' })).toBeVisible()
})

test('the at-risk insight for Sarah Martinez offers to create a task', async ({ page }) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/insights')
  // the rule dedupes per ISO week, so an earlier run may already have acted on it
  let card = page.locator('article', { hasText: 'Sarah Martinez needs attention' }).first()
  if (!(await card.isVisible().catch(() => false))) {
    await page.getByRole('button', { name: 'Show all' }).click()
    card = page.locator('article', { hasText: 'Sarah Martinez needs attention' }).first()
  }
  await expect(card).toBeVisible()
  await expect(card.getByText(/last contact \d+ days ago|dropped/)).toBeVisible()
  const create = card.getByRole('button', { name: 'Create task' })
  if (await create.isVisible().catch(() => false)) {
    await create.click()
    await expect(page.getByText('Task created')).toBeVisible()
    await expect(page).toHaveURL(/\/app\/contacts\/00000000-0000-4000-8000-0000000000a3/)
  } else {
    await expect(card.getByText('Acted on')).toBeVisible()
  }
})

test('Analytics shows summary numbers, both charts, and the top relationships table', async ({
  page,
}) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/analytics')
  await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible()
  await page.getByRole('button', { name: 'Quarter' }).click()
  await expect(page.getByText('$5.7M')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Relationships by band' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Interactions over time' })).toBeVisible()
  const table = page.getByRole('table').last()
  await expect(table.getByRole('link', { name: /Emily Rodriguez/ })).toBeVisible()
  // charts use only token colors: every rect fill is a CSS variable or a token hex
  const fills = await page
    .locator('svg rect[fill]')
    .evaluateAll((els) => els.map((e) => e.getAttribute('fill') ?? ''))
  expect(fills.length).toBeGreaterThan(0)
  for (const f of fills)
    expect(f === 'none' || f.startsWith('var(--color-') || f === 'transparent').toBeTruthy()
  // manager sees the team tab
  await page.getByRole('tab', { name: 'Team' }).click()
  await expect(page.getByRole('cell', { name: /Dan Okafor/ })).toBeVisible()
})
