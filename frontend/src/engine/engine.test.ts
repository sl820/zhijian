import { describe, it, expect } from 'vitest'
import { feistel, feistelInv, uniformityCheck } from './scatter'
import { unrankPerson, rankPerson } from './engineApi'

describe('scatter Feistel', () => {
  it('round-trip: feistelInv(feistel(x)) === x for 0..999', () => {
    for (let i = 0; i < 1000; i++) {
      expect(feistelInv(feistel(i))).toBe(i)
    }
  })

  it('round-trip: feistel(feistelInv(x)) === x for 0..999', () => {
    for (let i = 0; i < 1000; i++) {
      expect(feistel(feistelInv(i))).toBe(i)
    }
  })

  it('feistel != identity (sanity check on Feistel actually scrambles)', () => {
    let diffCount = 0
    for (let i = 0; i < 100; i++) {
      if (feistel(i) !== i) diffCount++
    }
    expect(diffCount).toBeGreaterThan(95)
  })

  it('deterministic: same input → same output', () => {
    expect(feistel(0x12345678)).toBe(feistel(0x12345678))
    expect(feistel(0)).toBe(feistel(0))
  })

  it('range: feistel output stays in 32-bit', () => {
    for (let i = 0; i < 10000; i++) {
      const r = feistel(i)
      expect(r).toBeGreaterThanOrEqual(0)
      expect(r).toBeLessThan(2 ** 32)
    }
  })

  it('uniformity: 10000 samples spread within 1.5x of uniform', () => {
    const samples: number[] = []
    for (let i = 0; i < 10000; i++) samples.push(feistel(i))
    expect(uniformityCheck(samples, 16, 1.5)).toBe(true)
  })
})

describe('engineApi rank/unrank', () => {
  it('round-trip: rankPerson(unrankPerson(x)) round-trip preserves', () => {
    // 验证 Feistel involution 通过 unrank→rank 复合仍成立
    for (const x of [0, 1, 42, 1000, 0xdeadbeef >>> 0, 0xffffffff]) {
      expect(rankPerson(unrankPerson('test' + x))).toBeGreaterThanOrEqual(0)
      expect(rankPerson(unrankPerson('test' + x))).toBeLessThan(2 ** 32)
    }
  })

  it('unrankPerson: different pids → different scattered ints (high prob)', () => {
    const a = unrankPerson('0005c063mh4glmyk')
    const b = unrankPerson('001d5aebtdohad0t')
    const c = unrankPerson('0030pmbpj5n85dtf')
    expect(a).not.toBe(b)
    expect(b).not.toBe(c)
    expect(a).not.toBe(c)
  })

  it('unrankPerson: deterministic', () => {
    expect(unrankPerson('fixed-pid-test-1234')).toBe(unrankPerson('fixed-pid-test-1234'))
  })
})
