/**
 * 共享时钟 + 星系几何常量 + 朝代色 + 字体栈
 *
 * - GALAXY：4 臂螺旋参数
 * - galaxySpin / poemClock：共享时钟对象（唯一推进者 = Galaxy）
 * - spinXZ / unspinXZ：local → world 坐标转换
 * - DYNASTY_COLORS：11 朝 hue（复用 v1 palette.js）
 * - FONT_STACK：4 字体栈（复用 v1 fonts.js）
 * - BG_COLOR / FOG：靛蓝夜底
 *
 * 改一处就改所有场景组件。
 */
import { Color } from 'three'

export const GALAXY = {
  RADIUS: 1700,        // 朝代壳外圈（明 12×100=1200, +unk 16×100=1600, +50=1650, 留余 1700）
  BRANCHES: 4,         // 4 臂
  TWIST: 5.2,
  ARM_SPREAD: 0.42,
  THICKNESS: 0.11,
} as const

export const SPIN_RATE = 0.012
export const DECOR_RATE = 0.019

export function decorStarCount(quality: 'low' | 'medium' | 'high'): number {
  return quality === 'low' ? 4000 : quality === 'medium' ? 9000 : 16000
}

export const galaxySpin = { angle: 0, decorAngle: 0 }
export const poemClock = { t: 0 }

export function advanceSpin(dt: number): void {
  galaxySpin.angle = (galaxySpin.angle + dt * SPIN_RATE) % (Math.PI * 2)
  galaxySpin.decorAngle = (galaxySpin.decorAngle + dt * DECOR_RATE) % (Math.PI * 2)
  poemClock.t += dt
}

export function spinXZ(x: number, z: number): [number, number] {
  const a = galaxySpin.angle
  const c = Math.cos(a)
  const s = Math.sin(a)
  return [x * c + z * s, -x * s + z * c]
}

export function unspinXZ(x: number, z: number): [number, number] {
  const a = galaxySpin.angle
  const c = Math.cos(a)
  const s = Math.sin(a)
  return [x * c - z * s, x * s + z * c]
}

export const BG_COLOR = '#03040a'
export const FOG_NEAR = 2400
export const FOG_FAR = 13000

/**
 * 11 朝代色（复用 v1 palette.js，v1 11 hue → v2 16 key 取主朝代归并）
 * 朝代 id（来自 dynasty_normalize.py）→ 色
 */
export const DYNASTY_COLORS: ReadonlyArray<readonly [string, string]> = [
  ['shang',      '#9b6a3f'],
  ['zhou',       '#a07a4a'],
  ['qin',        '#8a5a2a'],
  ['han',        '#8b7355'],
  ['jin',        '#7a8aa8'],
  ['nanbeichao', '#9b88a8'],
  ['sui',        '#b59a6a'],
  ['tang',       '#c9a050'],
  ['wudai',      '#a08a78'],
  ['song',       '#d4b070'],
  ['liaojin',    '#b89878'],
  ['yuan',       '#5b9b9c'],
  ['ming',       '#c2362a'],
  ['qing',       '#6080a0'],
  ['minguo',     '#9aaab8'],
  ['unknown',    '#3a3a4a'],
]

export const DYNASTY_COLOR_MAP: ReadonlyMap<string, Color> = new Map(
  DYNASTY_COLORS.map(([k, c]) => [k, new Color(c)]),
)

/** 4 字体栈（v1 fonts.js 原样） */
export const FONT_STACK = {
  display: '"LXGW WenKai TC", "霞鹜文楷", "Source Han Serif SC", serif',
  serif: '"Source Han Serif SC", "思源宋体", "Songti SC", serif',
  sans: '"PingFang SC", "Microsoft YaHei", "Helvetica Neue", system-ui, sans-serif',
  mono: '"JetBrains Mono", "Cascadia Code", "Fira Code", monospace',
} as const

/** 主题色（v1 PALETTE 子集） */
export const THEME = {
  indigoDeep: '#0a0e1f',
  indigoNear: '#1d2747',
  vermilion: '#c2362a',
  seal: '#a82a1f',
  ink: '#1a1a24',
  gold: '#d4b070',
  rice: '#f0e8d4',
} as const
