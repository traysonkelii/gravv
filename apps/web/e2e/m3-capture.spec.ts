import { expect, test } from '@playwright/test'
import { signIn } from './helpers'

test('text capture from the contact page becomes a fact and a task after review', async ({
  page,
}) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/contacts')
  await page.getByLabel('Search contacts').fill('Johnson')
  await page.getByRole('link', { name: /Michael Johnson/ }).click()
  await expect(page.getByRole('heading', { name: /Michael Johnson/ })).toBeVisible()

  await page.getByRole('button', { name: 'Capture note' }).click()
  const sheet = page.getByRole('dialog')
  await expect(sheet.getByText('Col. Michael Johnson')).toBeVisible()
  await sheet.getByRole('tab', { name: 'Text' }).click()
  const marker = Date.now().toString(36).slice(-4)
  await sheet
    .getByLabel('What happened')
    .fill(
      `Met the Colonel, he loves competitive marble racing ${marker}, remind me to call the program officers next Tuesday`,
    )
  await sheet.getByRole('button', { name: 'Extract note' }).click()

  await expect(page).toHaveURL(/\/app\/captures\//)
  await expect(page.getByRole('heading', { name: 'Review capture' })).toBeVisible({
    timeout: 20_000,
  })
  await expect(
    page.getByRole('checkbox', { name: `Competitive marble racing ${marker}` }),
  ).toBeChecked()
  await expect(page.getByLabel('Task', { exact: true })).toHaveValue('Call the program officers')
  await expect(page.getByText('Matched with')).toBeVisible()
  await page.getByRole('button', { name: /Save to/ }).click()

  await expect(page).toHaveURL(/\/app\/contacts\/00000000-0000-4000-8000-0000000000a1$/)
  await page.getByRole('tab', { name: 'Notes to remember' }).click()
  await expect(page.getByText(`Competitive marble racing ${marker}`)).toBeVisible()
  await expect(page.getByText('note', { exact: true }).first()).toBeVisible()
  await page.getByRole('tab', { name: 'History' }).click()
  await expect(
    page.getByText(/Met the Colonel, he loves competitive marble racing/).first(),
  ).toBeVisible()
})

test('pending captures appear on Home and a failed capture keeps its text', async ({ page }) => {
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/home')
  await page.getByRole('button', { name: 'Capture', exact: true }).first().click()
  const sheet = page.getByRole('dialog')
  await sheet.getByRole('tab', { name: 'Text' }).click()
  await sheet.getByLabel('What happened').fill('Quick note with nobody named.')
  await sheet.getByRole('button', { name: 'Extract note' }).click()
  await expect(page.getByRole('heading', { name: 'Review capture' })).toBeVisible({
    timeout: 20_000,
  })
  await page.goto('/app/home')
  await expect(page.getByRole('heading', { name: 'Pending captures' })).toBeVisible()
  await page.getByRole('link', { name: 'Review' }).first().click()
  await page.getByRole('button', { name: 'Discard' }).click()
  await expect(page).toHaveURL(/\/app\/home/)
})
