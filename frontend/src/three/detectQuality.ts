/**
 * 弱显卡探测 → 决定 DPR 上限 / Bloom 开关 / 装饰星数
 *
 * 探测策略：
 * - WebGL2 不支持 → low
 * - maxTextureSize < 4096 → low
 * - 设备像素比 ≥ 2.5 + 强 UA（mobile）→ medium
 * - 默认 → high
 *
 * 诗云范本，志鉴 v2 微调（数据规模 5.5x 更大，弱机阈值更激进）。
 */
export type Quality = 'low' | 'medium' | 'high'

export function detectQuality(): Quality {
  if (typeof window === 'undefined') return 'high'
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl2') ?? canvas.getContext('webgl')
    if (!gl) return 'low'
    const dbg = (gl as WebGLRenderingContext).getExtension('WEBGL_debug_renderer_info')
    if (dbg) {
      const renderer = (gl as WebGLRenderingContext).getParameter(dbg.UNMASKED_RENDERER_WEBGL) as string
      if (/SwiftShader|Software|llvmpipe/i.test(renderer)) return 'low'
    }
    const maxTex = (gl as WebGLRenderingContext).getParameter((gl as WebGLRenderingContext).MAX_TEXTURE_SIZE) as number
    if (maxTex < 4096) return 'low'
    const dpr = window.devicePixelRatio
    const isMobile = /Mobi|Android/i.test(navigator.userAgent)
    if (isMobile || dpr >= 2.5) return 'medium'
    return 'high'
  } catch {
    return 'high'
  }
}

export function dprMax(quality: Quality): number {
  return quality === 'low' ? 1 : quality === 'medium' ? 1.25 : 1.75
}

export function bloomEnabled(quality: Quality): boolean {
  return quality === 'high'
}
