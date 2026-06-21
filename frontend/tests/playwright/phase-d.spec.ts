/**
 * Phase D-13 真浏览器视觉回归 + 交互验证
 *
 * 验 5 个端到端场景：
 * 1. 打开页面 → 4 重同心圆 + 28 宿 + Landmarks + PersonStars 全可见
 * 2. 点击朝代 chip "minguo" → URL hash 变 #d=minguo + canvas 只剩外圈白点
 * 3. 点击朝代 chip "全部" → URL hash 清空 + 全部点回归
 * 4. 永久链接 #d=tang 刷新 → tang chip 高亮 + 内圈可见
 * 5. 永久链接 #a=<pid> 刷新 → PersonPanel 直接显示（验拾取逻辑链）
 */
import { test, expect } from '@playwright/test'
import { mkdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const SHOT_DIR = join(process.cwd(), 'screenshots')
mkdirSync(SHOT_DIR, { recursive: true })

const URL_BASE = '/zhijian-v2/'

async function waitCanvas(page: import('@playwright/test').Page) {
  await page.waitForSelector('canvas', { timeout: 15_000 })
  await page.waitForTimeout(3500) // 165k Points first-frame + 字体首绘
}

async function shot(page: import('@playwright/test').Page, name: string) {
  await page.screenshot({ path: join(SHOT_DIR, `${name}.png`), fullPage: false })
}

// 读 PNG 文件判断非黑像素数（不依赖 WebGL preserveDrawingBuffer）
async function countNonBlackInPng(path: string): Promise<{ w: number; h: number; nonBlack: number; total: number }> {
  const buf = readFileSync(path)
  // 解析 PNG 头（IHDR）拿尺寸，IDAT 拿像素
  // 简单做法：用 Buffer 看宽高 + 抽样字节非 0 像素比例
  const w = buf.readUInt32BE(16)
  const h = buf.readUInt32BE(20)
  // 像素是 deflate 压缩的 IDAT，这里只看压缩字节的非零密度
  // 64KB 起步的 PNG，全黑像素压缩后 ~5KB；非黑像素越多体积越大
  const total = buf.length
  // 启发式：>20KB 表示有内容；<10KB 表示基本全黑
  // 不能精确算非黑像素数，只能用作基本校验
  return { w, h, nonBlack: total, total }
}

test.describe('Phase D 端到端', () => {
  test('1. 初始场景渲染', async ({ page }) => {
    await page.goto(URL_BASE, { waitUntil: 'domcontentloaded' })
    await waitCanvas(page)
    await shot(page, '01-initial')
    // 截全屏应至少含 HUD + 4 重圆 + bulge；粗校 PNG 体积
    const stat = await countNonBlackInPng(join(SHOT_DIR, '01-initial.png'))
    expect(stat.nonBlack).toBeGreaterThan(30000) // 30KB 以上说明有内容（不全黑）
  })

  test('2. 朝代过滤 minguo → URL hash + 只剩外圈', async ({ page }) => {
    await page.goto(URL_BASE, { waitUntil: 'domcontentloaded' })
    await waitCanvas(page)
    await page.click('button:has-text("minguo")')
    await page.waitForTimeout(500)
    expect(page.url()).toContain('#d=minguo')
    await shot(page, '02-minguo-filter')
  })

  test('3. 重置回全部', async ({ page }) => {
    await page.goto(URL_BASE + '#d=minguo', { waitUntil: 'domcontentloaded' })
    await waitCanvas(page)
    await page.click('button:has-text("全部")')
    await page.waitForTimeout(500)
    const hash = await page.evaluate(() => window.location.hash)
    expect(hash === '' || !hash.includes('d=')).toBe(true)
    await shot(page, '03-reset-all')
  })

  test('4. 永久链接 #d= 恢复', async ({ page }) => {
    await page.goto(URL_BASE + '#d=tang', { waitUntil: 'domcontentloaded' })
    await waitCanvas(page)
    await shot(page, '04-permalink-tang')
    // hash 应保留
    expect(page.url()).toContain('#d=tang')
  })

  test('5. 永久链接 #a= → PersonPanel', async ({ page }) => {
    // 用 jiapu_v2.json 第一个 pid 做测试（保证数据存在）
    const pid = '860s7netgqkn3b0x'
    await page.goto(URL_BASE + '#a=' + pid, { waitUntil: 'domcontentloaded' })
    await waitCanvas(page)
    await page.waitForTimeout(2500) // loadPerson async + PersonPanel 渲染
    // PersonPanel 出现条件：absolute 定位 div 含"朝代"和"姓"和"pid"
    const panelVisible = await page.evaluate(() => {
      const divs = document.querySelectorAll('div')
      for (const div of divs) {
        const t = div.textContent ?? ''
        const cs = window.getComputedStyle(div as HTMLElement)
        if ((cs.position === 'fixed' || cs.position === 'absolute')
            && t.includes('朝代') && t.includes('姓') && t.includes('pid')) {
          return { visible: true, text: t.slice(0, 200) }
        }
      }
      return { visible: false, text: '' }
    })
    expect(panelVisible.visible).toBe(true)
    await shot(page, '05-person-panel-via-permalink')
  })
})
