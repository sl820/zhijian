/**
 * 4 稳定接口 #3: 位置查表
 *
 * 启动时一次性加载 public/layouts/jiapu_v2.json（Phase C 辅助 npz_to_layout_json.py 生成）。
 * personPosition(pid) → {dynasty, angle, z}（CLAUDE.md 契约）
 */
import type { Position, LayoutData } from '@/types/layout'

const BASE = import.meta.env.BASE_URL
const LAYOUT_URL = `${BASE}layouts/jiapu_v2.json`

const DYN2ID: Record<string, number> = {
  shang: 0, zhou: 1, qin: 2, han: 3, jin: 4, nanbeichao: 5,
  sui: 6, tang: 7, wudai: 8, song: 9, liaojin: 10, yuan: 11,
  ming: 12, qing: 13, minguo: 14, unknown: 15,
}

let layoutData: LayoutData | null = null
let pidIndex: Map<string, number> | null = null

export async function loadLayout(): Promise<LayoutData> {
  if (layoutData) return layoutData
  const res = await fetch(LAYOUT_URL)
  if (!res.ok) throw new Error(`failed to load ${LAYOUT_URL}: ${res.status}`)
  layoutData = (await res.json()) as LayoutData
  pidIndex = new Map()
  layoutData.nodeIds.forEach((pid, i) => pidIndex!.set(pid, i))
  return layoutData
}

export function personPosition(pid: string): { dynasty: string; angle: number; z: number } | null {
  if (!layoutData || !pidIndex) {
    throw new Error('position.ts: call loadLayout() before personPosition()')
  }
  const i = pidIndex.get(pid)
  if (i === undefined) return null
  const p = layoutData.positions[i]
  if (!p) return null
  const dynasty = Object.keys(DYN2ID).find((k) => DYN2ID[k] === p.dynastyId) ?? 'unknown'
  return { dynasty, angle: p.angle, z: p.z }
}

export function getPosition(pid: string): Position | null {
  if (!layoutData || !pidIndex) return null
  const i = pidIndex.get(pid)
  if (i === undefined) return null
  return layoutData.positions[i] ?? null
}

export function allPositions(): { pid: string; p: Position }[] {
  if (!layoutData) return []
  const out: { pid: string; p: Position }[] = []
  for (let i = 0; i < layoutData.nodeIds.length; i++) {
    const pid = layoutData.nodeIds[i]
    const p = layoutData.positions[i]
    if (pid && p) out.push({ pid, p })
  }
  return out
}

/** pid → 世界坐标 (x, y, z)。null 表示未在 layout 中。 */
export function personWorldPos(pid: string): { x: number; y: number; z: number } | null {
  const p = getPosition(pid)
  if (!p) return null
  return { x: p.x, y: p.y, z: p.z }
}

export { DYN2ID }
