/**
 * 4 稳定接口 #4: zustand store + permalink
 *
 * 字段：
 *   selectedPerson: pid | null       — 当前选中的先祖
 *   selectedLine:   lineId | null    — 当前选中的支系
 *   flyTarget:      {x,y,z} | null   — fly mode 目标
 *   filters:        { dynasty, surname, generation } — UI 过滤
 *
 * 永久链接：
 *   #a=<personId>    → selectedPerson
 *   #p=<谱名>.<代数>.<支号>  → TODO Phase D
 *   #l=<lineId>      → selectedLine
 *   #g=<generation>  → filters.generation
 */
import { create } from 'zustand'

export interface Filters {
  dynasty: string | null
  surname: string | null
  generation: number | null
}

interface ZhijianState {
  selectedPerson: string | null
  selectedLine: string | null
  flyTarget: { x: number; y: number; z: number } | null
  filters: Filters
  setPerson: (pid: string | null) => void
  setLine: (lineId: string | null) => void
  setFlyTarget: (t: { x: number; y: number; z: number } | null) => void
  setFilter: (k: keyof Filters, v: string | number | null) => void
  reset: () => void
}

const DEFAULT_FILTERS: Filters = { dynasty: null, surname: null, generation: null }

export const useZhijianStore = create<ZhijianState>((set) => ({
  selectedPerson: null,
  selectedLine: null,
  flyTarget: null,
  filters: { ...DEFAULT_FILTERS },
  setPerson: (pid) => set({ selectedPerson: pid }),
  setLine: (lineId) => set({ selectedLine: lineId }),
  setFlyTarget: (t) => set({ flyTarget: t }),
  setFilter: (k, v) =>
    set((s: ZhijianState) => ({
      filters: { ...s.filters, [k]: v === '' ? null : v },
    })),
  reset: () =>
    set({
      selectedPerson: null,
      selectedLine: null,
      flyTarget: null,
      filters: { ...DEFAULT_FILTERS },
    }),
}))

/** 同步 permalink: store → URL hash */
export function syncPermalink(state: Partial<ZhijianState>): void {
  if (typeof window === 'undefined') return
  const hash = new URLSearchParams()
  if (state.selectedPerson) hash.set('a', state.selectedPerson)
  if (state.selectedLine) hash.set('l', state.selectedLine)
  if (state.filters?.generation != null) hash.set('g', String(state.filters.generation))
  if (state.filters?.dynasty) hash.set('d', state.filters.dynasty)
  if (state.filters?.surname) hash.set('s', state.filters.surname)
  const newHash = hash.toString() ? '#' + hash.toString() : ''
  if (window.location.hash !== newHash) {
    history.replaceState(null, '', window.location.pathname + window.location.search + newHash)
  }
}

/** 解析 permalink: URL hash → 初始 state */
export function parsePermalink(): Partial<ZhijianState> {
  if (typeof window === 'undefined') return {}
  const h = window.location.hash.slice(1)
  if (!h) return {}
  const params = new URLSearchParams(h)
  const filters: Filters = { ...DEFAULT_FILTERS }
  const d = params.get('d')
  const s = params.get('s')
  const g = params.get('g')
  if (d) filters.dynasty = d
  if (s) filters.surname = s
  if (g && !Number.isNaN(Number(g))) filters.generation = Number(g)
  return {
    selectedPerson: params.get('a') ?? null,
    selectedLine: params.get('l') ?? null,
    filters,
  }
}
