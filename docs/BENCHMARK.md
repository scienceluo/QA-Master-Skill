# 可复现 QA 能力对比基准

- Task: `TASK-008`
- Requirement: `REQ-011`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`

## 目的与验收条件

该基准提供一个原创、离线且可复现的框架，用相同场景集、相同模型标识和相同设置，对两个参与者的实际行为输出进行成对记录。它不调用模型、GitLab、Jira、Confluence、SynapseRT 或公司环境。

`benchmarks/scenarios.json` 必须至少包含以下 12 个场景：只设计、冲突需求、仅源码、仅网页、等待构建、API 认证/边界、无 SLA、缺失证据、恢复会话、上游变更失效、缺陷回归、报告。每个场景均要求已知事实、范围、可观察的 oracle 和追踪/覆盖边界，且没有复制外部项目的提示词或实现。

验收条件：

1. 初始 `benchmarks/manifest.json` 为 `NOT_EXECUTED`，并为两个参与者的每个场景保存行为输出和五个 rubric 维度的空位；它不声称任何评分或优势。
2. 两个实际输出文件都必须绑定同一个场景集 SHA-256、同一模型名、完全相同的 JSON 设置，以及完整且唯一的场景响应。
3. 每个响应必须包含实际行为输出和由人提交的 factuality、scope、oracle、traceability、coverage 五项评分、理由和证据引用。工具不填补缺失分数，也不把进程成功当评分。
4. 结果清单记录原始输出 SHA-256、场景集 SHA-256、参与者版本和提交的分数；缺少任一方、模型/设置/输入不一致或维度不完整时命令失败。
5. 即使测量数据完整，工具只返回 `HUMAN_REVIEW_REQUIRED`，从不自动断言任一方优于另一方。

## 输入与运行

提交文件是 JSON，含 `participant_id`、`participant_version`、`model`、`settings`、`scenario_set_sha256` 和 `responses`。每个 response 含一个 `scenario_id`、非空 `behavioral_output`，以及五个 rubric 对象；每个 rubric 对象包含 `score`（1–5）、`rationale` 和 `evidence_ref`。

```powershell
python -m qa_master.benchmark `
  --scenarios benchmarks/scenarios.json `
  --left qa-master-output.json `
  --right comparison-output.json `
  --model gpt-example `
  --settings '{"temperature":0}' `
  --output benchmark-result.json
```

`--model` 和 `--settings` 是本轮固定实验契约；提交文件也必须逐项相同。输出的 `claim_status` 始终不是 superiority claim。初始清单或缺少输出时为 `NOT_EXECUTED`，不可作为真实比较结果。

## 评分和限制

五项统一 rubric 分别评估：事实是否有来源且不臆造（factuality）、是否遵守限定操作范围（scope）、是否给出可测预期而不虚构阈值（oracle）、是否保留需求/场景/证据链接（traceability）、是否说明必要测试维度和适用性（coverage）。评分是带理由和证据引用的人工输入，当前没有认证评审者、独立双评审或统计显著性模型。

因此该功能是实验记录和完整性校验，不是专家评审、外部产品审计、竞争结论或项目验收。完整且经过独立评审的成对测量数据仍只进入人工审查；任何公开的 superiority claim 需要单独的人类决定与保留证据。
