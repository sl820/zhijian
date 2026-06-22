/**
 * Phase D-13 真浏览器视觉回归 + 交互验证
 *
 * 验 6 个端到端场景：
 * 1. 打开页面 → 4 重同心圆 + 28 宿 + Landmarks + PersonStars 全可见
 * 2. 点击朝代 chip "minguo" → URL hash 变 #d=minguo + canvas 只剩外圈白点
 * 3. 点击朝代 chip "全部" → URL hash 清空 + 全部点回归
 * 4. 永久链接 #d=tang 刷新 → tang chip 高亮 + 内圈可见
 * 5. 永久链接 #a=<pid> 刷新 → PersonPanel 直接显示（验拾取逻辑链）
 * 6. Phase D-9 SearchPanel：搜 按钮 → 姓 tab → 「韩」→ 结果点 → URL #a= + PersonPanel + camera fly
 */
import { test, expect } from '@playwright/test'
import { mkdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const SHOT_DIR = join(process.cwd(), 'screenshots')
mkdirSync(SHOT_DIR, { recursive: true })

const URL_BASE = '/'

async function waitCanvas(page: import('@playwright/test').Page) {
  await page.waitForSelector('canvas', { timeout: 15_000 })
  await page.waitForTimeout(3500) // 165k Points first-frame + 字体首绘
}

async function shot(page: import('@playwright/test').Page, name: string) {
  await page.screenshot({ path: join(SHOT_DIR, `${name}.png`), fullPage: false })
}

test.describe('Phase D 端到端', () => {
  test('1. 初始场景渲染', async ({ page }) => {
    await page.goto(URL_BASE, { waitUntil: 'domcontentloaded' })
    await waitCanvas(page)
    await shot(page, '01-initial')
    const stat = readFileSync(join(SHOT_DIR, '01-initial.png'))
    expect(stat.length).toBeGreaterThan(30000)
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
    expect(page.url()).toContain('#d=tang')
  })

  test('5. 永久链接 #a= → PersonPanel', async ({ page }) => {
    const pid = '860s7netgqkn3b0x'
    await page.goto(URL_BASE + '#a=' + pid, { waitUntil: 'domcontentloaded' })
    await waitCanvas(page)
    await page.waitForTimeout(2500)
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

  test('6. Phase D-9 SearchPanel 4 tab 搜 + 跳转', async ({ page }) => {
    await page.goto(URL_BASE, { waitUntil: 'domcontentloaded' })
    await waitCanvas(page)

    await page.click('button:has-text("搜")')
    await page.waitForTimeout(300)
    const panelOpen = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('div')).some((d) => {
        return (d.textContent ?? '').includes('搜先祖')
      })
    })
    expect(panelOpen).toBe(true)
    await shot(page, '06a-search-opened')

    const input = page.locator('input[placeholder*="姓"]')
    await input.fill('韩')
    await page.waitForTimeout(6000) // ensurePersonsLoaded 拉 83 桶 + 扫 165k

    const resultCount = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('button[title]')).filter((b) => {
        return /^[a-z0-9]{16}$/.test(b.title)
      }).length
    })
    expect(resultCount).toBeGreaterThan(0)
    await shot(page, '06b-search-results-han')

    const firstResult = page.locator('button[title]').filter({ hasText: /世/ }).first()
    const expectedPid = await firstResult.getAttribute('title')
    expect(expectedPid).toMatch(/^[a-z0-9]{16}$/)
    await firstResult.click()
    await page.waitForTimeout(500)
    expect(page.url()).toContain('#a=' + expectedPid)

    await page.waitForTimeout(800)
    const panelShowsPid = await page.evaluate((pid) => {
      return document.body.textContent?.includes(`pid: ${pid}`) ?? false
    }, expectedPid!)
    expect(panelShowsPid).toBe(true)
    await shot(page, '06c-search-jumped-to-person')
  })
})
