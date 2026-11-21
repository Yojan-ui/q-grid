// In-browser QAOA statevector + exhaustive search for small QUBOs (n <= 14). Same circuit as the Python
// reference (|+>^n, exp(-i gamma H_C), RX(2 beta) mixer), qubit i = bit i (little-endian).
// QAOA simulated classically in the browser: verified against exact solutions, no quantum advantage claimed.
export type Qubo = { M: number[][]; c?: number }

export function energies(q: Qubo): Float64Array {
  const n = q.M.length, N = 1 << n, E = new Float64Array(N)
  for (let z = 0; z < N; z++) {
    let e = q.c ?? 0
    for (let i = 0; i < n; i++) {
      if (!((z >> i) & 1)) continue
      e += q.M[i][i]
      for (let j = i + 1; j < n; j++) if ((z >> j) & 1) e += 2 * q.M[i][j]
    }
    E[z] = e
  }
  return E
}

export function isingNormalised(q: Qubo, E: Float64Array) {
  const n = q.M.length
  let c = q.c ?? 0, s2 = 0
  const h = new Array(n).fill(0)
  for (let i = 0; i < n; i++) { c += q.M[i][i] / 2; h[i] -= q.M[i][i] / 2 }
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
    const m = q.M[i][j]; c += m / 2; h[i] -= m / 2; h[j] -= m / 2; s2 += (m / 2) ** 2
  }
  for (const v of h) s2 += v * v
  const sigma = Math.sqrt(s2) || 1
  const En = new Float64Array(E.length)
  for (let z = 0; z < E.length; z++) En[z] = (E[z] - c) / sigma
  return En
}

/** Probabilities after each QAOA layer (layer 0 = uniform). */
export function qaoaLayers(En: Float64Array, gammas: number[], betas: number[]): Float64Array[] {
  const N = En.length, n = Math.round(Math.log2(N))
  let re = new Float64Array(N).fill(1 / Math.sqrt(N)), im = new Float64Array(N)
  const out: Float64Array[] = [probs(re, im)]
  for (let k = 0; k < gammas.length; k++) {
    for (let z = 0; z < N; z++) {
      const a = -gammas[k] * En[z], c = Math.cos(a), s = Math.sin(a)
      const r = re[z] * c - im[z] * s, i2 = re[z] * s + im[z] * c
      re[z] = r; im[z] = i2
    }
    const cb = Math.cos(betas[k]), sb = Math.sin(betas[k])
    for (let q = 0; q < n; q++) {
      const bit = 1 << q
      for (let z = 0; z < N; z++) {
        if (z & bit) continue
        const z1 = z | bit
        const r0 = re[z], i0 = im[z], r1 = re[z1], i1 = im[z1]
        // [[c, -i s], [-i s, c]]
        re[z] = cb * r0 + sb * i1; im[z] = cb * i0 - sb * r1
        re[z1] = sb * i0 + cb * r1; im[z1] = -sb * r0 + cb * i1
      }
    }
    out.push(probs(re, im))
  }
  return out
}

function probs(re: Float64Array, im: Float64Array) {
  const p = new Float64Array(re.length)
  for (let z = 0; z < re.length; z++) p[z] = re[z] * re[z] + im[z] * im[z]
  return p
}

export function bits(z: number, n: number) {
  let s = ''
  for (let i = 0; i < n; i++) s += (z >> i) & 1
  return s
}

/** Deterministic sampler (mulberry32) so the badge is reproducible. */
export function sample(p: Float64Array, shots: number, seed = 1234): number[] {
  let a = seed >>> 0
  const rnd = () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296 }
  const cdf = new Float64Array(p.length); let acc = 0
  for (let i = 0; i < p.length; i++) { acc += p[i]; cdf[i] = acc }
  const out: number[] = []
  for (let s = 0; s < shots; s++) {
    const r = rnd() * acc
    let lo = 0, hi = p.length - 1
    while (lo < hi) { const m = (lo + hi) >> 1; if (cdf[m] < r) lo = m + 1; else hi = m }
    out.push(lo)
  }
  return out
}
