import { expect, test, type Page } from '@playwright/test'
import { accessToken, latestInviteLink, signIn, signUp, uniqueEmail } from './helpers'

const API = 'http://127.0.0.1:8000/api/v1'

test('new user signs up, completes onboarding, and sees Home', async ({ page }) => {
  const email = uniqueEmail('signup')
  await page.goto('/auth/sign-up')
  await signUp(page, 'Nora Newcomer', email)
  await expect(page).toHaveURL(/\/onboarding/)
  await expect(page.getByRole('heading', { name: 'About you' })).toBeVisible()

  await page.getByLabel('Role').fill('Program Manager')
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByRole('heading', { name: 'What you follow' })).toBeVisible()
  await page.getByRole('button', { name: 'Pinball' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByRole('heading', { name: 'What you want from Gravv' })).toBeVisible()
  await page.getByLabel('Strengthen key relationships').check()
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByRole('heading', { name: 'Connect your tools' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Available soon' }).first()).toBeDisabled()
  await page.getByRole('button', { name: 'Skip for now' }).click()
  await expect(page.getByRole('heading', { name: 'Ready' })).toBeVisible()
  await page.getByRole('button', { name: 'Open Gravv' }).click()

  await expect(page).toHaveURL(/\/app\/home/)
  await expect(
    page.getByRole('heading', { name: /Good (morning|afternoon|evening), Nora\./ }),
  ).toBeVisible()

  // progress persisted server-side: reloading /onboarding bounces back to the app
  await page.goto('/onboarding')
  await expect(page).toHaveURL(/\/app/)
})

async function meridianWorkspaceId(page: Page): Promise<string> {
  const token = await accessToken(page)
  const res = await page.request.get(`${API}/workspaces`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const list = (await res.json()) as { id: string; name: string }[]
  return list.find((w) => w.name === 'Meridian Components')!.id
}

test('owner invites a teammate who accepts from the inbox link, then is departed', async ({
  browser,
  page,
}) => {
  const invitee = uniqueEmail('invitee')
  await signIn(page, 'sarah@demo.gravv.local')
  await page.goto('/app/settings/members')
  await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible()
  await page.getByLabel('Invite by email').fill(invitee)
  await page.getByLabel('Role', { exact: true }).selectOption('member')
  await page.getByRole('button', { name: 'Send invitation' }).click()
  await expect(page.getByText('Invitation sent')).toBeVisible()

  const link = await latestInviteLink(invitee)
  const ctx = await browser.newContext()
  const other = await ctx.newPage()
  await other.goto(link)
  await expect(other.getByRole('heading', { name: 'Join Meridian Components' })).toBeVisible()
  await other.getByRole('link', { name: /Create an account with/ }).click()
  await expect(other.getByLabel('Email')).toHaveValue(invitee)
  await signUp(other, 'Ivan Invitee', invitee)
  await expect(other).toHaveURL(/\/invite\//)
  await other.getByRole('button', { name: 'Accept invitation' }).click()
  await expect(other).toHaveURL(/\/onboarding|\/app/)

  await page.reload()
  const row = page.getByRole('row', { name: new RegExp(invitee) })
  await expect(row).toBeVisible()

  const wsId = await meridianWorkspaceId(page)
  const inviteeToken = await accessToken(other)
  const before = await other.request.get(`${API}/workspaces/${wsId}`, {
    headers: { Authorization: `Bearer ${inviteeToken}` },
  })
  expect(before.status()).toBe(200)

  await row.getByRole('button', { name: 'Mark departed' }).click()
  await page.getByRole('button', { name: 'Mark departed' }).last().click()
  await expect(page.getByText('Member marked departed')).toBeVisible()

  const after = await other.request.get(`${API}/workspaces/${wsId}`, {
    headers: { Authorization: `Bearer ${inviteeToken}` },
  })
  expect(after.status()).toBe(403)
  const me = await other.request.get(`${API}/me`, {
    headers: { Authorization: `Bearer ${inviteeToken}` },
  })
  const memberships = ((await me.json()) as { memberships: { kind: string; status: string }[] })
    .memberships
  expect(memberships.find((m) => m.kind === 'personal')?.status).toBe('active')
  await ctx.close()
})
