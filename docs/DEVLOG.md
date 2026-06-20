# DEVLOG.md — 志鉴 v2 主编年史

> 仿照诗云 [Cohenjikan/shiyun DEVLOG](https://github.com/Cohenjikan/shiyun/blob/main/docs/DEVLOG.md) 的"每个 session 留痕"模式。
> 每篇 session 文档：`docs/devlog/YYYY-MM-DD-session-N.md`。

## Sessions

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

**挂账**：
- [ ] Phase B: pipeline ETL 脚本（extract_persons / extract_relations / build_dynasties / build_surnames / build_name_lexicon / pack_data / precompute_layout / validate_pipeline）
- [ ] Phase B: 33 万 FA2 全量 precompute（补完 M5 遗留）
- [ ] Phase C: 引擎层 TypeScript（FA2 wrapper + 双射 PoC + scatter + engineApi）
- [ ] Phase D: React 18 + Three.js 前端骨架（Galaxy / PersonStars / RelationLines / FlyControls / gpuPick / StarFieldBackground）
- [ ] Phase D: UI 样壳（SearchPanel / PersonPanel / LinePanel / Cinema / HUD）+ zustand store + permalink
- [ ] Phase E: deploy/ 三件套（precompress / nginx / og-inject / github-pages.yml）
- [ ] Phase F: docs/{ARCHITECTURE, FRONTEND_GUIDE, ENGINE_API, DATA_CONTRACT, DEPLOY, PIPELINE, DATA_AUDIT}.md

## 协议

- 每 session 写一篇 `docs/devlog/YYYY-MM-DD-session-N.md`
- 主 DEVLOG 汇总指针 + 关键决策
- HANDOFF.md 存跨 session 上下文接力（最近 60KB）
- 验证门槛：每个 session 结束必须 `npm test && npm run build` 全绿

## 引用

- 诗云 DEVLOG 范本：https://github.com/Cohenjikan/shiyun/blob/main/docs/DEVLOG.md
- 诗云 HANDOFF 范本：https://github.com/Cohenjikan/shiyun/blob/main/docs/devlog/HANDOFF.md
