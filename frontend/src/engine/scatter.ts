/**
 * Feistel 散布 (PoC)
 *
 * 4-round involutive Feistel cipher on 32-bit。
 * Feistel 网络本身是 involution（self-inverse）—— 再调用一次就解回去。
 * 用作"rank/unrank"散布验证（round-trip + uniformity）。
 *
 * 注：生产布局用 public/layouts/jiapu_v2.npz（Python precompute），scatter 仅作 PoC。
 */
const KEYS: readonly number[] = [0x9e3779b9, 0x243f6a88, 0xb7e15162, 0xc6ef3720]

function roundF(x: number, k: number): number {
  let h = (x ^ k) >>> 0
  h = Math.imul(h, 0x85ebca6b) >>> 0
  h = (h ^ (h >>> 13)) >>> 0
  h = Math.imul(h, 0xc2b2ae35) >>> 0
  h = (h ^ (h >>> 16)) >>> 0
  return h >>> 0
}

export function feistel(x: number): number {
  let lo = x & 0xffff
  let hi = (x >>> 16) & 0xffff
  for (let i = 0; i < KEYS.length; i++) {
    const newLo = hi
    const fhi = roundF(hi, KEYS[i]!)
    hi = (lo ^ (fhi & 0xffff)) & 0xffff
    lo = newLo
  }
  return (((hi & 0xffff) << 16) | (lo & 0xffff)) >>> 0
}

/** Feistel 解密：keys 倒序 + swap 方向反。
 *  feistelInv(feistel(x)) === x for any 32-bit x
 */
export function feistelInv(x: number): number {
  let lo = x & 0xffff
  let hi = (x >>> 16) & 0xffff
  for (let i = KEYS.length - 1; i >= 0; i--) {
    const newLo = (hi ^ (roundF(lo, KEYS[i]!) & 0xffff)) & 0xffff
    const newHi = lo
    lo = newLo
    hi = newHi
  }
  return (((hi & 0xffff) << 16) | (lo & 0xffff)) >>> 0
}

/** 32-bit 散布均匀性粗检：N 个样本分到 16 桶，max bucket ratio < 阈值 */
export function uniformityCheck(samples: number[], buckets = 16, maxRatio = 1.5): boolean {
  const counts = new Array(buckets).fill(0) as number[]
  for (const s of samples) counts[s % buckets]!++
  const expected = samples.length / buckets
  const max = Math.max(...counts)
  return max / expected < maxRatio
}
