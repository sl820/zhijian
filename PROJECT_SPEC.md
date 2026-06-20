# PROJECT_SPEC.md — 志鉴 v2

> ⚠️ **本文件是占位**。v1 的 2262 行详细规划已废弃。
> 完整的 v2 规范由 `docs/ARCHITECTURE.md` 取代（Phase D 完成后写入）。

## 一句话定位

志鉴·家谱星图：33 万家谱人物的三维星系可视化，仿照诗云 Poetry Cloud 架构。

## v2 三大原则

1. **纯静态、永不加后端**（诗云范本）
2. **数据 ETL 离线一次，运行时零计算**
3. **DEVLOG 驱动的迭代节奏**（每个 session 留痕）

## v1 → v2 路径

| v1 资产 | v2 路径 |
|---|---|
| `archive/v1/app/` (FastAPI) | ❌ 不复刻 |
| `archive/v1/frontend_views/` (Vue) | ❌ 不复刻 |
| `scripts/precompute_layout.py` (FA2) | → `pipeline/precompute_layout.py`（复用 + 跑 33 万） |
| `data/layouts/jiapu_v1.npz` (5k) | → `public/layouts/jiapu_v2.npz`（33 万全量） |
| `archive/v1/data_raw/` (RAG seed) | ❌ 不复刻 |
| `archive/v1/scripts/` (早期 ETL) | ❌ 不复刻 |

## 详细规范

待 Phase D 完成时写 `docs/ARCHITECTURE.md`。在此之前以 `CLAUDE.md` + `README.md` + 本文件为执行规范。
