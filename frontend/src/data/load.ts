/**
 * 4 稳定接口 #1: data 加载层
 *
 * Range fetch 读 public/persons/ 与 public/relations/ 桶。
 * 索引 idx.json 在启动时一次性拉入内存。
 * 单条 person 走"二分定位 bucket → fetch 整 bucket → 线性查找 pid"路径。
 */
import type { Person } from '@/types/person'
import type { Relation } from '@/types/relation'
import type { Line } from '@/types/line'
import type { BucketIndex, BucketMeta } from '@/types/index'

const BASE = import.meta.env.BASE_URL
const PERSONS_DIR = `${BASE}persons/`
const RELATIONS_DIR = `${BASE}relations/`

interface BucketCache {
  index: BucketIndex
  byPid: Map<string, Person> | null
  byLineId: Map<string, Line> | null
  cnToPinyin: Map<string, string> | null
}

const personsCache: BucketCache = { index: { version: 0, prefix: '', buckets: [] }, byPid: null, byLineId: null, cnToPinyin: null }
const relationsCache: BucketCache = { index: { version: 0, prefix: '', buckets: [] }, byPid: null, byLineId: null, cnToPinyin: null }

async function fetchIndex(dir: string, cache: BucketCache): Promise<BucketIndex> {
  if (cache.index.buckets.length > 0) return cache.index
  const res = await fetch(`${dir}idx.json`)
  if (!res.ok) throw new Error(`failed to load ${dir}idx.json: ${res.status}`)
  const idx = (await res.json()) as BucketIndex
  cache.index = idx
  return idx
}

function findBucket(idx: BucketIndex, pid: string): BucketMeta | null {
  // bucket 按 pid 排序 → 二分
  const bs = idx.buckets
  let lo = 0
  let hi = bs.length - 1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const b = bs[mid]!
    if (pid < b.start_pid) hi = mid - 1
    else if (pid > b.end_pid) lo = mid + 1
    else return b
  }
  return null
}

async function fetchBucket(dir: string, prefix: string, b: BucketMeta): Promise<unknown[]> {
  const url = `${dir}${prefix}_${String(b.id).padStart(4, '0')}.json`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`failed to load ${url}: ${res.status}`)
  return (await res.json()) as unknown[]
}

async function ensurePersonsLoaded(): Promise<Map<string, Person>> {
  if (personsCache.byPid) return personsCache.byPid
  const idx = await fetchIndex(PERSONS_DIR, personsCache)
  const all = new Map<string, Person>()
  const cnMap: Map<string, string> = new Map()
  // 并行拉所有 bucket（83 桶 ≈ 50MB，浏览器 6 并发足够）
  const allRows = await Promise.all(
    idx.buckets.map((b) => fetchBucket(PERSONS_DIR, 'persons', b) as Promise<Person[]>)
  )
  for (const rows of allRows) {
    for (const p of rows) {
      all.set(p.pid, p)
      if (p.name && p.family_name && p.name.length > 0) {
        const firstChar = p.name.charAt(0)
        if (!cnMap.has(firstChar)) cnMap.set(firstChar, p.family_name.toLowerCase())
      }
    }
  }
  personsCache.byPid = all
  personsCache.cnToPinyin = cnMap
  return all
}

async function ensureRelationsLoaded(): Promise<Relation[]> {
  if (relationsCache.byPid) return relationsCache.byPid as unknown as Relation[]
  const idx = await fetchIndex(RELATIONS_DIR, relationsCache)
  const all: Relation[] = []
  const allRows = await Promise.all(
    idx.buckets.map((b) => fetchBucket(RELATIONS_DIR, 'relations', b) as Promise<Relation[]>)
  )
  for (const rows of allRows) {
    for (const r of rows) all.push(r)
  }
  ;(relationsCache as unknown as { byPid: Relation[] }).byPid = all
  return all
}

/** 加载单个人物（按 pid）。返回 null 表示未找到。 */
export async function loadPerson(pid: string): Promise<Person | null> {
  const idx = await fetchIndex(PERSONS_DIR, personsCache)
  const b = findBucket(idx, pid)
  if (!b) return null
  const rows = (await fetchBucket(PERSONS_DIR, 'persons', b)) as Person[]
  return rows.find((p) => p.pid === pid) ?? null
}

/**
 * 加载一条支系（按 lineId = family_uri tail 16 chars）。
 * 运行时聚合：扫所有 persons 找相同 family_uri，按 (generation, order) 排序。
 */
export async function loadLine(lineId: string): Promise<Line | null> {
  const all = await ensurePersonsLoaded()
  let root: Person | undefined
  const members: Person[] = []
  for (const p of all.values()) {
    if (p.family_uri && p.family_uri.slice(-16) === lineId) {
      members.push(p)
      if (p.family_role.startsWith('shi-') || p.family_role === 'shi-zu') {
        if (!root || p.generation < root.generation) root = p
      }
    }
  }
  if (members.length === 0) return null
  members.sort((a, b) => a.generation - b.generation || a.order.localeCompare(b.order, 'zh'))
  return {
    lineId,
    familyUri: members[0]!.family_uri,
    familyName: members[0]!.family_name,
    rootPid: root ? root.pid : members[0]!.pid,
    dynasty: members[0]!.dynasty,
    personCount: members.length,
    pids: members.map((m) => m.pid),
  }
}

