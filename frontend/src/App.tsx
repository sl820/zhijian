import { useEffect, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { BG_COLOR, FOG_NEAR, FOG_FAR } from '@/three/galaxyParams'
import { dprMax, detectQuality } from '@/three/detectQuality'
import { Galaxy } from '@/three/Galaxy'
import { CoordinateRings } from '@/three/CoordinateRings'
import { Landmarks } from '@/three/Landmarks'
import { PersonStars } from '@/three/PersonStars'
import { FlyControls } from '@/three/FlyControls'
import { useZhijianStore, parsePermalink, syncPermalink } from '@/state/store'
import { HUD } from '@/ui/HUD'
import { PersonPanel } from '@/ui/PersonPanel'
import { SearchPanel } from '@/ui/SearchPanel'

export function App() {
  const quality = useZhijianStore((s) => s.quality)
  const setQuality = useZhijianStore((s) => s.setQuality)
  const selectedPerson = useZhijianStore((s) => s.selectedPerson)
  const filters = useZhijianStore((s) => s.filters)

  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setQuality(detectQuality())
    const init = parsePermalink()
    if (init.selectedPerson) useZhijianStore.getState().setPerson(init.selectedPerson)
    if (init.filters) useZhijianStore.setState({ filters: init.filters })
  }, [setQuality])

  useEffect(() => {
    syncPermalink({ selectedPerson, filters })
  }, [selectedPerson, filters])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        useZhijianStore.getState().setSearchOpen(false)
        return
      }
      if (e.target instanceof HTMLInputElement) return
      if (e.key === '/') {
        e.preventDefault()
        useZhijianStore.getState().setSearchOpen(true)
        return
      }
      if (e.key.toLowerCase() === 'h') {
        useZhijianStore.getState().setUiHidden(!useZhijianStore.getState().uiHidden)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (err) {
    return (
      <div style={{ padding: 24, color: '#f88', background: BG_COLOR, minHeight: '100vh' }}>
        ERR: {err}
      </div>
    )
  }

  return (
    <div style={{ width: '100vw', height: '100vh', position: 'relative', overflow: 'hidden', background: BG_COLOR }}>
      <Canvas
        camera={{ position: [0, 0, 3500], fov: 55, near: 0.1, far: 18000 }}
        dpr={[1, dprMax(quality)]}
        gl={{ antialias: false, powerPreference: 'high-performance' }}
        raycaster={{ params: { Points: { threshold: 15 } } as never }}
      >
        <color attach="background" args={[BG_COLOR]} />
        <fog attach="fog" args={[BG_COLOR, FOG_NEAR, FOG_FAR]} />
        <Galaxy />
        <CoordinateRings />
        <Landmarks />
        <PersonStars />
        <FlyControls />
      </Canvas>
      <HUD />
      <SearchPanel />
      <PersonPanel />
      <div style={{
        position: 'absolute',
        bottom: 8,
        left: 12,
        color: '#666',
        fontSize: 11,
        fontFamily: 'system-ui',
        zIndex: 50,
        pointerEvents: 'none',
      }}>
        拖拽旋转 · WASD/Space/Shift 移动 · 滚轮缩放 · 点击节点查看 · / 搜 · H 隐/显
      </div>
    </div>
  )
}
