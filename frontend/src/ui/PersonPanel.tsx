/**
 * 极简 PersonPanel — 显示选中先祖基础信息
 * 不接血缘/支系（那些留给 Phase D-7+）
 */
import { useEffect, useState } from 'react'
import { loadPerson } from '@/data/load'
import { useZhijianStore } from '@/state/store'
import type { Person } from '@/types/person'
import { FONT_STACK, THEME, DYNASTY_COLOR_MAP } from '@/three/galaxyParams'

const dynastyNameCn: Record<string, string> = {
  shang: '商', zhou: '周', qin: '秦', han: '汉', jin: '晋', nanbeichao: '南北朝',
  sui: '隋', tang: '唐', wudai: '五代', song: '宋', liaojin: '辽金', yuan: '元',
  ming: '明', qing: '清', minguo: '民国', unknown: '不详',
}

const familyRoleCn: Record<string, string> = {
  'shi-zu': '始祖', 'shi-qian-zu': '始迁祖', 'yuan-zu': '元祖',
  'xian-zu': '显祖', 'zhi-zu': '支祖', 'fang-zu': '房祖',
  'ming-ren': '名人',
}

export function PersonPanel() {
  const pid = useZhijianStore((s) => s.selectedPerson)
  const setPerson = useZhijianStore((s) => s.setPerson)
  const [person, setPersonData] = useState<Person | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!pid) {
      setPersonData(null)
      return
    }
    loadPerson(pid)
      .then((p) => {
        if (!p) {
          setErr('not found')
          setPersonData(null)
        } else {
          setErr(null)
          setPersonData(p)
        }
      })
      .catch((e: unknown) => setErr(String(e)))
  }, [pid])

  if (!pid) return null
  if (err) {
    return (
      <div style={panelStyle}>
        <div style={headerStyle}>
          <span style={{ color: THEME.vermilion }}>载入失败</span>
          <button style={closeBtn} onClick={() => setPerson(null)}>×</button>
        </div>
        <div style={{ color: '#aaa' }}>{err}</div>
      </div>
    )
  }
  if (!person) {
    return (
      <div style={panelStyle}>
        <div style={headerStyle}>
          <span style={{ color: '#888' }}>载入中…</span>
          <button style={closeBtn} onClick={() => setPerson(null)}>×</button>
        </div>
      </div>
    )
  }

  const color = DYNASTY_COLOR_MAP.get(person.dynasty)
  const dynastyCn = dynastyNameCn[person.dynasty] ?? person.dynasty
  const roleCn = familyRoleCn[person.family_role] ?? person.family_role
  const dynastyColor = color ? `#${color.getHexString()}` : THEME.gold

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <span style={{ color: THEME.rice, fontSize: 18, fontFamily: FONT_STACK.display }}>{person.name}</span>
        <button style={closeBtn} onClick={() => setPerson(null)}>×</button>
      </div>
      {person.name_alt && person.name_alt !== person.name && (
        <div style={rowStyle}>
          <span style={labelStyle}>又名</span>
          <span style={{ color: THEME.gold }}>{person.name_alt}</span>
        </div>
      )}
      {person.courtesy && (
        <div style={rowStyle}>
          <span style={labelStyle}>字</span>
          <span style={{ color: THEME.rice }}>{person.courtesy}</span>
        </div>
      )}
      {person.pseudonym && (
        <div style={rowStyle}>
          <span style={labelStyle}>号</span>
          <span style={{ color: THEME.rice }}>{person.pseudonym}</span>
        </div>
      )}
      <div style={rowStyle}>
        <span style={labelStyle}>朝代</span>
        <span style={{ color: dynastyColor, fontWeight: 600 }}>{dynastyCn}</span>
      </div>
      {roleCn && (
        <div style={rowStyle}>
          <span style={labelStyle}>角色</span>
          <span style={{ color: THEME.rice }}>{roleCn}</span>
        </div>
      )}
      {person.family_name && (
        <div style={rowStyle}>
          <span style={labelStyle}>姓</span>
          <span style={{ color: THEME.gold }}>{person.family_name}</span>
        </div>
      )}
      <div style={{ ...rowStyle, borderTop: `1px solid ${THEME.indigoNear}`, paddingTop: 8, marginTop: 8, fontSize: 11, color: '#666' }}>
        pid: {person.pid}
      </div>
    </div>
  )
}

const panelStyle: React.CSSProperties = {
  position: 'absolute',
  right: 20,
  top: 80,
  width: 320,
  padding: 16,
  background: 'rgba(10, 14, 31, 0.92)',
  border: `1px solid ${THEME.indigoNear}`,
  borderRadius: 8,
  color: THEME.rice,
  fontFamily: FONT_STACK.serif,
  fontSize: 14,
  zIndex: 100,
  boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  borderBottom: `1px solid ${THEME.indigoNear}`,
  paddingBottom: 8,
  marginBottom: 12,
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

const rowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 12,
  padding: '4px 0',
}

const labelStyle: React.CSSProperties = {
  color: '#888',
  minWidth: 40,
  fontSize: 12,
}
