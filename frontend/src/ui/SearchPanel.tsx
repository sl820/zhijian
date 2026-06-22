/**
 * SearchPanel — 4 tab 搜索先祖
 * 姓：family_name 前缀 → 结果点 setPerson + fly 到 (r, angle, z)
 * 名：name / name_alt / courtesy / pseudonym 子串
 * 支系：family_uri / family_name 子串 → 同 line 只返始祖
 * 朝代：直接列 16 朝代 + Person 计数，点击 = 朝代过滤
 */
import { useEffect, useState } from 'react'
import { useZhijianStore } from '@/state/store'
import { searchByName, searchByLine, searchSurname, getDynastyCounts, loadPerson } from '@/data/load'
import { personWorldPos } from '@/data/position'
import type { Person } from '@/types/person'
import { FONT_STACK, THEME, DYNASTY_COLOR_MAP } from '@/three/galaxyParams'

type Tab = 'surname' | 'name' | 'line' | 'dynasty'

const dynastyNameCn: Record<string, string> = {
  shang: '商', zhou: '周', qin: '秦', han: '汉', jin: '晋', nanbeichao: '南北朝',
  sui: '隋', tang: '唐', wudai: '五代', song: '宋', liaojin: '辽金', yuan: '元',
  ming: '明', qing: '清', minguo: '民国', unknown: '不详',
}

const tabs: { key: Tab; label: string }[] = [
  { key: 'surname', label: '姓' },
  { key: 'name', label: '名' },
  { key: 'line', label: '支系' },
  { key: 'dynasty', label: '朝代' },
]

