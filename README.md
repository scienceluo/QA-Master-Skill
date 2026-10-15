# QA Master Skill

一个仓库、一个 QA Master 入口。当前是 **V1 开发版，不是已验收的正式版**。无需另装其它 QA Skill 仓库。

## 安装与开始

需要 Python 3.10 或以上；Windows 与 Linux 使用相同 Python 命令。

```sh
git clone --branch codex/qa-master-v1-continuation --single-branch https://github.com/scienceluo/QA-Master-Skill.git
cd QA-Master-Skill
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install .
python -m qa_master install-codex --user
```

安装器将入口、专业指南、领域参考和本地助手一起安装到 `~/.agents/skills/qa-master`。在 Codex 中打开待测项目，输入 `$qa-master 评审这份需求并生成测试用例，开发还未完成，不执行测试`。Codex 根据材料开展分析和设计，助手负责本地规划状态；注册表列出文件不代表已经完成分析或执行测试。

只供某个项目使用时，改用 `python -m qa_master install-codex --project <项目目录>`，安装到该项目的 `.agents/skills/qa-master`。安装后若 Codex 未刷新技能列表，重新打开会话。重复安装相同内容不会覆盖文件；更新未修改的受管安装用 `--update`，旧版保留为 ZIP。存在用户修改或未知文件时拒绝覆盖，请先保留自定义内容并选择新安装目录。

安装后的 Skill 不依赖原始源码目录或另一个 QA Skills 仓库；本地助手需要 Python 3.10+，没有 Python 时仍可按指南由 Codex 完成分析设计，但不能使用状态助手。三类对象的分析设计指导已内置；真实设备/远程执行能力须分别验证，不能视为已经接通。详细交付边界见 [Codex 核心版](docs/CODEX_CORE.md)。

## 已有可用入口

| 入口 | 能做什么 | 边界 |
|---|---|---|
| `python -m qa_master plan "任务"` | 规划阶段、信息缺口、专业指南，保存禁止执行/写入的任务范围 | 保守规则解析，不授权执行 |
| `python -m qa_master pause "等待资料"` / `resume` | 保存暂停状态，恢复后重新检查流程条件 | 暂停期间拒绝推进；恢复不增加授权 |
| `python -m qa_master.campaign_cli --input examples/campaign.json --output .qa-master/design.json` | 结构化需求生成草稿、追踪、覆盖及缺口 | 草稿，不能代替人类批准 |
| `python -m qa_master.config_ui --config .qa-master/config.json` | 本机配置页面，默认 http://127.0.0.1:8765 | 仅非秘密配置和凭据环境变量引用 |
| `python -m qa_master.benchmark --help` | 同题、同模型、同设置的双边评测资料校验 | 缺少双方实际输出时不能得出优劣 |

内置指南覆盖需求冲突、功能边界/状态、API、白盒、集成、性能/负载/压力/稳定性、兼容性、安全/恢复、回归与证据报告。见 [专业能力](docs/SKILL_CAPABILITIES.md)。这些指南和确定性生成器不等于完整语义 Agent。

正式 CLI 使用统一的 schema v2 状态。旧 Campaign/Workflow 文件在查看时不改写，首次修改时保留同目录字节备份再迁移；已有状态不能被 `init` 覆盖。旧审批和执行记录仅保留历史，不自动获得可信授权。迁移与恢复边界见 [实现记录](docs/verification/schema-migration-implementation.md)。

## 集成与执行

- [企业接口](docs/ENTERPRISE_ADAPTERS.md)：Jira 读取/受控写入、Confluence Cloud 读取、SynapseRT 显式部署接口契约、写入日志和读回。请求成功不能直接当作读回验证，响应丢失不会自动重复写入。
- [GitLab CI 核验](docs/GITLAB_CI_ATTESTATION.md)：读取项目、Job、Pipeline、保护规则，再获取 JUnit 制品。外部制品保持未认证来源。
- [本机 Runner](docs/LOCAL_RUNNER.md)：可信宿主授权、源码/执行程序绑定、有限输出、环境隔离和超时清理。进程成功不是业务测试通过。
- [本地任务生命周期核心](docs/JOB_SCHEDULER.md)：保存派发前状态、按序观察、显式恢复、取消与超时；并发冲突或响应丢失后不会自动重复派发。它是供宿主集成的库，尚未连接 CLI、远程传输或真实 Worker。
- [安全约束](docs/SECURITY_CONTINUATION.md)：执行回执和结果来源由宿主验证，默认拒绝；任何 JSON 布尔值或审批人文本均不能证明真实身份。

企业写入、执行和发布判断的宿主验证接口需要可信集成方实现。当前不提供默认放行器；单独填写 `approved_by`、设置环境变量或调用旧版 `approve` 命令不能获得实际执行权限。

## 验证与剩余工作

当前复测证据位于 [verification](docs/verification/)，原始基线失败与修复记录均保留。历史 README 已归档至 [history](docs/history/README-before-continuation.md)，其中测试计数不代表当前版本。

尚未交付：完整多语言语义 Agent、远程 SSH/WinRM 执行与资源调度、生产身份/密钥库、具体 SynapseRT 部署的全部业务操作与缺陷回归自动闭环、双方完整行为对照评测。配置页目前为经过校验的 JSON 编辑器。

真实企业环境 E2E 为 `NOT_EXECUTED`，不影响本地产品开发。尚无证据证明总体优于 Awesome QA Skills，也不发布 V1.0 正式标签。详细范围见 [V1 验收](docs/V1_ACCEPTANCE.md)、[需求追踪](docs/03-requirements/requirement-traceability-matrix.md) 与 [评测协议](docs/BENCHMARK.md)。

## 代码与数据

本项目专业内容采用原创实现，不冒认第三方作者身份。不要把真实 Token、密码、Cookie、私钥、公司测试资料或环境配置提交到这个 Public 仓库。用户状态和本地配置保存在被 Git 忽略的 `.qa-master/` 下。
