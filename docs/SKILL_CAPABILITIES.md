# 专业 QA 能力层设计与验收范围

**Task:** TASK-QA-PROFESSIONAL-CAPABILITIES (开发中)  
**Requirements traceability:** REQ-QA-CAP-001 至 REQ-QA-CAP-005（本任务范围内的实现性需求，尚待项目需求基线批准）  
**Evidence status:** NOT_EXECUTED（本文件描述设计和本地单元验证范围，不记录业务系统测试结果）。

## 目标和边界

QA Master 保持一个安装入口。`skills/qa-master/SKILL.md` 是总控入口；包内 `qa_master/skills/professional/` 中的指南是本仓库原创、可被注册表发现的审查和设计指导。注册表只返回已在本地包中验证存在的文件，绝不把选择某一指南说成已调用模型、已运行测试或已产生测试结论。

本增量交付的是静态能力路由和可审阅方法，涵盖需求多源冲突与人工复核、功能边界与状态、API 合约/鉴权/负向、白盒分支与路径、集成、性能/负载/压力/稳定性、兼容性、安全、恢复、回归及缺陷和证据报告。它不实现远程执行、压测调度、漏洞扫描、身份认证、AI 语义推理或“优于其他 Skill”的基准结论。

## 设计

`qa_master.skill_registry` 以指南文件的受限 YAML 风格元数据作为索引。每个指南至少声明稳定 ID、覆盖维度、适用意图、风险范围和具体输入/输出产物。发现过程会校验文件存在、UTF-8 可读、元数据完整、维度属于 `qa_master.core.DIMENSIONS`；无效或缺失文件只产生 `gaps`。选择过程按请求 intent、dimensions 和 risk 过滤实际发现的指南，并始终返回 `execution: NOT_EXECUTED` 与 `status: PLANNING_ONLY`。

资源搜索使用 `importlib.resources` 下的包内 `qa_master/skills`。发布配置必须把这些 Markdown 指南作为 package data；安装验证应在 clean-wheel 环境确认能发现同一组文件。此处的单元测试验证源树包资源，不能代替安装包验证。

## 可验收条件

| ID | 条件 | 本地可验证方式 |
| --- | --- | --- |
| REQ-QA-CAP-001 | 每个专业领域有真实、具输入/输出、方法、可执行 oracle 示例、缺口处理和复核清单的原创指南。 | `discover_skills()` 返回预期指南；人工阅读 `qa_master/skills/professional/`。 |
| REQ-QA-CAP-002 | 注册表只选择实际存在且元数据合法的文件。 | 临时目录缺文件/坏元数据测试产生 gap，不产生虚构选择。 |
| REQ-QA-CAP-003 | 路由可按 intent、规范维度和风险筛选，并报告未知维度/未匹配能力。 | `tests/test_skill_registry.py`。 |
| REQ-QA-CAP-004 | 规划结果不得隐含测试执行或业务 PASS/FAIL。 | `tests/test_skill_registry.py` 检查 `NOT_EXECUTED` 与 `PLANNING_ONLY`。 |
| REQ-QA-CAP-005 | 总控入口说明专业层的真实范围和打包限制。 | 阅读 `skills/qa-master/SKILL.md` 与本文件。 |

## 评审与后续

代码审查应确认元数据解析不会将任意路径作为可执行指令，筛选仅基于已发现的文件，及所有专业指南将草稿、观察和已执行证据区分开。独立测试仍需要确认安装 wheel 后的资源发现、真实项目中输入产物的充分性，以及任何后续执行器的授权/环境边界。