export function SearchPanel() {
  const open = useZhijianStore((s) => s.searchOpen)
  const setOpen = useZhijianStore((s) => s.setSearchOpen)
  const setPerson = useZhijianStore((s) => s.setPerson)
  const setFlyTarget = useZhijianStore((s) => s.setFlyTarget)
  const setFilter = useZhijianStore((s) => s.setFilter)

  const [tab, setTab] = useState<Tab>('surname')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Person[]>([])
  const [dynasties, setDynasties] = useState<{ dynasty: string; count: number }[]>([])
  const [loading, setLoading] = useState(false)

  // 首次挂载 + 切到 dynasty tab 时拉取朝代计数
  useEffect(() => {
    if (!open) return
    if (dynasties.length === 0) {
      getDynastyCounts().then(setDynasties).catch(() => setDynasties([]))
    }
  }, [open, dynasties.length])

  // query 变化时执行搜索（name / line tab）
  useEffect(() => {
    if (!open) return
    if (tab === 'dynasty') return
    if (tab === 'surname') {
      // 姓 tab 用 query 当 family_name 前缀直接 filter
      setLoading(true)
      searchSurname(query, 30)
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setLoading(false))
      return
    }
    if (tab === 'name') {
      setLoading(true)
      searchByName(query, 30)
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setLoading(false))
      return
    }
    if (tab === 'line') {
      setLoading(true)
      searchByLine(query, 30)
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setLoading(false))
    }
  }, [open, tab, query])

  if (!open) return null

  const onPickPerson = (p: Person) => {
    setPerson(p.pid)
    // fly camera to (x, y, z) 上方 800 单位，让目标在视野正中
    const w = personWorldPos(p.pid)
    if (w) {
      setFlyTarget({ x: w.x, y: w.y, z: w.z + 800 })
    }
    setOpen(false)
  }

  const onPickDynasty = (d: string) => {
    setFilter('dynasty', d)
    setOpen(false)
  }

  return (
    <div style={panelStyle} onClick={(e) => e.stopPropagation()}>
      <div style={headerStyle}>
        <span style={{ color: THEME.gold, fontFamily: FONT_STACK.display, fontSize: 16 }}>搜先祖</span>
        <button style={closeBtn} onClick={() => setOpen(false)} title="关闭 (Esc)">×</button>
      </div>
      <div style={tabRowStyle}>
        {tabs.map((t) => (
          <button
            key={t.key}
            style={tabBtn(tab === t.key)}
            onClick={() => { setTab(t.key); setQuery(''); setResults([]) }}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab !== 'dynasty' && (
        <input
          autoFocus
          style={inputStyle}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            tab === 'surname' ? '输入姓（如 韩/李/王）'
              : tab === 'name' ? '输入名/字/号'
              : '输入支系名或家族 uri tail'
          }
        />
      )}
      <div style={resultListStyle}>
        {tab === 'dynasty' ? (
          dynasties.length === 0 ? (
            <div style={emptyStyle}>载入中…</div>
          ) : (
            dynasties.map((d) => {
              const cn = dynastyNameCn[d.dynasty] ?? d.dynasty
              const color = DYNASTY_COLOR_MAP.get(d.dynasty)
              const hex = color ? `#${color.getHexString()}` : THEME.gold
              return (
                <button
                  key={d.dynasty}
                  style={dynastyRow}
                  onClick={() => onPickDynasty(d.dynasty)}
                >
                  <span style={{ color: hex, fontWeight: 600, minWidth: 40 }}>{cn}</span>
                  <span style={{ color: '#888', fontSize: 11 }}>{d.dynasty}</span>
                  <span style={{ color: THEME.rice, marginLeft: 'auto' }}>{d.count}</span>
                </button>
              )
            })
          )
        ) : loading ? (
          <div style={emptyStyle}>搜索中…</div>
        ) : results.length === 0 ? (
          <div style={emptyStyle}>{query ? '无匹配' : '请输入'}</div>
        ) : (
          results.map((p) => {
            const cn = dynastyNameCn[p.dynasty] ?? p.dynasty
            const color = DYNASTY_COLOR_MAP.get(p.dynasty)
            const hex = color ? `#${color.getHexString()}` : THEME.gold
            return (
              <button
                key={p.pid}
                style={personRow}
                onClick={() => onPickPerson(p)}
                title={p.pid}
              >
                <span style={{ color: THEME.rice, fontFamily: FONT_STACK.serif }}>
                  {p.name || '(无名)'}
                </span>
                <span style={{ color: THEME.gold, fontSize: 12 }}>{p.family_name}</span>
                <span style={{ color: hex, fontSize: 12, minWidth: 30 }}>{cn}</span>
                <span style={{ color: '#666', fontSize: 10, marginLeft: 'auto' }}>第{p.generation}世</span>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}

const panelStyle: React.CSSProperties = {
  position: 'absolute',
  top: 80,
  left: 20,
  width: 360,
  maxHeight: 'calc(100vh - 100px)',
  background: 'rgba(10, 14, 31, 0.95)',
  border: `1px solid ${THEME.indigoNear}`,
  borderRadius: 8,
  color: THEME.rice,
  fontFamily: FONT_STACK.serif,
  zIndex: 200,
  boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
  display: 'flex',
  flexDirection: 'column',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  borderBottom: `1px solid ${THEME.indigoNear}`,
  padding: '8px 12px',
}

const tabRowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 4,
  padding: '8px 12px 0',
}

function tabBtn(active: boolean): React.CSSProperties {
  return {
    background: active ? THEME.vermilion : 'transparent',
    border: `1px solid ${active ? THEME.vermilion : THEME.indigoNear}`,
    color: THEME.rice,
    padding: '4px 12px',
    borderRadius: 3,
    cursor: 'pointer',
    fontFamily: FONT_STACK.sans,
    fontSize: 12,
  }
}

const inputStyle: React.CSSProperties = {
  margin: '8px 12px',
  padding: '6px 8px',
  background: 'rgba(29,39,71,0.6)',
  border: `1px solid ${THEME.indigoNear}`,
  borderRadius: 4,
  color: THEME.rice,
  fontFamily: FONT_STACK.sans,
  fontSize: 13,
  outline: 'none',
}

const resultListStyle: React.CSSProperties = {
  flex: 1,
  overflowY: 'auto',
  padding: '0 4px 8px',
  minHeight: 200,
  maxHeight: '60vh',
}

const personRow: React.CSSProperties = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
  width: '100%',
  background: 'transparent',
  border: 'none',
  borderBottom: '1px solid rgba(29,39,71,0.4)',
  color: THEME.rice,
  padding: '6px 8px',
  textAlign: 'left',
  cursor: 'pointer',
  fontFamily: FONT_STACK.serif,
  fontSize: 13,
}

const dynastyRow: React.CSSProperties = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
  width: '100%',
  background: 'transparent',
  border: 'none',
  borderBottom: '1px solid rgba(29,39,71,0.4)',
  color: THEME.rice,
  padding: '6px 8px',
  textAlign: 'left',
  cursor: 'pointer',
  fontFamily: FONT_STACK.serif,
  fontSize: 13,
}

const emptyStyle: React.CSSProperties = {
  padding: 16,
  color: '#666',
  textAlign: 'center',
  fontFamily: FONT_STACK.sans,
  fontSize: 12,
}

const closeBtn: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: THEME.rice,
  fontSize: 22,
  cursor: 'pointer',
  padding: 0,
  width: 24,
  height: 24,
}
