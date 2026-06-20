# AGENTS.md — 志鉴 v2 多 agent 协作约定

## 默认分工

志鉴 v2 工作流以**单一 lead agent**为主，按需派生 Explore / Plan / general-purpose 子 agent：

| 任务类型 | 用谁 |
|---|---|
| 查文件 / 定位符号 / 摸代码 | `Explore` |
| 出实现方案 | `Plan`（或在 lead 内 Plan Mode） |
| 跨多文件调研（3+ query） | `Explore` |
| 复杂多步（并行子任务） | `general-purpose` |
| 大块代码生成 + 验证 | `lead` 主线 |

## Lead agent 工作节奏

每个 session（一次对话）按诗云模板：

1. **接任务** → 看 `docs/DEVLOG.md` 上下文（最近 session 摘要）
2. **Plan**（如涉及大改动）→ Plan Mode 出方案 → ExitPlanMode 等用户批准
3. **改代码** → 改完跑验证（`npm test && npm run build`）
4. **写 DEVLOG** → 在 `docs/devlog/YYYY-MM-DD-session-N.md` 写本 session 增量
5. **commit** → 按用户偏好"先 commit 再验证"

## 子 agent 调用规则

- **Explore**：传 1 个明确目标 + 文件路径（不要笼统"摸一下"）
- **Plan**：传 Phase 1 调研结果 + 约束条件；要求给 step-by-step
- **general-purpose**：必须写 `必须加载 web-access skill 并遵循指引`（如需联网）
- **避免**：
  - 子 agent 干 lead 该干的事（如：写文档、改 CLAUDE.md）
  - 重复劳动：subagent 已经搜过的，lead 不要重复搜
  - prompt 里暗示手段（"搜索"会锚定到 WebSearch）；写目标（"调研"/"获取"）

## 文档约定

- **MEMORY.md**：跨 session 索引，每条 ≤ 150 字符
- **CLAUDE.md**：项目级铁律，红线、约定、工作流
- **AGENTS.md**：agent 分工（本文档）
- **DEVLOG**：session 级协作记录，每 session 一篇
- **docs/devlog/HANDOFF.md**：跨 session 上下文接力（最近 60KB）

## DEVLOG 模板

每个 session 文档含：

```markdown
# YYYY-MM-DD Session N · <一句话主题>

## Context
- 上次 session 留下的挂账：...
- 本次触发：...

## Decisions
- 决策 1: <决策>。原因：<为什么>
- 决策 2: ...

## Changes
- commit `<hash>`: <一句话>
- file path:line — <改了什么>

## Verification
- npm test: PASS
- npm run build: PASS
- 浏览器端到端: ...

## Outstanding / 挂账
- [ ] 待办 1
- [ ] 待办 2
```

## 红线（与 CLAUDE.md 一致）

- 不删文件/目录/历史（除已规划的大爆炸清理）
- 不改 .env / token / CI 配置（除非明确要求）
- 不 git push 不 git rebase -i 不 git reset --hard
- 不安装全局依赖
- 公开操作（npm publish / 部署 / 发文）必须先问
