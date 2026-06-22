# HANDOFF.md — 志鉴 v2 跨 session 上下文接力

> 最近 60KB 的 session 摘要接力。本文件由 lead agent 在每个 session 末尾追加。

---

## Session 1 (2026-06-20) 摘要

**核心**：v2 启动 + 模板分析 + 工作树冻结 + 大爆炸清理。

**v1 → v2 决策**：
- 前端：Vue 3 → React 18 + TS（彻底诗云化）
- 后端：FastAPI + ChromaDB + Ollama → **纯静态 + 丢所有后端**
- 差异化亮点（RAG/OCR/research/insights_engine）：**全部丢弃**
- 工作流：先 commit v1 dirty → push → 开 `zhijian-v2-shiyun-style` 分支 → 大爆炸清理

**当前分支状态**：
```
master 9d34a5d (4 commits ahead of remote pre-push)
  └── zhijian-v2-shiyun-style 40d754d (HEAD, 6 commits ahead of master)
       ├── 2617f38 feat(nebula): v5 续作 + ClusterRenderer/CoordinateRings/NodeRegistry 池化
       ├── 293c0a0 fix(backend): layout service IndexError + jiapu SELECT 字段对齐 + precompute FA2
       ├── 4d74911 feat(r9): narrative 研究叙事模式 + research API + demo router
       ├── 9d34a5d chore(frontend): vue 杂项调整 + AGENTS.md
       ├── f90f320 chore(archive): v1 归档 + 项目瘦身
       └── 40d754d docs(v2): CLAUDE.md/README.md/AGENTS.md/PROJECT_SPEC.md 重写 + .gitignore v2 适配
```

**目录现状**：
- `archive/v1/` — FastAPI + Vue 业务视图 + RAG seed 归档
- `scripts/precompute_layout.py` — FA2 真布局脚本（v2 复用为 `pipeline/precompute_layout.py`）
- `data/layouts/jiapu_v1.npz` — 5k FA2 预布局（untracked, gitignored；v2 跑 33 万全量）
- `frontend/src/components/nebula/*.js` — Vue 实现（保留作参考，v2 React 重写）
- `docs/DEVLOG.md` + 本文件 — DEVLOG 起步

**诗云模板对照要点**（每点都对 v2 有具体动作）：
1. 数据双射（rank/unrank + Feistel）→ **PoC**，生产用志鉴 FA2
2. Range 分片 → **直接复刻** → `persons/{bucket}.json` + `idx.json`
3. 4 稳定接口 → schema 改名（poet→person, poem→line）
4. 朝代同心壳 → 直接复刻（径向）
5. 角向 + z 轴 → **家谱新增**：姓氏 hash + 世代 z
6. 关系网 → parent/child/spouse/adopt（结构化边，**不需要 NLP 挖**）
7. 字/号别名表 → 诗云 250 条 → **家谱数千条**
8. 三种 pull 模式 → 重新定义语义（纯随机支系 / 谱例约束 / 常用字）
9. 永久链接 → `#a=` / `#p=` / `#l=` / `#g=`
10. DEVLOG + HANDOFF → 100% 复刻（即本文档）

**未完成 / 挂账**：
- Phase B 数据 ETL（pipeline/ 全部脚本）
- Phase C 引擎层（src/engine/）
- Phase D 前端骨架（src/{three,ui,state,data}/）
- Phase E 部署（deploy/）
- Phase F docs/{ARCHITECTURE,FRONTEND_GUIDE,ENGINE_API,DATA_CONTRACT,DEPLOY,PIPELINE,DATA_AUDIT}.md

**关键技术决策**：
- 数据根：`D:/上海图书馆开放数据/data/shlib_jiapu.db`（仓库外绝对路径）
- 前端开发端口：5173（Vite 默认）
- 后端：❌ 无
- 部署目标：GitHub Pages（sl820.github.io/zhijian-v2/）

**已识别风险**：
- 数据源绝对路径硬编码 → v2 必须用 `process.env` 或相对定位
- npm/pnpm 选型 → 待 Phase D 决定（诗云用 npm）
- 33 万 FA2 precompute 性能（5k 版已知 ~12min，33 万估 ~12 小时？）→ Phase B 实测

