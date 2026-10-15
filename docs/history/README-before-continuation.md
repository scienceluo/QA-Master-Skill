# QA Master Skill

**单仓库、一套安装入口的原创 QA 总控工程（当前为 v0.2 开发版）。**

目标：对用户的一句话测试任务，自动判断需求评审、测试设计、代码分析、执行、回归、报告等阶段，按风险、审批与状态安全推进。测试技能以本项目自有模块实现，不要求用户另装其它 QA Skill。

## 当前已实现（V0.1）
- 任务意图和范围解析的基础规则
- 项目状态与确认答复持久化
- 需求/用例/执行审批门禁
- 缺少构建/环境时暂停
- 13 类测试覆盖检查
- 39 项本地单元测试：21 项工作流规则 + 18 项需求/用例/证据检查（详见 `docs/QUALITY_BASELINE.md`）

## V0.2 新增：可运行质量审计逻辑
- `qa_master/quality.py`：需求歧义/来源/确认检查、结构化用例字段和追踪审计、证据约束的执行结果汇总
- `tests/test_quality.py`：18 项新单元测试
- 尚不包含自动语义需求解析或完整用例生成，必须由 Agent/后续引擎负责。

## 尚未实现
完整的原创需求分析/白盒/API/性能/稳定性/安全 Skill 内容、运行时 AI Agent 分派、GitLab/Jira/SynapseRT/Wiki 接口、远程 Runner、自动生成可执行脚本及端到端闭环。**V0.1 不应视为可独立完成所有测试的成品。**

## 安装（Windows）
```powershell
git clone https://github.com/leongibhub/QA-Master-Skill.git
cd QA-Master-Skill
py -3.10 -m unittest discover -s tests -v
py -3.10 -m qa_master init "demo"
py -3.10 -m qa_master plan "只生成测试用例，不执行测试"
```

在 Codex/OpenCode 以当前目录为工程根目录，读取 `AGENTS.md` 与 `skills/qa-master/SKILL.md`。当前命令行工具是本地规则验证器，并不会自动访问外部平台。

## 统一产品化方向
`skills/qa-master` 为唯一入口；`skills/` 下逐步加入独立实现的需求评审、功能/API/白盒、性能/压力、可靠性、安全、回归及报告模块；`adapters/` 与 `runners/` 为后续内置集成。一次安装应包含已实现的全部模块，无需用户单独配置或安装第三方 QA Skill 包。

## 知识产权
项目以自主实现为原则。可以研究公开项目的功能思想，但不复制受许可证限制的实现，也不将他人代码篡改署名后作为原创发布。借鉴的第三方资料如需使用，应遵守其许可证及归属要求。

> 注意：这是 Public 仓库。不要提交 Token、密码、SSH 私钥或真实机器凭据。


## V0.3 增量能力（原生单仓库）
- `qa_master/generator.py`: 从具有明确验收标准的结构化需求生成可追踪的**草稿**用例；不虚构缺少的异常预期、数据和阈值。
- `qa_master/code_intel.py`: 只读分析本地 Python 源文件的 AST，报告函数、分支及异常路径候选。观测到的代码行为不会自动成为正式需求。
- `qa_master/api_intel.py`: 从已经解析的 OpenAPI `paths` 中抽取 API 测试清单及文档缺口，不连接接口、不声称执行。
- `tests/test_generators.py`: 新增 17 项本地单元测试；合计 56 项本地通过（Python 3.13）。GitHub Actions 运行结果另行核验。

### 当前限制
这里的生成器是**确定性基础能力**，尚不具备从自由文本自动抽取完整业务规则、基于多语言代码的深层语义分析、独立生成全部非功能用例、自动运行 API/性能测试或外部企业平台联动的能力。V0.3 **没有**超过 Awesome QA Skills 的实测证据。要达到该目标仍需按真实基准集持续开发和对比。


## V1.0 development branch milestone: persistent workflow core (2026-10-14)
The new `qa_master/workflow.py` provides dependency expansion, required-input checks, human approval gates with version+scope, no bypass of unready steps, evidence references, upstream-change invalidation and save/load.
`tests/test_workflow.py` includes 15 regression scenarios. Full local suite: **89 passing tests**.

**Limitations:** This is a dependency/authorization *planner*, not an actual scheduler or Jira/SynapseRT executor. It does not authenticate approval identities, bind approvals cryptographically to artifact hashes, or perform enterprise API calls. A complete V1.0 release is still pending. Do not start destructive tests based solely on this model.


## V1.0 开发进度：GitLab 真实只读接口（2026-10）
- 新增 `qa_master/gitlab_adapter.py`：GitLab REST v4 项目信息、递归目录及源码文件读取，HTTPS 默认启用，分页和数据大小受限。
- 新增 `tests/test_gitlab_adapter.py`：15 项 Mock HTTP 测试。
- 使用方法与安全边界见 `docs/GITLAB_CONNECTOR.md`。
- 连接器代码已提交并核验；尚**未**以公司 GitLab 实际环境进行端到端验证。代码逆向语义分析、Jira/SynapseRT、远程执行器仍需继续开发。


## V1.0 开发里程碑：源码候选需求（2026-10-14）

新增 `qa_master/reverse_requirements.py`：结合只读 GitLab Adapter，限定文件数量和大小，分析 Python 函数、分支与异常候选，保留文件行号、Blob ID 与内容哈希；输出始终是 `PENDING_HUMAN` 候选需求。新增 `tests/test_reverse_requirements.py`（17 项测试）和 `docs/REVERSE_REQUIREMENTS.md`。

