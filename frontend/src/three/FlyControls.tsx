/**
 * FlyControls — 极简版
 * - WASD/Space/Shift 平移
 * - 鼠标左键拖拽 look / 滚轮缩放
 * - 不用引 leva 调试面板（先简单）
 *
 * 不实现引力共转 / 双指 touch / lockPoet（这些留给 Phase D-7+）
 */
import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Camera, Vector3 } from 'three'
import { galaxySpin } from './galaxyParams'

const SPEED = 600
const ZOOM_SPEED = 0.0015

export function FlyControls() {
  const camera = useThree((s) => s.camera) as Camera
  const gl = useThree((s) => s.gl)
  const keys = useRef(new Set<string>())
  const dragging = useRef(false)
  const lastX = useRef(0)
  const lastY = useRef(0)
  const yaw = useRef(0)
  const pitch = useRef(0)

  useEffect(() => {
    const canvas = gl.domElement
    canvas.style.cursor = 'grab'

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      keys.current.add(e.key.toLowerCase())
    }
    const onKeyUp = (e: KeyboardEvent) => {
      keys.current.delete(e.key.toLowerCase())
    }
    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      dragging.current = true
      lastX.current = e.clientX
      lastY.current = e.clientY
      canvas.style.cursor = 'grabbing'
      canvas.setPointerCapture(e.pointerId)
    }
    const onMove = (e: PointerEvent) => {
      if (!dragging.current) return
      const dx = e.clientX - lastX.current
      const dy = e.clientY - lastY.current
      lastX.current = e.clientX
      lastY.current = e.clientY
      yaw.current -= dx * 0.005
      pitch.current -= dy * 0.005
      pitch.current = Math.max(-Math.PI / 2 + 0.1, Math.min(Math.PI / 2 - 0.1, pitch.current))
    }
    const onUp = (e: PointerEvent) => {
      dragging.current = false
      canvas.style.cursor = 'grab'
      canvas.releasePointerCapture(e.pointerId)
    }
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const dir = new Vector3()
      camera.getWorldDirection(dir)
      const delta = Math.sign(e.deltaY) * Math.abs(e.deltaY) * ZOOM_SPEED
      camera.position.addScaledVector(dir, delta)
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    canvas.addEventListener('pointerdown', onDown)
    canvas.addEventListener('pointermove', onMove)
    canvas.addEventListener('pointerup', onUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })

    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      canvas.removeEventListener('pointerdown', onDown)
      canvas.removeEventListener('pointermove', onMove)
      canvas.removeEventListener('pointerup', onUp)
      canvas.removeEventListener('wheel', onWheel)
    }
  }, [camera, gl])

  useFrame((_, dt) => {
    const ks = keys.current
    let dx = 0
    let dy = 0
    let dz = 0
    if (ks.has('w')) dy += 1
    if (ks.has('s')) dy -= 1
    if (ks.has('a')) dx -= 1
    if (ks.has('d')) dx += 1
    if (ks.has(' ')) dz += 1
    if (ks.has('shift')) dz -= 1
    if (dx === 0 && dy === 0 && dz === 0) return

    const move = new Vector3()
    const forward = new Vector3()
    camera.getWorldDirection(forward)
    const right = new Vector3().crossVectors(forward, camera.up).normalize()
    move.addScaledVector(right, dx)
    move.addScaledVector(forward, dy)
    move.y += dz
    move.normalize().multiplyScalar(SPEED * dt)
    camera.position.add(move)
  })

  useFrame(() => {
    // yaw 绕 Y，pitch 绕 X（右手系），初始 yaw=pitch=0 时朝 -Z
    // Three.js camera 默认看 -Z，所以初始 dir 必须是 (0, 0, -1)
    const cy = Math.cos(yaw.current)
    const sy = Math.sin(yaw.current)
    const cp = Math.cos(pitch.current)
    const sp = Math.sin(pitch.current)
    const dir = new Vector3(sy * cp, sp, -cy * cp)
    camera.lookAt(camera.position.clone().add(dir))
  })

  return null
}