**已知约束**：
- 用户硬红线：git push / rebase / reset --hard / npm publish 都要先问
- 工作流偏好：先 commit 再验证
- 验证门槛：tsc + vitest + vite build 全绿

---

## Session 3 (2026-06-21) 摘要

**核心**：Phase C 引擎层 TS 完成。

**v2 → Phase C 决策**：
- 工程基线：v1 Vue 全栈 → React 18.3 + TS 5.6 + Vite 5.4 + three 0.169 + @react-three/fiber + zustand 4.5 + vitest 2.1
- 包管理器：npm（跟诗云）
- Vite base：`/zhijian-v2/`（GH Pages 子路径）
- Layout 数据：NPZ（Python 源）→ JSON（前端消费），`pipeline/npz_to_layout_json.py` 一次性生成 27MB jiapu_v2.json

**4 稳定接口就位**：
1. `src/data/load.ts` — loadPerson / loadLine / loadAncestors / searchSurname（Range fetch）
2. `src/engine/engineApi.ts` — pullAt (3 mode) / unrankPerson / rankPerson / neighborsOf
3. `src/data/position.ts` — personPosition(pid) → {dynasty, angle, z}（读 jiapu_v2.json）
4. `src/state/store.ts` — zustand + syncPermalink + parsePermalink

**测试**：
- ✅ tsc --noEmit 0 错
- ✅ vitest 14/14 PASS（findBucket 5 + Feistel 6 + rank/unrank 3）
- ✅ vite build 706ms，dist 147KB (gzip 48KB)

**Feistel 实现要点**：
- 4 rounds 16-bit halves, 32-bit total
- `feistelInv` 是真正的反向（keys 倒序 + swap 方向反），不是 involution
- uniformity 10000 samples 16 桶 < 1.5x 均匀