**限制：** 当前不等于 AI 语义逆向需求，不支持多语言的深入解析，也没有真实 GitLab 环境的端到端验证。要形成正式需求，必须完成人工评审和批准；代码当前行为不自动作为正确的验收标准。


## 当前真实交付状态（2026-10-14）
**项目仍处于 V1.0 开发中，未通过端到端验收，也未证明优于 Awesome QA Skills。** 新增 `qa_master/enterprise.py` 和 `tests/test_enterprise.py`（只读接口保护、审批作用域、SynapseRT 计划 Dry-run、远程机器配置验证）。本地隔离环境 134 项单元测试通过。完整未完成项及正式版准入标准请见 [`docs/V1_ACCEPTANCE.md`](docs/V1_ACCEPTANCE.md)。


## 2026-10-14 实际开发更新 — 企业控制与本机执行

- `qa_master/enterprise.py`：只读 HTTPS API 连接、作用域审批对象、SynapseRT Dry-run（**不进行实际写入**）、机器配置检查。
- `qa_master/local_runner.py`：经许可的本机 unittest/pytest 命令执行，采集进程结果、超时、日志及 SHA-256 证据；**进程退出成功不等于业务测试 PASS**。
- 测试：`tests/test_enterprise.py` 和 `tests/test_local_runner.py`；当前本地隔离测试共 **143 项通过**。
- 文档：`docs/V1_ACCEPTANCE.md`、`docs/LOCAL_RUNNER.md`。

**仍未具备 V1.0 正式发布条件**：公司 Jira/SynapseRT/Confluence 的真实接口对接和认证、远程 SSH/WinRM Runner、全类型专家测试引擎、端到端质量验收及与 Awesome QA Skills 的实测对标尚未完成。详见准入清单，不得用单元测试数量替代项目验收。


## 一键生成项目测试设计草稿（新增）

```powershell
python -m qa_master.campaign_cli --input examples/campaign.json --output campaign-report.json
python -m unittest discover -s tests -q
```

已接通结构化需求分析、需求质量检查、多类型草稿用例、追踪与覆盖检查。输出 JSON 会保留审批和执行的待确认状态，**不会**写 Jira/SynapseRT 或启动测试。这是离线集成的第一个端到端 CLI，详见 [docs/CAMPAIGN_CLI.md](docs/CAMPAIGN_CLI.md)。在本地进行了 151 项测试（包含 CLI 子进程验证），但企业系统端到端验收和对标仍未完成。


## 自然语言任务规划（2026-10-14）

CLI `python -m qa_master --state .qa-master/campaign.json plan "先评审需求并生成用例，不执行测试"` 现在通过内置 `qa_master/intent.py` 解析任务，读取已保存项目信息，返回 `stages`、`no_execution`、`no_external_writes`、`questions` 和 `uncertainty`。比如只有 GitLab 时会询问是否有需求；回答“没有”后不重复追问。

这是**保守关键词意图解析器**，不是 LLM 自然语言理解或自动执行引擎；复杂表达与否定组合尚不能保证全覆盖。只支持规划，不会创建 Jira 对象、触发真实测试。新增 `tests/test_intent.py`（15 项）和 `tests/test_intent_cli.py`（2 项），本地完整 unittest 为 **168/168 PASS**。GitHub Actions 云端结果仍需单独确认。


## 2026-10-14 审批完整性加强

新增 `qa_master/approval.py` 和 `Workflow.approve_exact/evaluate_exact/complete_exact`：审批现在可以与**项目、操作、范围和 JSON 产物 SHA-256** 精确绑定，修改需求/用例或更换范围后拒绝沿用原审批。老版本仅记录文本版本的审批不满足新检查。包含 12 项模块测试和 5 项工作流集成测试；文件已上传 GitHub。

**重要：这并不是受信任的身份认证与审计服务。** Reviewer 当前只是记录字段，旧 `complete` 路径仍存在，因此生产环境必须统一切换到不可绕过的服务端授权门禁。详见 [审批完整性设计](docs/ARTIFACT_APPROVAL.md)。本轮环境无法访问 GitHub 域名完成克隆，因此没有声称整仓最新提交回归通过，请查看 GitHub Actions 并在可联网环境运行 `python -m unittest discover -s tests -v`。


## 发布质量门禁（2026-10-14）

新增 `qa_master/release_gate.py`，可按测试用例、运行证据、审批、缺陷和跳过豁免判断 `BLOCKED` 或 `READY_FOR_HUMAN_REVIEW`，不自动授权上线。修复全部 SKIPPED 也可能进入评审的问题。详见 [`docs/RELEASE_GATE.md`](docs/RELEASE_GATE.md)。本地全量单元测试 188 项通过；GitHub Actions 结果需独立确认。该功能尚未接入 Jira/SynapseRT 真实执行记录。


## JUnit CI 测试结果导入（2026-10-14）
新增 `qa_master/junit_ingest.py` 和 `tests/test_junit_ingest.py`：将 JUnit XML 的成功/失败/错误/跳过结果映射到唯一的正式 Case ID，保留 XML SHA-256，拒绝重复、未映射、冲突结果及 DTD。外部 XML 默认标记 `UNVERIFIED_EXTERNAL_ARTIFACT`；发布质量门禁新增 `UNVERIFIED_SOURCE` 阻断，不将外来数据冒充可信的 CI 证据。详见 [JUnit 证据导入说明](docs/JUNIT_INGEST.md)。

本地整仓 `unittest` 共 **203 项通过**。最新 GitHub Actions 运行结果仍需单独核验。真实 CI 来源认证、SynapseRT 回写和远程测试机联调仍未完成。