/** 加载某人的祖先链（沿 parentOf 边上溯到 root）。返回有序 pid 列表（含自身）。 */
export async function loadAncestors(pid: string): Promise<string[]> {
  const all = await ensureRelationsLoaded()
  const parentOf: Map<string, string[]> = new Map()
  for (const r of all) {
    if (r.rel === 'parentOf') {
      const arr = parentOf.get(r.dst) ?? []
      arr.push(r.src)
      parentOf.set(r.dst, arr)
    }
  }
  const chain: string[] = [pid]
  let cur = pid
  const seen = new Set<string>([pid])
  while (true) {
    const ps = parentOf.get(cur)
    if (!ps || ps.length === 0) break
    const next = ps.find((p) => !seen.has(p))
    if (!next) break
    chain.push(next)
    seen.add(next)
    cur = next
  }
  return chain
}

/**
 * 按姓氏搜索（支持中文字符：自动映射到拼音前缀；纯 pinyin 输入直接前缀匹配）。
 * 返回匹配的 Person 列表（按朝代 + 姓名排序，截前 50）。
 */
export async function searchSurname(query: string, limit = 50): Promise<Person[]> {
  if (!query) return []
  const q = query.toLowerCase()
  const all = await ensurePersonsLoaded()
  const cnMap = personsCache.cnToPinyin ?? new Map<string, string>()
  // 查 CN → pinyin：query 是中文时取对应 pinyin prefix
  const pinyinPrefix = cnMap.get(query) ?? q
  const out: Person[] = []
  for (const p of all.values()) {
    if (
      p.family_name.toLowerCase().startsWith(pinyinPrefix) ||
      p.name.startsWith(query) ||
      p.pid.startsWith(q)
    ) {
      out.push(p)
      if (out.length >= limit * 4) break
    }
  }
  out.sort((a, b) => a.dynasty.localeCompare(b.dynasty) || a.name.localeCompare(b.name, 'zh'))
  return out.slice(0, limit)
}

/**
 * 按名/字/号搜索（子串匹配）。
 * 返回匹配的 Person 列表（按朝代 + 姓名排序，截前 limit）。
 */
export async function searchByName(query: string, limit = 50): Promise<Person[]> {
  if (!query) return []
  const q = query.trim()
  if (!q) return []
  const all = await ensurePersonsLoaded()
  const out: Person[] = []
  for (const p of all.values()) {
    if (
      p.name.includes(q) ||
      p.name_alt.includes(q) ||
      p.courtesy.includes(q) ||
      p.pseudonym.includes(q)
    ) {
      out.push(p)
      if (out.length >= limit * 4) break
    }
  }
  out.sort((a, b) => a.dynasty.localeCompare(b.dynasty) || a.name.localeCompare(b.name, 'zh'))
  return out.slice(0, limit)
}

/**
 * 按支系搜索（family_name 或 family_uri 子串匹配）。
 * 返回去重后的 Person 列表（同 family_uri 只返回最早一代始祖）。
 */
export async function searchByLine(query: string, limit = 50): Promise<Person[]> {
  if (!query) return []
  const q = query.trim()
  if (!q) return []
  const all = await ensurePersonsLoaded()
  const byLineUri: Map<string, Person> = new Map()
  for (const p of all.values()) {
    if (!p.family_uri) continue
    if (p.family_uri.includes(q) || p.family_name.includes(q)) {
      // 同 line 只留 generation 最小（即始祖）
      const cur = byLineUri.get(p.family_uri)
      if (!cur || p.generation < cur.generation) {
        byLineUri.set(p.family_uri, p)
      }
      if (byLineUri.size >= limit * 4) break
    }
  }
  const out = Array.from(byLineUri.values())
  out.sort((a, b) => a.dynasty.localeCompare(b.dynasty) || a.family_name.localeCompare(b.family_name, 'zh'))
  return out.slice(0, limit)
}

/** 拉所有不重复的 family_name 列表（按出现频次倒序），给姓 tab 自动补全。 */
export async function getAllFamilyNames(limit = 200): Promise<{ name: string; count: number }[]> {
  const all = await ensurePersonsLoaded()
  const cnt: Map<string, number> = new Map()
  for (const p of all.values()) {
    if (!p.family_name) continue
    cnt.set(p.family_name, (cnt.get(p.family_name) ?? 0) + 1)
  }
  return Array.from(cnt.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }))
}

/** 按朝代统计 Person 数量，给朝代 tab 显示。 */
export async function getDynastyCounts(): Promise<{ dynasty: string; count: number }[]> {
  const all = await ensurePersonsLoaded()
  const cnt: Map<string, number> = new Map()
  for (const p of all.values()) {
    cnt.set(p.dynasty, (cnt.get(p.dynasty) ?? 0) + 1)
  }
  return Array.from(cnt.entries())
    .map(([dynasty, count]) => ({ dynasty, count }))
    .sort((a, b) => b.count - a.count)
}
