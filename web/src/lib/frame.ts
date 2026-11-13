import type { Frame } from './types'

export const FRAME_SIZE = 64

/** Decode wire frame (64 hex rows) into a flat Uint8Array of palette indices. */
export function decodeFrame(frame: Frame | null | undefined): Uint8Array {
  const out = new Uint8Array(FRAME_SIZE * FRAME_SIZE)
  if (!frame) return out
  for (let y = 0; y < FRAME_SIZE; y++) {
    const row = frame[y] ?? ''
    for (let x = 0; x < FRAME_SIZE; x++) {
      const v = parseInt(row[x] ?? '0', 16)
      out[y * FRAME_SIZE + x] = Number.isNaN(v) ? 0 : v
    }
  }
  return out
}

/** Encode a flat index array into wire format. */
export function encodeFrame(cells: ArrayLike<number>): Frame {
  const rows: string[] = []
  for (let y = 0; y < FRAME_SIZE; y++) {
    let r = ''
    for (let x = 0; x < FRAME_SIZE; x++) r += (cells[y * FRAME_SIZE + x] & 15).toString(16)
    rows.push(r)
  }
  return rows
}

/** Cheap equality for change detection (e.g. no-op actions in replay). */
export function framesEqual(a: Frame | undefined, b: Frame | undefined): boolean {
  if (!a || !b || a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
  return true
}
