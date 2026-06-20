# 志鉴·家谱星图 (Jiapu XingTu) v2

33 万家谱人物的三维星系可视化。仿照 [`Cohenjikan/shiyun`](https://github.com/Cohenjikan/shiyun) 诗云 Poetry Cloud 架构。

**在线 Demo**：（待部署）

## 项目状态

| Phase | 状态 |
|---|---|
| Phase A 工作树冻结 | ✅ 完成（v1 归档 + v2 分支） |
| Phase B 数据 ETL | 🔲 待启动 |
| Phase C 引擎层 | 🔲 待启动 |
| Phase D 前端骨架 | 🔲 待启动 |
| Phase E 部署 | 🔲 待启动 |
| Phase F DEVLOG | 🔄 持续 |

详见 `docs/DEVLOG.md`。

## 快速开始

```bash
# 安装
npm install

# 开发预览
npm run dev          # http://localhost:5173

# 单元测试（引擎 round-trip + 数据加载）
npm test

# 类型检查 + 构建
npm run build

# 数据 ETL（Python 离线脚本，需先激活环境）
python pipeline/extract_persons.py
python pipeline/extract_relations.py
python pipeline/build_dynasties.py
python pipeline/build_surnames.py
python pipeline/build_name_lexicon.py
python pipeline/pack_data.py
python pipeline/precompute_layout.py    # 33 万 FA2 全量
python pipeline/validate_pipeline.py    # 单测 + 全量一致性
```

## 架构

**两层稳定边界** + **三层可重写样壳**：

```
[数据契约] ──┐                          ┌── [three 样壳]
             ├── engineApi (4 稳定接口) ──┤
[数据加载] ──┘                          └── [ui 样壳]
                                                │
                                                └── [state zustand]
```

- **数据契约层**：`data/contract.ts` 定义 schema；`data/load.ts` Range 取片实现
- **引擎层**：`engine/engineApi.ts` 4 个稳定接口（`loadPerson`、`pullAt`、`personPosition`、`store`）
- **三层样壳**（可任意重写）：`src/three/`、`src/ui/`、`src/state/`

## 数据

| 维度 | 值 |
|---|---|
| 数据源 | `D:/上海图书馆开放数据/data/shlib_jiapu.db`（仓库外） |
| 人物数 | 1,684,232（其中家谱约 33 万有效节点） |
| 关系数 | 13K 直接 + 588K CBDB 引用 |
| 部署形式 | 256 个 JSON 桶（每片 ≤ 1 MB）+ FA2 预布局 .npz |

**为什么 33 万不是 168 万**：志鉴 v2 只展示**家谱源**（jiapu）的核心人物。CBDB / dimingzhi / gmwx 等 8 源的数据通过 pipeline 间接聚合，主体仍是 jiapu。

## 与诗云的差异

| 维度 | 诗云 | 志鉴 v2 |
|---|---|---|
| 数据 | 诗歌 | 家谱人物 |
| 节点 | 32,657 诗人 | 33 万先祖 |
| 关系 | 4,849 赠诗弧（NLP 挖） | 结构化 parent/child/spouse/adopt |
| 空间散布 | rank/unrank + Feistel | **FA2 真布局**（家谱天然结构化） |
| 双射 | 生产路径 | **PoC 验证引擎边界** |
| 第三维 | 时间 | **世代 z 轴** |
| 三种 pull 模式 | 纯随机/格律/常用字 | 纯随机支系/谱例约束/常用字 |

诗云的**核心巧思**（数据双射）作为 PoC 验证引擎边界；生产用志鉴 FA2 真布局。家谱天然有结构数据，不需要笛卡尔积穷举。

## 文档

- `docs/ARCHITECTURE.md` — 分层架构
- `docs/FRONTEND_GUIDE.md` — 前端契约
- `docs/ENGINE_API.md` — 引擎接口
- `docs/DATA_CONTRACT.md` — 静态资源 schema
- `docs/DEPLOY.md` — 部署
- `docs/PIPELINE.md` — 数据 ETL
- `docs/DATA_AUDIT.md` — 语料选型
- `docs/DEVLOG.md` — 主编年史
- `docs/devlog/HANDOFF.md` — 人机协作交接
- `docs/devlog/YYYY-MM-DD-session-N.md` — 各 session 增量

## 协议

代码 MIT。家谱语料保留上游许可。
