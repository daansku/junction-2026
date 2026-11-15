/**
 * Tick values for a log axis that never crowd: 1-2-5 steps, thinned to 1-3, then to powers of ten,
 * until at most `maxCount` fit. Plot draws every log tick when tickFormat is a function, so
 * charts pass these explicitly.
 */
export function logTicks(min: number, max: number, maxCount: number): number[] {
  if (!(min > 0) || !(max > min)) return []
  const lo = Math.floor(Math.log10(min))
  const hi = Math.ceil(Math.log10(max))
  for (const steps of [[1, 2, 5], [1, 3], [1]]) {
    const out: number[] = []
    for (let k = lo; k <= hi; k++) for (const s of steps) {
      const v = s * 10 ** k
      if (v >= min && v <= max) out.push(v)
    }
    if (out.length <= Math.max(2, maxCount)) return out
  }
  // very wide ranges: every other power of ten
  const out: number[] = []
  for (let k = lo; k <= hi; k += 2) if (10 ** k >= min && 10 ** k <= max) out.push(10 ** k)
  return out
}
