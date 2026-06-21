/**
 * 极简 HUD — 顶部 4 按钮 + 朝代过滤
 * 完整版（统计/速度/常驻标签）留给 Phase D-9+
 */
import { useZhijianStore } from '@/state/store'
import { FONT_STACK, THEME, DYNASTY_COLORS } from '@/three/galaxyParams'

export function HUD() {
  const reset = useZhijianStore((s) => s.reset)
  const filter = useZhijianStore((s) => s.filters)
  const setFilter = useZhijianStore((s) => s.setFilter)
  const uiHidden = useZhijianStore((s) => s.uiHidden)
  const setUiHidden = useZhijianStore((s) => s.setUiHidden)

  if (uiHidden) {
    return (
      <button style={showBtn} onClick={() => setUiHidden(false)} title="显示界面 (H)">
        显
      </button>
    )
  }

  return (
    <div style={hudStyle}>
      <div style={rowStyle}>
        <span style={titleStyle}>志鉴 · 家谱星图</span>
        <button style={btn} onClick={reset}>重置</button>
        <button style={btn} onClick={() => setUiHidden(true)}>隐</button>
      </div>
      <div style={rowStyle}>
        <span style={labelStyle}>朝代</span>
        <button
          style={chipStyle(filter.dynasty === null)}
          onClick={() => setFilter('dynasty', null)}
        >
          全部
        </button>
        {DYNASTY_COLORS.filter(([k]) => k !== 'unknown').map(([k]) => (
          <button
            key={k}
            style={chipStyle(filter.dynasty === k)}
            onClick={() => setFilter('dynasty', k)}
          >
            {k}
          </button>
        ))}
      </div>
    </div>
  )
}

const hudStyle: React.CSSProperties = {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  padding: 12,
  background: 'linear-gradient(180deg, rgba(10,14,31,0.9) 0%, rgba(10,14,31,0) 100%)',
  color: THEME.rice,
  fontFamily: FONT_STACK.serif,
  zIndex: 100,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

const rowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
  flexWrap: 'wrap',
}

const titleStyle: React.CSSProperties = {
  fontSize: 18,
  color: THEME.gold,
  fontFamily: FONT_STACK.display,
  marginRight: 16,
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#888',
}

const btn: React.CSSProperties = {
  background: 'rgba(29,39,71,0.8)',
  border: `1px solid ${THEME.indigoNear}`,
  color: THEME.rice,
  padding: '4px 12px',
  borderRadius: 4,
  cursor: 'pointer',
  fontFamily: FONT_STACK.sans,
  fontSize: 12,
}

function chipStyle(active: boolean): React.CSSProperties {
  return {
    background: active ? THEME.vermilion : 'rgba(29,39,71,0.5)',
    border: `1px solid ${active ? THEME.vermilion : THEME.indigoNear}`,
    color: THEME.rice,
    padding: '2px 8px',
    borderRadius: 3,
    cursor: 'pointer',
    fontFamily: FONT_STACK.sans,
    fontSize: 11,
  }
}

const showBtn: React.CSSProperties = {
  position: 'absolute',
  top: 12,
  right: 12,
  background: 'rgba(10,14,31,0.9)',
  border: `1px solid ${THEME.indigoNear}`,
  color: THEME.rice,
  padding: '4px 12px',
  borderRadius: 4,
  cursor: 'pointer',
  zIndex: 100,
  fontFamily: FONT_STACK.sans,
  fontSize: 12,
}
