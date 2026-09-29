import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { signIn, uniqueEmail } from './helpers'

test('create a contact, add a fact and a meeting note, see them on the timeline', async ({
  page,
}) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/contacts')
  await expect(page.getByRole('heading', { name: 'Contacts' })).toBeVisible()
  await page.getByLabel('Search contacts').fill('Johnson')
  await expect(page.getByRole('link', { name: /Michael Johnson/ })).toBeVisible()

  const last = `Park${Date.now().toString(36).slice(-5)}`
  await page.getByRole('button', { name: 'Add contact' }).first().click()
  await expect(page).toHaveURL(/\/app\/contacts\/new/)
  await page.getByLabel('Honorific').fill('Maj.')
  await page.getByLabel('First name').fill('Lisa')
  await page.getByLabel('Last name').fill(last)
  await page.getByLabel('Title').fill('Program Officer')
  await page.getByLabel('Company').fill('Space Force')
  await page.getByLabel('Emails').fill(`lisa.${last.toLowerCase()}@spaceforce.mil`)
  await page.getByLabel('Relationship').selectOption('government')
  await page.getByRole('button', { name: 'Add contact' }).click()
  await expect(page).toHaveURL(/\/app\/contacts\/[0-9a-f-]{36}$/)
  await expect(page.getByRole('heading', { name: `Maj. Lisa ${last}` })).toBeVisible()
  await expect(page.locator('main header').getByText('Space Force, Program Officer')).toBeVisible()
  await expect(page.getByRole('meter')).toHaveAttribute('aria-valuenow', '0')

  await page.getByRole('tab', { name: 'Notes to remember' }).click()
  await page.getByLabel('Category').selectOption('interest')
  await page.getByLabel('Something to remember').fill('Runs the Peterson test range')
  await page.getByRole('button', { name: 'Remember this' }).click()
  await expect(page.getByText('Runs the Peterson test range')).toBeVisible()
  await expect(page.getByText('manual', { exact: true })).toBeVisible()

  await page.getByRole('tab', { name: 'History' }).click()
  await page.getByRole('button', { name: 'Add note' }).click()
  await page.getByLabel('Kind', { exact: true }).selectOption('meeting')
  await page.getByLabel('Subject').fill('Test plan kickoff')
  await page
    .getByLabel('What happened')
    .fill('Walked through the integration test plan. She wants weekly status.')
  await page.getByRole('button', { name: 'Save note' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  await expect(page.getByText('Test plan kickoff')).toBeVisible()
  await expect(
    page.getByText('Walked through the integration test plan. She wants weekly status.'),
  ).toBeVisible()

  await page.getByRole('tab', { name: 'Overview' }).click()
  await expect(page.getByText(/meeting, just now|meeting, \d+m ago/)).toBeVisible()
})

test('a private contact is invisible to a teammate', async ({ browser, page }) => {
  const last = `Private${Date.now().toString(36).slice(-5)}`
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/contacts/new')
  await page.getByLabel('First name').fill('Quiet')
  await page.getByLabel('Last name').fill(last)
  await page.getByLabel('Visibility').selectOption('private')
  await page.getByRole('button', { name: 'Add contact' }).click()
  await expect(page.getByRole('heading', { name: `Quiet ${last}` })).toBeVisible()
  const url = page.url()

  const ctx = await browser.newContext()
  const other = await ctx.newPage()
  await signIn(other, 'priya@demo.gravv.local')
  await other.goto('/app/contacts')
  await other.getByLabel('Search contacts').fill(last)
  await expect(other.getByText('No contacts yet')).toBeVisible()
  await other.goto(url)
  await expect(other).toHaveURL(/\/app\/contacts$/)
  await ctx.close()
  void uniqueEmail
})

test('contact detail has no serious accessibility violations', async ({ page }) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/contacts')
  await page.getByLabel('Search contacts').fill('Johnson')
  await page.getByRole('link', { name: /Michael Johnson/ }).click()
  await expect(page.getByRole('heading', { name: /Michael Johnson/ })).toBeVisible()
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  const serious = results.violations.filter(
    (v) => v.impact === 'serious' || v.impact === 'critical',
  )
  expect(
    serious,
    JSON.stringify(
      serious.map((v) => ({ id: v.id, nodes: v.nodes.length })),
      null,
      2,
    ),
  ).toEqual([])
})
