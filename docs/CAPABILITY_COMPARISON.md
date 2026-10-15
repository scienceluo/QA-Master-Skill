# QA Master 与 Awesome QA Skills：能力盘点

- Task: `TASK-012` (supports `REQ-011`)
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Observation status: `OBSERVED` catalog inventory; no behavioral comparison executed

## 上游快照与边界

本盘点在 2026-10-14 从公开仓库 `https://github.com/naodeng/awesome-qa-skills` 浅克隆获得，固定 commit 为 `1a8c57c0e1c31b80aea5cb85dd830387dee09c9f`。该快照含 330 个 `SKILL.md` 文件：英文和中文各 165 个。上游 `docs/catalog/skills-index_EN.md` 描述每种语言含 10 个 workflow、150 个 testing type、5 个 skill-engineering package。

本文件只使用目录、名称和上游公开目录页进行分类计数；没有复制其提示词、脚本、模板或实现。上游内容会变化，因此此表只对应上述 commit。下表也不是质量评分、功能等价证明或 superiority assertion。

## 覆盖映射

表中“部分”表示 QA Master 有受限的本地实现或计划器，可处理该组的一小部分输入；它不代表与上游任一具体 Skill 等价。表中“缺失”表示本仓库未发现该组的可运行专用能力。十个 workflow、150 个 testing type 和五个 engineering package 均落入下列互斥能力组，因而这是对整个 catalog 的分类映射，而非挑选少数相似名称。

| 上游完整能力组 | 上游目录覆盖 | QA Master 当前映射 | 状态 | 实际边界 |
|---|---|---|---|---|
| 跨阶段 workflow | 10 workflows | `intent.py`、`workflow.py`、`campaign_cli.py`、`release_gate.py` | 部分 | 本地阶段规划、草稿和门禁；没有上游式多角色自动工作流或实际执行。 |
| 需求、风险、设计与可测性 | requirements/test strategy/acceptance/risk/testing types | `quality.py`、`coverage_design.py`、`review_packet.py` | 部分 | 结构化输入检查和草稿覆盖；没有完整语义需求/架构分析。 |
| 用例设计技术 | decision/state/boundary/pairwise/model/property 等 testing types | `generator.py`、`coverage_design.py`、`api_codegen.py` | 部分 | 可生成有限结构化草稿；不实现这些专用设计方法的完整算法或专家引导。 |
| 功能、API、手工、UI、移动与无障碍 | functional/api/manual/mobile/accessibility/security 基础组 | `api_intel.py`、`api_codegen.py`、`gitlab_adapter.py` | 部分 | OpenAPI 和本地源码分析；没有浏览器、移动、手工或可访问性执行器。 |
| 发布、缺陷和测试报告 | bug/report/review 与 release workflow | `junit_ingest.py`、`release_gate.py`、`review_packet.py` | 部分 | 证据和阻断检查；没有真实缺陷写回、发布或人工验收。 |
| 可靠性、安全、恢复 | reliability/resilience/chaos/security/recovery testing types | `local_runner.py` 的本地命令限制 | 缺失 | 没有专用可靠性、安全、恢复测试引擎或授权执行。 |
| 自动化框架与工具 | API clients、Selenium/Playwright/Cypress、视觉和跨浏览器组 | `api_codegen.py` | 部分 | 仅生成受限 pytest 草稿；不运行或集成这些框架。 |
| 回归与测试套件工程 | flaky/regression/mutation/mock/suite-health 组 | `workflow.py`、`release_gate.py` | 部分 | 可记录失效和门禁；没有选择、mutation 或 flaky 分析引擎。 |
| 性能与容量 | performance/load/stress/capacity 组 | `coverage_design.py` 的阈值缺口处理 | 部分 | 能拒绝虚构 SLA；没有负载生成、测量或容量分析。 |
| 复盘与可观测性 | root-cause/log/observability 组 | 无专用模块 | 缺失 | 没有日志、指标或根因分析器。 |
| 生产质量与事故响应 | production verification/incident/trace/anomaly 组 | 无专用模块 | 缺失 | 没有生产访问或生产验证；本项目也不应隐式执行。 |
| AI/Agent QA | LLM/RAG/prompt/agent/safety 组 | `benchmark.py` 的离线成对记录 | 缺失 | 基准框架不会评估模型质量、RAG、prompt 或 agent 行为。 |
| Skill engineering | 5 个 skill-engineering packages | `skill_registry.py`、`qa_master/skills/` | 部分 | 本地注册与存在性检查；没有上游同等的治理、评估和修复闭环。 |

## 本次可复现比较准备

`benchmarks/scenarios.json` 是独立创作的 12 个 QA 场景，涵盖设计限定、冲突、源码候选、网页、构建等待、API 边界、无 SLA、证据、恢复、变更失效、缺陷回归和报告。`benchmarks/manifest.json` 对两个参与方的全部行为输出均是 `NOT_EXECUTED`。

`qa_master.benchmark` 只接受同一场景 SHA-256、同一 model 和 settings 的两个完整提交，保留原始输出 SHA-256 和人填 rubric 证据。它从不生成 superiority conclusion；即使完整数据存在，结果也只是 `HUMAN_REVIEW_REQUIRED`。要比较全部上游能力，仍需逐个 capability 设计相同输入、同一模型设置、独立评分和保存行为输出；当前 12 个场景不能覆盖或证明 165 个上游逻辑 Skill 的质量。

## 配置 UI 的当前状态

`qa_master.config_ui` 是可运行的 loopback-only 原型，可安全编辑一个经 schema 校验的 JSON 配置，并只接受环境变量凭据引用。它目前以 JSON textarea 为输入，尚不是面向每项服务、映射和机器的便利表单；因此“配置 UI 易用性”仍为 `PARTIAL`，不能作为 `REQ-010` 的最终验收或项目 Gate 证据。
