/**
 * precompress.mjs — 预压缩 dist/ 静态资源为 .gz 和 .br
 *
 * 设计目标：
 * - GitHub Pages / nginx / Cloudflare 都支持"同 URL + Accept-Encoding 协商返回 .gz / .br"
 * - 提前离线压缩比 on-the-flight 节省 CPU，部署后访问速度更快
 * - 大文件流式 pipeline 处理，不爆内存
 *
 * 用法：node deploy/precompress.mjs [dist 路径]
 * 默认：相对当前工作目录的 dist/
 *
 * 输出：每个可压缩文件旁生成同名 .gz（gzip level 9）和 .br（brotli level 11）
 * 跳过：小于 1024B（不值得压缩）、大于 100MB（太大、CPU 不划算）
 *       非白名单后缀（已压缩格式如 .png/.jpg/.woff2 再压也白搭）
 */

import { createReadStream, createWriteStream, statSync, readdirSync } from 'node:fs'
import { join, extname, relative, sep } from 'node:path'
import { createGzip, createBrotliCompress, constants } from 'node:zlib'
import { pipeline } from 'node:stream/promises'

const arg2 = process.argv[2]
const DIST = arg2 && arg2.length > 0 ? arg2 : join(process.cwd(), 'dist')

const COMPRESSIBLE = new Set([
  '.html', '.js', '.mjs', '.css', '.json',
  '.svg', '.xml', '.txt', '.map',
])
const MIN_SIZE = 1024
const MAX_SIZE = 100 * 1024 * 1024

console.log(`[precompress] dist: ${DIST}`)

async function walk(dir) {
  const out = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      out.push(...(await walk(full)))
    } else if (entry.isFile()) {
      out.push(full)
    }
  }
  return out
}

function shouldCompress(file, size) {
  if (size < MIN_SIZE || size > MAX_SIZE) return false
  return COMPRESSIBLE.has(extname(file).toLowerCase())
}

async function compressOne(file) {
  const size = statSync(file).size
  if (!shouldCompress(file, size)) return { skipped: true, file, size }

  await pipeline(
    createReadStream(file),
    createGzip({ level: 9 }),
    createWriteStream(file + '.gz'),
  )
  await pipeline(
    createReadStream(file),
    createBrotliCompress({
      params: { [constants.BROTLI_PARAM_QUALITY]: 11 },
    }),
    createWriteStream(file + '.br'),
  )
  return { compressed: true, file, size }
}

const t0 = Date.now()
const files = await walk(DIST)
let compressed = 0
let skipped = 0
let failed = 0
let totalIn = 0
let totalGz = 0
let totalBr = 0

for (const file of files) {
  try {
    const r = await compressOne(file)
    if (r.compressed) {
      const gzSize = statSync(r.file + '.gz').size
      const brSize = statSync(r.file + '.br').size
      const rel = relative(DIST, r.file).split(sep).join('/')
      const ratioGz = ((1 - gzSize / r.size) * 100).toFixed(1)
      const ratioBr = ((1 - brSize / r.size) * 100).toFixed(1)
      console.log(
        `[precompress] ${rel}  ${(r.size / 1024).toFixed(1)}KB -> ` +
        `gz ${(gzSize / 1024).toFixed(1)}KB (-${ratioGz}%) ` +
        `br ${(brSize / 1024).toFixed(1)}KB (-${ratioBr}%)`,
      )
      compressed++
      totalIn += r.size
      totalGz += gzSize
      totalBr += brSize
    } else {
      skipped++
    }
  } catch (err) {
    failed++
    console.error(`[precompress] FAIL ${relative(DIST, file)}: ${err.message}`)
  }
}

const dt = ((Date.now() - t0) / 1000).toFixed(1)
const overallGz = totalIn > 0 ? ((1 - totalGz / totalIn) * 100).toFixed(1) : '0'
const overallBr = totalIn > 0 ? ((1 - totalBr / totalIn) * 100).toFixed(1) : '0'
console.log('')
console.log(
  `[precompress] done in ${dt}s — ` +
  `${compressed} compressed, ${skipped} skipped, ${failed} failed`,
)
console.log(
  `[precompress] total: ${(totalIn / 1024 / 1024).toFixed(2)}MB -> ` +
  `gz ${(totalGz / 1024 / 1024).toFixed(2)}MB (-${overallGz}%) ` +
  `br ${(totalBr / 1024 / 1024).toFixed(2)}MB (-${overallBr}%)`,
)
