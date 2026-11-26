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
