// Derived numbers (a formula over loaded data, e.g. a sum or a share) are registered here with their reason, so the
// numbers test (scripts/check-numbers.mjs) can tell them from hard-coded figures. No effect on what is displayed.
type W = Window & { __qgDerived?: { v: number; why: string }[] }
export function reg(v: number, why: string): number {
  if (typeof window !== 'undefined' && Number.isFinite(v)) {
    const w = window as W
    const a = (w.__qgDerived ||= [])
    if (a.length < 5000) a.push({ v, why })
  }
  return v
}

/** Register every number quoted inside a text that came from a replay file (e.g. problem_points[i].text), so the
 *  numbers test knows the figure was loaded, not typed into the UI. Returns the text unchanged. */
export function regText(t: string | null | undefined, why: string): string {
  const s = t ?? ''
  for (const m of s.matchAll(/[−-]?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|[−-]?\d+(?:\.\d+)?/g)) reg(parseFloat(m[0].replace(/,/g, '').replace('−', '-')), why)
  return s
}
