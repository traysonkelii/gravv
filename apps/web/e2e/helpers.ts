import { expect, type Page } from '@playwright/test'

export const DEMO_PASSWORD = 'demo-password-1'
export const MAILPIT = 'http://127.0.0.1:54324'

export function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}@test.gravv.local`
}

export async function signIn(page: Page, email: string, password = DEMO_PASSWORD): Promise<void> {
  await page.goto('/auth/sign-in')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/app|\/onboarding|\/invite/)
}

export async function signUp(
  page: Page,
  name: string,
  email: string,
  password = 'e2e-password-123',
): Promise<void> {
  await page.getByLabel('Full name').fill(name)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
}

export async function latestInviteLink(to: string): Promise<string> {
  for (let attempt = 0; attempt < 20; attempt++) {
    const res = await fetch(
      `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${to}`)}&limit=1`,
    )
    const body = (await res.json()) as { messages: { ID: string }[] }
    const id = body.messages[0]?.ID
    if (id) {
      const msg = (await (await fetch(`${MAILPIT}/api/v1/message/${id}`)).json()) as {
        Text: string
      }
      const match = msg.Text.match(/http:\/\/\S+\/invite\/[A-Za-z0-9_-]+/)
      if (match) return match[0]
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error(`no invitation email for ${to}`)
}

/* Reads the Supabase access token the SPA keeps in localStorage, for direct API assertions. */
export async function accessToken(page: Page): Promise<string> {
  return page.evaluate(() => {
    const key = Object.keys(localStorage).find(
      (k) => k.startsWith('sb-') && k.endsWith('-auth-token'),
    )
    if (!key) throw new Error('no session')
    return (JSON.parse(localStorage.getItem(key)!) as { access_token: string }).access_token
  })
}