**新增文件**：
- frontend/src/{main.tsx, App.tsx, types/*.ts, data/{load,position,load.test}.ts, engine/{scatter,engineApi,engine.test}.ts, state/store.ts}
- frontend/{package.json, tsconfig.json, vite.config.ts, index.html} 全重写
- pipeline/npz_to_layout_json.py
- public/layouts/jiapu_v2.json (27MB, committed)

**删除**：frontend/vite.config.js (v1 Vue 残留)

**未完成 / 挂账**：
- Phase D: React 18 + Three.js 前端骨架（Galaxy / PersonStars / RelationLines / FlyControls / SearchPanel / PersonPanel / LinePanel / Cinema / HUD）
- Phase E: 部署（precompress / nginx / og-inject / github-pages.yml + 部署到 sl820.github.io/zhijian-v2/）
- Phase F: 文档（ARCHITECTURE / FRONTEND_GUIDE / ENGINE_API / DATA_CONTRACT / DEPLOY / PIPELINE / DATA_AUDIT）

**v1 残留**（未清理，等 Phase D 整块处理）：
- frontend/src/{App.vue, components/, views/, router/, services/, stores/, styles/, constants/}
- 4 稳定接口新文件不与 v1 冲突（不同子目录）

---

## Session 4 (2026-06-21) 摘要

**核心**：Phase D 3D 骨架完成（React 18 + Three.js）。

**Phase D 决策**：
- 渲染：Points + ShaderMaterial（165k 节点），共享 geometry，朝代过滤走 `aSize = 0`
- 拾取：同 group Points + `e.index` + Canvas raycaster threshold=15（弃 GPU color-id 拾取）
- 字体：drei <Text> + unicode-font-resolver CDN（Phase D-12 自托管）
- 朝代色：v1 11 朝 hue 调色板（THEME.ink/gold + 16 朝）
- 坐标：x,y=disc 平面，z=世代极薄（[-1.5, 17.5]），camera (0,0,3500) 俯视，所有 group 绕 Z 转

**关键 bug 修复**（4 个）：
1. `gl_PointSize` 公式常数 300→25000（距离 6500 原来 0.046px→现在 7+ px）
2. FlyControls dir 公式 z 分量加负号（默认朝 -Z，不是 +Z）
3. CoordinateRings/Landmarks 平面从 XZ 改 XY（跟数据对齐）
4. 拾取 `e.instanceId` → `e.index`（Points 非 InstancedMesh）；删整个 pick shader

**测试**：
- ✅ tsc --noEmit 0 错
- ✅ vitest 14/14 PASS（Phase C 引擎层没坏）
- ✅ vite build 3.48s，dist 1.1MB (gzip 318KB)
- ✅ Dev server 渲染验证：4 重同心圆 + 28 宿 + 165k 点 + bulge + Landmarks 螺旋 wedge
- ✅ 朝代过滤：点 minguo → URL `#d=minguo` 同步，最外圈白点 only
- ⚠️ Canvas hover/click 真浏览器测试未跑（MCP synthetic dispatch 限制）

**新增文件**：
- frontend/src/three/{galaxyParams, detectQuality, positions, xingye, Galaxy, CoordinateRings, Landmarks, PersonStars, FlyControls}.{ts,tsx}
- frontend/src/ui/{HUD, PersonPanel}.tsx

**修改**：
- frontend/src/App.tsx — Canvas 入口 + raycaster threshold
- frontend/vite.config.ts — publicDir → ../public
- frontend/package.json — 加 @react-three/drei

**未完成 / 挂账**（按优先级）：
- Phase D-7+ : KinshipLines / LinePanel / SearchPanel / Cinema / Onboarding
- Phase D-12 : 字体自托管
- Phase D-13 : Playwright 视觉回归
- Phase D-14 : postprocessing Bloom
- v1 Vue 残留删除（**建议下个 session 一并清**）
- Phase E : 部署（precompress/nginx/og-inject/github-pages.yml + sl820.github.io/zhijian-v2/）
- Phase F : 文档 6 篇（ARCHITECTURE / FRONTEND_GUIDE / ENGINE_API / DATA_CONTRACT / DEPLOY / PIPELINE / DATA_AUDIT）


## Session 5 (2026-06-22) 摘要

**核心**：Phase D-9 SearchPanel 完成（4 tab 搜索先祖 + camera fly + 并行 fetch）。

**Phase D-9 决策**：
- 4 tab：姓（searchSurname + CN→pinyin 映射）/ 名（searchByName 子串）/ 支系（searchByLine 按 family_uri 去重）/ 朝代（getDynastyCounts 列 16 朝代 + 人数）
- 并行 fetch：83 桶 `Promise.all` 并行拉（之前串行 > 6s，并行后 ~1.5s）
- camera fly：store `flyTarget` → FlyControls subscribe → useFrame lerp 4.0 → 距离 < 5 清空。用户拖拽/滚轮/再按 WASD 自动取消
- 快捷键：`/` 打开 SearchPanel + `Esc` 关闭

**关键 bug 修复**（3 个）：
1. `family_name` 字段是 pinyin（'han'）不是中文（'韩'）→ 加载时建 cnToPinyin map 一次永久
2. TS `RaycasterParameters` 类型严格 → `as never`
3. layout `Position` 已预计算 x/y/z → 不现场算 `r * cos θ`（避免浮点误差）

**测试**：
- ✅ tsc --noEmit 0 错
- ✅ vitest 14/14 PASS（不变）
- ✅ vite build 3.66s，dist 1.1MB (gzip 320KB)
- ✅ Playwright 6/6 PASS（46.7s，含原 5 + 新 1）

**新增文件**：
- frontend/src/ui/SearchPanel.tsx

**修改**：
- frontend/src/data/load.ts — searchByName/searchByLine/getAllFamilyNames/getDynastyCounts + cnToPinyin + 并行 fetch
- frontend/src/data/position.ts — personWorldPos 用 layout 预计算
- frontend/src/state/store.ts — searchOpen + setSearchOpen
- frontend/src/three/FlyControls.tsx — flyTarget subscribe + lerp + cancelFly
- frontend/src/ui/HUD.tsx — 搜按钮
- frontend/src/App.tsx — mount SearchPanel + / 快捷键 + Esc 关闭
- frontend/tests/playwright/phase-d.spec.ts — 加 test 6

**未完成 / 挂账**（按优先级）：
- Phase E : 部署（precompress/nginx/og-inject/github-pages.yml + sl820.github.io/zhijian-v2/）
- Phase F : 文档 6 篇（ARCHITECTURE / FRONTEND_GUIDE / ENGINE_API / DATA_CONTRACT / DEPLOY / PIPELINE / DATA_AUDIT）
- Phase D-7/8/10/11/12/14 延后 : KinshipLines / LinePanel / Cinema / Onboarding / 字体自托管 / Bloom

---
