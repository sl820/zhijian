/**
 * v2 三维位置工具
 *
 * personPosition(pid) → {x, y, z, dynasty, radius, generation}
 * 内部读 data/position.ts 的 jiapu_v2.json
 *
 * 朝代壳径向（r） + 姓氏角向（θ） + 世代 z
 * 朝代 0..14 → 半径 (id+1) * 100；unknown id 15 → 1650
 */
import { loadLayout, allPositions } from '@/data/position'
import type { Position } from '@/types/layout'

export interface ScenePosition extends Position {
  pid: string
  dynasty: string
}

let cached: ScenePosition[] | null = null
let pidToScene: Map<string, ScenePosition> | null = null
const DYN_NAMES = [
  'shang', 'zhou', 'qin', 'han', 'jin', 'nanbeichao', 'sui', 'tang',
  'wudai', 'song', 'liaojin', 'yuan', 'ming', 'qing', 'minguo', 'unknown',
] as const

export async function loadScenePositions(): Promise<ScenePosition[]> {
  if (cached) return cached
  await loadLayout()
  const positions = allPositions()
  cached = positions.map(({ pid, p }) => ({
    ...p,
    pid,
    dynasty: DYN_NAMES[p.dynastyId] ?? 'unknown',
  }))
  pidToScene = new Map(cached.map((s) => [s.pid, s]))
  return cached
}

export function personPosition(pid: string): ScenePosition | null {
  if (!pidToScene) return null
  return pidToScene.get(pid) ?? null
}

export function allScenePositions(): ScenePosition[] {
  return cached ?? []
}

/** 朝代壳半径 */
export function dynastyShellRadius(dynastyId: number): number {
  return (dynastyId + 1) * 100
}

/** 邻域查询：给定 pid，返回 3D 距离最近的 N 个 */
export function neighborsOf(pid: string, n = 10): ScenePosition[] {
  const me = personPosition(pid)
  if (!me || !cached) return []
  const out: { p: ScenePosition; d: number }[] = []
  for (const p of cached) {
    if (p.pid === pid) continue
    const dx = p.x - me.x
    const dy = p.y - me.y
    const dz = p.z - me.z
    const d = dx * dx + dy * dy + dz * dz
    out.push({ p, d })
  }
  out.sort((a, b) => a.d - b.d)
  return out.slice(0, n).map((o) => o.p)
}
