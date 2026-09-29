// Lighthouse budgets (Section 9.8): performance >= 85 on mobile, accessibility >= 95, on the public pages.
// Usage: node scripts/lighthouse.mjs http://127.0.0.1:4173   (after `pnpm build && pnpm preview`)
import { launch } from 'chrome-launcher'
import lighthouse from 'lighthouse'

const base = process.argv[2] ?? 'http://127.0.0.1:4173'
const pages = ['/', '/auth/sign-in']
const budgets = { performance: 0.85, accessibility: 0.95 }
const chrome = await launch({
  chromeFlags: ['--headless=new', '--no-sandbox'],
  chromePath: process.env.CHROME_PATH,
})
let failed = false
try {
  for (const path of pages) {
    const result = await lighthouse(base + path, {
      port: chrome.port,
      output: 'json',
      onlyCategories: Object.keys(budgets),
      formFactor: 'mobile',
      screenEmulation: {
        mobile: true,
        width: 390,
        height: 844,
        deviceScaleFactor: 3,
        disabled: false,
      },
    })
    const scores = Object.fromEntries(
      Object.entries(result.lhr.categories).map(([k, v]) => [k, v.score]),
    )
    const line = Object.entries(scores)
      .map(([k, v]) => `${k}=${Math.round((v ?? 0) * 100)}`)
      .join(' ')
    const ok = Object.entries(budgets).every(([k, min]) => (scores[k] ?? 0) >= min)
    console.log(`${ok ? 'PASS' : 'FAIL'} ${path} ${line}`)
    if (!ok) {
      failed = true
      const audits = Object.values(result.lhr.audits)
        .filter((a) => a.details?.type === 'opportunity' && (a.numericValue ?? 0) > 100)
        .sort((a, b) => (b.numericValue ?? 0) - (a.numericValue ?? 0))
        .slice(0, 5)
      for (const a of audits) console.log(`  ${a.id}: ${Math.round(a.numericValue ?? 0)} ms`)
      for (const id of [
        'largest-contentful-paint',
        'total-blocking-time',
        'speed-index',
        'first-contentful-paint',
      ])
        console.log(`  ${id}: ${result.lhr.audits[id]?.displayValue ?? ''}`)
    }
  }
} finally {
  await chrome.kill()
}
process.exit(failed ? 1 : 0)
