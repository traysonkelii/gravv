import { expect, test } from '@playwright/test'
import { signIn } from './helpers'

test('the seeded network renders, selecting Michael Johnson shows mutual connections, and the path finder reaches NASA', async ({
  page,
}) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/network')
  const canvas = page.getByRole('img', { name: /Network of \d+ contacts/ })
  await expect(canvas).toBeVisible()
  const list = page.getByRole('list', { name: 'Network nodes' })
  await expect(list.getByRole('button', { name: /Col\. Michael Johnson/ })).toBeAttached()
  await expect(list.getByRole('button', { name: /Dr\. James Chen/ })).toBeAttached()
  // the list is visually hidden; a real click would land on the canvas and clear the selection
  await list.getByRole('button', { name: /Col\. Michael Johnson/ }).dispatchEvent('click')
  const panel = page.locator('[aria-label="Selected contact"]')
  await expect(panel.getByRole('heading', { name: 'Col. Michael Johnson' })).toBeVisible()
  await expect(panel.getByText('James Chen')).toBeVisible()
  await expect(panel.getByText('Patricia Williams')).toBeVisible()
  await expect(panel.getByText(/\$2\.5M/)).toBeVisible()

  await page.getByLabel('Find a path to').selectOption('NASA')
  await expect(page.getByText(/Path: Sarah Chen to Dr\. James Chen/)).toBeVisible()

  // keyboard: arrow keys move the selection between nodes
  await canvas.focus()
  await page.keyboard.press('ArrowRight')
  await expect(panel.locator('h2')).not.toHaveText('Col. Michael Johnson')
  await page.getByRole('button', { name: 'Reset view' }).click()
})

test('tasks can be added, snoozed, and completed', async ({ page }) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/tasks')
  const title = `Send the range test plan ${Date.now().toString(36).slice(-4)}`
  await page.getByLabel('New task').fill(title)
  await page.getByRole('button', { name: 'Add task' }).click()
  await expect(page.getByText('Task added')).toBeVisible()
  const row = page.locator('li', { hasText: title }).first()
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Snooze 1 week' }).click()
  await expect(row.getByText(/snoozed until/)).toBeVisible()
  await row.getByRole('checkbox', { name: title }).click()
  await expect(page.getByText('Task completed')).toBeVisible()
  await page.getByRole('tab', { name: 'Done' }).click()
  await expect(page.locator('li', { hasText: title }).first()).toBeVisible()
})

test('a deal can be created, linked to a contact, and shows on the contact', async ({ page }) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/deals')
  await expect(page.getByRole('cell', { name: 'Phase 2 Satellite Program' })).toBeVisible()
  await page.getByRole('button', { name: 'Add deal' }).first().click()
  const name = `Range services ${Date.now().toString(36).slice(-4)}`
  const sheet = page.getByRole('dialog')
  await sheet.getByLabel('Name').fill(name)
  await sheet.getByLabel('Company').fill('U.S. Army')
  await sheet.getByLabel('Value in USD').fill('400000')
  await sheet.getByRole('button', { name: 'Add deal' }).click()
  await expect(page.getByText('Deal added')).toBeVisible()
  await page
    .getByRole('row', { name: new RegExp(name) })
    .getByRole('button', { name: 'Open' })
    .click()
  await page.getByRole('dialog').getByLabel('Link a contact').fill('Stevens')
  await page.getByRole('option', { name: /Robert Stevens/ }).click()
  await page.getByRole('dialog').getByLabel('Role', { exact: true }).selectOption('decision_maker')
  await page.getByRole('dialog').getByRole('button', { name: 'Link contact' }).click()
  await expect(page.getByText('Contact linked')).toBeVisible()
  await page
    .getByRole('dialog')
    .getByRole('link', { name: /Robert Stevens/ })
    .click()
  await page.getByRole('tab', { name: 'Deals' }).click()
  const item = page.locator('li', { hasText: name }).first()
  await expect(item).toBeVisible()
  await expect(item.getByText('decision maker')).toBeVisible()
  await expect(item.getByText('$400K')).toBeVisible()
})
