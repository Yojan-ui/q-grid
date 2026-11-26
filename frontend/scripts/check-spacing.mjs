// Spacing lint: padding / margin / gap / inset values in src/index.css sit on the 8 px grid, with 4 px half-steps
// (values below 4 px are optical hairline adjustments and allowed). Exit 1 on violations.
//   node scripts/check-spacing.mjs [--fix]
import { readFileSync, writeFileSync } from 'node:fs'
const f = new URL('../src/index.css', import.meta.url)
let css = readFileSync(f, 'utf8')
const prop = /\b(padding(?:-(?:top|right|bottom|left))?|margin(?:-(?:top|right|bottom|left))?|gap|row-gap|column-gap|inset|top|left|right|bottom)\s*:\s*([^;}]+)/g
const bad = []
const snap = v => (v < 4 ? v : Math.max(4, Math.round(v / 4) * 4))
const fixed = css.replace(prop, (all, p, val) => {
  if (/var\(|calc\(|%|auto|max\(|min\(/.test(val) && !/\d+px/.test(val)) return all
  const nv = val.replace(/(-?)(\d+(?:\.\d+)?)px/g, (m, sg, n) => {
    const v = parseFloat(n)
    if (v >= 4 && v % 4 !== 0 && !/^(top|left|right|bottom)$/.test(p)) { bad.push(`${p}: ${val.trim()}`); return `${sg}${snap(v)}px` }
    return m
  })
  return all.replace(val, nv)
})
console.log(`spacing values off the 4 px grid: ${bad.length}`)
bad.slice(0, 80).forEach(b => console.log('  ✗', b))
if (process.argv.includes('--fix')) { writeFileSync(f, fixed); console.log('fixed in place') }
process.exit(bad.length && !process.argv.includes('--fix') ? 1 : 0)
