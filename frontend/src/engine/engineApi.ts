/**
 * 4 稳定接口 #2: engine API
 *
 * pullAt       — 三种 pull 模式（家谱版）
 * unrankPerson — pid → scattered 32-bit integer
 * rankPerson   — scattered integer → un-scattered integer
 *
 * 注意：unrank/rank 是 Feistel 散布对的"编码/解码"语义，不是 PID ↔ Int 互转。
 * 验证：rankPerson(unrankPerson(x)) === x for any 32-bit x（Feistel involution）。
 */
import type { Person } from '@/types/person'
import { feistel } from './scatter'
import { personPosition } from '@/data/position'

export type PullMode = 'random-line' | 'name-rule' | 'common-char'

export interface PullParams {
  count: number
  rules?: 'eldest' | 'no-same-surname'
}

/**
 * 三种 pull 模式（家谱版）：
 * - random-line:  N^代数 笛卡尔积 → N 代人随机抽样
 * - name-rule:    谱例约束（嫡长子继承 / 不娶同姓）
 * - common-char:  按谱中真出现过的字过滤
 */
export async function pullAt(mode: PullMode, params: PullParams): Promise<Person[]> {
  // PoC 阶段：mode 解析 + 简单实现，Phase D 接入完整版
  if (params.count <= 0) return []
  if (mode === 'random-line') {
    return pullRandomLine(params.count)
  }
  if (mode === 'name-rule' && params.rules) {
    return pullByRule(params.count, params.rules)
  }
  if (mode === 'common-char') {
    return pullCommonChar(params.count)
  }
  return []
}

async function pullRandomLine(count: number): Promise<Person[]> {
  // 简化：取 layout 中前 count 个有朝代 person
  const out: Person[] = []
  for (let i = 0; i < count * 10 && out.length < count; i++) {
    // 实际需 loadPerson(pid) → 但这里要避免 fetch loop
    // 暂用 pid 合成占位
    if (out.length >= count) break
  }
  return out
}

async function pullByRule(count: number, _rule: string): Promise<Person[]> {
  return []
}

async function pullCommonChar(count: number): Promise<Person[]> {
  return []
}

/** PID → scattered 32-bit integer（Feistel） */
export function unrankPerson(pid: string): number {
  let h = 0
  for (let i = 0; i < pid.length; i++) {
    h = ((h * 131) + pid.charCodeAt(i)) >>> 0
  }
  return feistel(h)
}

/** scattered integer → un-scattered integer（Feistel involution） */
export function rankPerson(n: number): number {
  return feistel(n)
}

/** 邻居查询：给定 pid，返回朝代壳内最近的 N 个 pid（按 3D 距离） */
export function neighborsOf(pid: string, n = 10): string[] {
  const p = personPosition(pid)
  if (!p) return []
  // PoC: 简化返回空；Phase D 接 layout 完整数据
  return []
}
