# CLAUDE.md — 志鉴 v2

## 项目定位

志鉴·家谱星图（Jiapu XingTu）。把上海图书馆开放数据中 33 万家谱人物以三维星系方式呈现：每位先祖是一颗星，每条支系有自己的空间坐标。仿照 [`Cohenjikan/shiyun`](https://github.com/Cohenjikan/shiyun) 诗云 Poetry Cloud 的纯静态架构。

**v1 已归档到 `archive/v1/`**（FastAPI + Vue 3 + ChromaDB + Ollama RAG）。本分支 `zhijian-v2-shiyun-style` 是 v2 重做。

## 技术栈

- **前端**：React 18 + TypeScript + Vite（弃 Vue 3）
- **3D**：three.js + @react-three/fiber + drei + postprocessing
- **状态**：zustand
- **辅助**：opencc-js（简繁）、pinyin-pro（拼音）
- **构建门禁**：`tsc + vitest + vite build` 全绿
- **部署**：纯静态（GitHub Pages），HTTP Range 取片
- **数据 ETL**：Python 3.10+ 离线 pipeline（不部署）

## 核心架构：诗云 4 稳定接口

```
src/
├── engine/         # 引擎层：FA2 真布局（生产）+ rank/unrank 双射（PoC）
├── data/           # 数据契约 + Range 取片 + 加载
├── three/          # 3D 渲染样壳（可任意重写）
├── ui/             # UI 样壳（可任意重写）
├── state/          # zustand store + permalink
├── App.tsx
└── main.tsx
```

四个稳定边界（**任何重写都不能破坏**）：
1. `data/load.ts` — `loadPerson / loadLine / loadAncestors / searchSurname`
2. `engine/engineApi.ts` — `pullAt / unrankPerson / rankPerson`
3. `data/position.ts` — `personPosition(personId) → {dynasty, angle, z}`
4. `state/store.ts` — zustand：selectedPerson / selectedLine / flyTarget / filters

## 关键约定

- **纯静态、永不加后端**。若要 RAG/LLM，重新评估是否值得，**默认不做**。
- **数据 ETL 离线跑一次**，产物（`public/persons/*.json` + `public/layouts/jiapu_v2.npz`）进 git 或 CDN，不在运行时计算。
- **永久链接**：`#a=<personId>` / `#p=<谱名>.<代数>.<支号>` / `#l=<lineId>` / `#g=<generation>`
- **三种 pull 模式**（家谱版）：
  - 「纯随机支系」N^代数笛卡尔积
  - 「谱例约束」嫡长子继承 / 不娶同姓
  - 「名/字常用字」按谱中真出现过的字过滤
- **门禁**：每个 session 结束必须 `npm test && npm run build` 全绿，写完 DEVLOG 才能 push
- **数据根（仓库外）**：`D:/上海图书馆开放数据/data/shlib_jiapu.db`（1.68M persons / 13K relations / 588K cbdb_relations）

## 工作流

1. 接到任务先看 `docs/DEVLOG.md` + `docs/devlog/HANDOFF.md` 上下文
2. 大改动先 Plan Mode（plan 文件存 `~/.claude/plans/`）
3. 改完跑验证（`npm test && npm run build`）
4. 写 DEVLOG session 增量
5. **先 commit 再验证**（按用户偏好）
6. push 前问（CLAUDE.md 红线）

## 与 v1 的关系

| v1 资产 | v2 处置 |
|---|---|
| `scripts/precompute_layout.py` (FA2 真布局) | 复制到 `pipeline/precompute_layout.py`，跑 33 万全量 |
| `data/layouts/jiapu_v1.npz` (5k FA2) | v2 跑 33 万，输出 `public/layouts/jiapu_v2.npz` |
| `frontend/src/components/nebula/*.js` (Vue) | 仅作参考，v2 用 React + @react-three 重写 |
| `app/` (FastAPI 全部) | 归档到 `archive/v1/app/`，v2 不部署 |
| `app/rag/`、`app/ocr/`、`app/research/` | 归档到 `archive/v1/`，v2 不复刻 |
| `chroma_zhijian/` (67MB RAG) | 删除（gitignored） |
| `.venv_paddle/` (5.9GB) | 删除（gitignored） |

## 工程铁律

- 改完跑 `npm test && npm run build`，不只改不验
- 不注释报错、不加绕过标记，找根因
- 密钥/token/密码不进代码、不进 commit、不进日志
- 大改动前先 Plan Mode，我确认后再动手
- 不做"为未来可能需求"设计的过度抽象
- 不写无意义注释（注释"做什么"的不写；"为什么这样做"的非显然约束才写）

## 验证命令

```bash
# 前端测试 + 构建
cd /d/zhijian && npm test
cd /d/zhijian && npm run build

# 数据 ETL（Python 离线）
cd /d/zhijian && python pipeline/extract_persons.py
cd /d/zhijian && python pipeline/pack_data.py
cd /d/zhijian && python pipeline/precompute_layout.py    # 33 万 FA2 全量
cd /d/zhijian && python pipeline/validate_pipeline.py    # 单测 + 全量一致性

# 启动前端
cd /d/zhijian && npm run dev          # http://localhost:5173
```
