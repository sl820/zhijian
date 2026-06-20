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
