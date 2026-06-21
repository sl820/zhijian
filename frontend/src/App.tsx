import { useEffect, useState } from 'react'
import { loadLayout, allPositions } from '@/data/position'
import { useZhijianStore } from '@/state/store'

export function App() {
  const [ready, setReady] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [count, setCount] = useState(0)
  const selectedPerson = useZhijianStore((s) => s.selectedPerson)
  const setPerson = useZhijianStore((s) => s.setPerson)

  useEffect(() => {
    loadLayout()
      .then(() => {
        setCount(allPositions().length)
        setReady(true)
      })
      .catch((e: unknown) => setErr(String(e)))
  }, [])

  if (err) return <div style={{ padding: 24, color: '#f88' }}>ERR: {err}</div>
  if (!ready) return <div style={{ padding: 24, color: '#aaa' }}>志鉴 v2 · 引擎层 ready check…</div>

  return (
    <div style={{ padding: 24, fontFamily: 'system-ui, sans-serif', color: '#eee', background: '#000', minHeight: '100vh' }}>
      <h1>志鉴 v2 · Phase C 引擎层</h1>
      <p>layout 节点：<b>{count}</b></p>
      <p>当前选中：<b>{selectedPerson ?? '（无）'}</b></p>
      <button onClick={() => setPerson('0005c063mh4glmyk')}>选第一个 pid（demo）</button>
      <p style={{ marginTop: 24, color: '#888', fontSize: 13 }}>
        Phase C 完成。Phase D 启动 React 18 + Three.js 前端骨架。
      </p>
    </div>
  )
}
