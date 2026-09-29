// Greps apps/web/src for the forbidden list in the build plan (Section 10.7). Exit 1 on any hit.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const root = new URL('../src', import.meta.url).pathname
const allowlist = new Set(['design/tokens.css', 'design/fonts.css'])
const rules = [
  {
    name: 'border radius',
    re: /rounded-(?!none\b)[a-z0-9-]+|border-radius\s*:\s*(?!0(px)?\s*[;}])/,
  },
  {
    name: 'shadow outside tokens',
    re: /shadow-(?!plate\b|plate-raised\b|pressed\b|none\b)[a-z0-9-]+|box-shadow\s*:/,
  },
  { name: 'backdrop filter', re: /backdrop-(filter|blur)|blur-[a-z0-9]+/ },
  { name: 'gradient', re: /gradient/ },
  { name: 'hex color outside tokens', re: /#[0-9a-fA-F]{3,8}\b(?![^<]*>)/ },
  { name: 'arbitrary value', re: /\b[a-z-]+-\[[^\]]+\]/ },
  {
    name: 'forbidden hue',
    re: /\b(bg|text|border|from|to|via|fill|stroke|ring|outline)-(purple|blue|cyan|green|yellow|indigo|violet|sky|teal|emerald|lime|amber|fuchsia|pink|rose|orange|red)-/,
  },
  { name: 'uppercase', re: /\buppercase\b|text-transform\s*:\s*uppercase/ },
  {
    name: 'positive letter spacing',
    re: /tracking-(wide|wider|widest)|letter-spacing\s*:\s*0?\.[1-9]/,
  },
  { name: 'monospace font', re: /font-mono\b|monospace/ },
  { name: 'unicode arrow', re: /[←-⇿⟰-⟿]/ },
  { name: 'emoji', re: /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F2FF}\u{FE0F}]/u },
  { name: 'entrance animation', re: /fade-in|slide-up|animate-(bounce|pulse|ping|spin)/ },
  { name: 'hover transform', re: /hover:(scale|-?translate|rotate)-/ },
]

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (/\.(tsx?|css|html)$/.test(entry) && !/schema\.d\.ts$|openapi\.json$/.test(entry))
      out.push(p)
  }
  return out
}

let hits = 0
for (const file of walk(root)) {
  const rel = relative(root, file)
  if (allowlist.has(rel)) continue
  const lines = readFileSync(file, 'utf8').split('\n')
  lines.forEach((line, i) => {
    for (const rule of rules) {
      if (rule.re.test(line)) {
        console.log(`${rel}:${i + 1}: ${rule.name}: ${line.trim().slice(0, 100)}`)
        hits++
      }
    }
  })
}
if (hits) {
  console.log(`design lint: ${hits} hit(s)`)
  process.exit(1)
}
console.log('design lint: clean')
