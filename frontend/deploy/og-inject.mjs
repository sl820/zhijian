/**
 * og-inject.mjs — 给 dist/index.html 注入 OG / Twitter Card / favicon meta
 *
 * 设计目标：
 * - 社交分享卡片：分享到微信/微博/Twitter/LinkedIn 时显示「志鉴·家谱星图 + 描述 + 图」
 * - iOS/Android PWA：apple-touch-icon + theme-color
 * - 复制 build 时的 site URL 到 canonical + og:url，避免部署后 og:url 写死
 *
 * 关键 meta：
 * - og:title, og:description, og:image, og:url, og:type
 * - twitter:card (summary_large_image), twitter:image
 * - canonical link
 * - apple-touch-icon
 *
 * og-image.png 来自 deploy/og-image.png（1200×630，<200KB）
 *
 * 用法：node deploy/og-inject.mjs [dist 路径] [site URL]
 * 例：node deploy/og-inject.mjs dist https://sl820.github.io/zhijian/
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const DIST = process.argv[2] ?? join(process.cwd(), 'dist')
const SITE_URL = (process.argv[3] ?? 'https://sl820.github.io/zhijian/').replace(/\/$/, '')
const INDEX = join(DIST, 'index.html')

if (!existsSync(INDEX)) {
  console.error(`[og-inject] ${INDEX} not found, run vite build first`)
  process.exit(1)
}

let html = readFileSync(INDEX, 'utf8')

const title = '志鉴·家谱星图 — 33 万先祖的 3D 星系'
const description = '把上海图书馆 33 万家谱人物以三维星系方式呈现：每位先祖是一颗星，每条支系有自己的空间坐标。仿诗云 Poetry Cloud 架构，纯静态 + 3D WebGL。'
// SITE_URL 已 strip 末尾 /，拼接资源路径时要补回
const ogImage = `${SITE_URL}/og-image.png`
const themeColor = '#0a0e1f'

const tags = [
  { name: 'description', content: description },
  { name: 'theme-color', content: themeColor },
  { name: 'author', content: 'sl820' },

  // Open Graph (Facebook / LinkedIn / 微信 / 微博)
  { property: 'og:type', content: 'website' },
  { property: 'og:site_name', content: '志鉴·家谱星图' },
  { property: 'og:title', content: title },
  { property: 'og:description', content: description },
  { property: 'og:url', content: SITE_URL + '/' },
  { property: 'og:image', content: ogImage },
  { property: 'og:image:width', content: '1200' },
  { property: 'og:image:height', content: '630' },
  { property: 'og:locale', content: 'zh_CN' },

  // Twitter Card
  { name: 'twitter:card', content: 'summary_large_image' },
  { name: 'twitter:title', content: title },
  { name: 'twitter:description', content: description },
  { name: 'twitter:image', content: ogImage },
]

const linkTags = [
  { rel: 'canonical', href: SITE_URL + '/' },
  { rel: 'icon', href: 'favicon.svg', type: 'image/svg+xml' },
  { rel: 'apple-touch-icon', href: 'apple-touch-icon.png', sizes: '180x180' },
]

const metaTagsHtml = tags.map((t) => {
  const attr = t.name ? 'name' : 'property'
  const key = t.name ?? t.property
  return `<meta ${attr}="${key}" content="${escapeAttr(t.content ?? '')}">`
}).join('\n    ')

const linkTagsHtml = linkTags.map((l) => {
  const attrs = [`rel="${l.rel}"`, `href="${escapeAttr(l.href)}"`]
  if (l.type) attrs.push(`type="${l.type}"`)
  if (l.sizes) attrs.push(`sizes="${l.sizes}"`)
  return `<link ${attrs.join(' ')}>`
}).join('\n    ')

function escapeAttr(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')
}

// 幂等：先剥除上次 og-inject 注入的整块（用 og-inject 注释包裹），
// 避免 deploy:local 重复跑时 meta 重复堆叠
html = html.replace(/\s*<!-- og-inject-start -->[\s\S]*?<!-- og-inject-end -->/g, '')

// 在 <title> 之后注入（用 og-inject 注释包裹，便于下次替换整段）
const block = `<!-- og-inject-start -->\n    ${metaTagsHtml}\n    ${linkTagsHtml}\n    <!-- og-inject-end -->`
html = html.replace(/(<title>.*?<\/title>\s*)/s, `$1\n    ${block}\n`)

writeFileSync(INDEX, html)
console.log(`[og-inject] injected ${tags.length} meta + ${linkTags.length} link tags into index.html`)
console.log(`[og-inject] site URL: ${SITE_URL}`)
console.log(`[og-inject] og-image: ${ogImage}`)
