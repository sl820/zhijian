# DEVLOG.md — 志鉴 v2 主编年史

> 仿照诗云 [Cohenjikan/shiyun DEVLOG](https://github.com/Cohenjikan/shiyun/blob/main/docs/DEVLOG.md) 的"每个 session 留痕"模式。
> 每篇 session 文档：`docs/devlog/YYYY-MM-DD-session-N.md`。

## Sessions

### 2026-06-21 · Session 3 · Phase C 引擎层 TS 完成

**触发**：Phase B 数据就绪后，启动 Phase C 引擎层（4 稳定接口 TypeScript 实现）。

**关键决策**：
- D15: 前端栈定型 React 18.3 + TS 5.6 + Vite 5.4 + three 0.169 + @react-three/fiber + zustand 4.5 + vitest 2.1
- D16: vite base = `/zhijian-v2/`（GH Pages 子路径）
- D17: layout 数据走 JSON（`public/layouts/jiapu_v2.json` 27MB）— 不让浏览器解析 NPZ
- D18: 4 稳定接口路径固化（CLAUDE.md 红线）：data/load.ts + engine/engineApi.ts + data/position.ts + state/store.ts
- D19: Feistel 用 4 轮 16-bit halves，feistelInv 是真正的反向（keys 倒序 + swap 方向反）— 不是 involution
- D20: pullAt PoC 用 placeholder（mode 解析 + 接口签名，Phase D 接完整实现）

**变更**：
- 11 个新文件（src/ 4 稳定接口 + 5 类型 + 2 测试 + main + App）
- 4 个工程基线重写（package.json / tsconfig.json / vite.config.ts / index.html）
- 1 个 v1 残留删除（vite.config.js）
- 1 个数据产物（public/layouts/jiapu_v2.json 27MB，committed）
- 1 个 ETL 辅助脚本（pipeline/npz_to_layout_json.py）

**验证**：✅ tsc 0 错 · ✅ vitest 14/14 PASS · ✅ vite build 706ms 出 dist 147KB (gzip 48KB) · ⏳ Phase D 启动条件具备

**挂账**：
- [ ] Phase D: React 18 + Three.js 前端骨架（Galaxy / PersonStars / RelationLines / FlyControls / SearchPanel / PersonPanel / LinePanel / Cinema / HUD）
- [ ] Phase E: deploy/ 三件套 + 部署到 sl820.github.io/zhijian-v2/
- [ ] Phase F: docs/{ARCHITECTURE, FRONTEND_GUIDE, ENGINE_API, DATA_CONTRACT, DEPLOY, PIPELINE, DATA_AUDIT}.md

详细 Session 3 文档：`docs/devlog/2026-06-21-session-3.md`

### 2026-06-21 · Session 2 · Phase B 数据 ETL 完成

**触发**：Phase A 工作树冻结后，启动 Phase B 数据 ETL pipeline。

**关键决策**：
- D8: 朝代归并 3121 → 16 key（取复合字符串中第一个朝代 + 细分朝代归主朝代）
- D9: persons ETL 范围扩到全集 167 万（不是原计划 33 万）— 覆盖 relations 端点全集
- D10: ETL 中间产物不入 git，公共桶 127MB（GH Pages 1GB 限额内）
- D11: 布局从 FA2 改成"朝代径向 + 姓氏角向 + 世代 z"（v2 设计）
- D12: relations 两源合并（person_relations 13k + cbdb_relations 588k → 466k）
- D13: common 姓氏阈值降到 800（81 个 common）
- D14: name_lexicon 用全集 167 万 → 34,801 字 + 12,111 号

**数据画像**：
- persons 1,679,876（全集）/ 165,022（有朝代 = v2 数据上界）
- relations 466,108（端点全集在 persons 内，无悬空）
- 5 个朝代壳承载 93% 数据（明 36.76% / 清 18.19% / 宋 20.63% / 元 11.57% / 唐 5.94%）

**变更**：
- 9 个新文件（pipeline/）
- 5 个 intermediate + 3 个公共数据集
- 1 个布局 NPZ
- 1 个 validator（23/23 PASS）

**验证**：✅ validate_pipeline.py 23/23 PASS · ✅ 总 ETL ~9 分钟 · ⏳ Phase C 启动条件具备

**挂账**：
- [ ] Phase C: 引擎层 TS（4 稳定接口 + 双射 PoC + scatter）
- [ ] Phase D: React 18 + Three.js 前端骨架（Galaxy / PersonStars / RelationLines / Range provider）
- [ ] Phase E: deploy/ 三件套（precompress / nginx / og-inject / github-pages.yml）
- [ ] Phase F: docs/{ARCHITECTURE, FRONTEND_GUIDE, ENGINE_API, DATA_CONTRACT, DEPLOY, PIPELINE, DATA_AUDIT}.md

详细 Session 2 文档：`docs/devlog/2026-06-21-session-2.md`

### 2026-06-20 · Session 1 · v2 启动 + 模板分析 + 工作树冻结

**触发**：用户看到 [Cohenjikan/shiyun](https://github.com/Cohenjikan/shiyun) 诗云项目后，决定仿照其架构重做志鉴，仅替换数据层（家谱替换诗歌）。

**关键决策**（与用户 4 问对齐）：
1. 前端栈：Vue 3 → React 18 + TypeScript（彻底诗云化）
2. 后端：FastAPI → 纯静态 + 丢 FastAPI（丢 RAG/OCR/research）
3. 工作树：先 commit 现有 27 modified + 23 untracked 到 master → push → 开新分支 `zhijian-v2-shiyun-style` → 大爆炸清理
4. 差异化：全部丢弃，做纯净诗云范本

**诗云 8 维度对照**（详见 session 1 文档）：
- 数据双射：保留为 PoC 验证引擎边界；**生产用志鉴 FA2 真布局**
- 静态 Range 分片：直接复刻 → `persons/{bucket}.json` + `idx.json`
- 4 稳定接口：直接复刻 schema（poet→person, poem→line）
- 朝代同心壳 + 姓氏 hash + 世代 z 轴（家谱新增第三维）
- 赠诗网络 → 关系网（结构化 parent/child/spouse/adopt）
- 字/号别名表：诗云 250 条 → 家谱数千条
- 三种 pull 模式：纯随机支系 / 谱例约束 / 常用字
- DEVLOG：100% 复刻（即本文档）
- 永久链接：`#a=` / `#p=` / `#l=` / `#g=`

**变更**：
- `9d34a5d` chore(frontend): vue 杂项调整 + AGENTS.md
- `4d74911` feat(r9): narrative 研究叙事模式 + research API + demo router
- `293c0a0` fix(backend): layout service IndexError + jiapu SELECT 字段对齐 + precompute FA2
- `2617f38` feat(nebula): v5 续作 + ClusterRenderer/CoordinateRings/NodeRegistry 池化
- `f90f320` chore(archive): v1 归档 + 项目瘦身
- `40d754d` docs(v2): CLAUDE.md/README.md/AGENTS.md/PROJECT_SPEC.md 重写 + .gitignore v2 适配

**验证**：✅ git tree clean · ✅ push 到 origin 成功 · ✅ 新分支就绪 · ⏳ Phase B 启动条件具备

## 协议

- 每 session 写一篇 `docs/devlog/YYYY-MM-DD-session-N.md`
- 主 DEVLOG 汇总指针 + 关键决策
- HANDOFF.md 存跨 session 上下文接力（最近 60KB）
- 验证门槛：每个 session 结束必须 `npm test && npm run build` 全绿

## 引用

- 诗云 DEVLOG 范本：https://github.com/Cohenjikan/shiyun/blob/main/docs/DEVLOG.md
- 诗云 HANDOFF 范本：https://github.com/Cohenjikan/shiyun/blob/main/docs/devlog/HANDOFF.md
