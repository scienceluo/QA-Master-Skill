# 本地配置中心

- Task: `TASK-007`
- Requirements: `REQ-010`; supports `NFR-003` and `NFR-004`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`

## 目标与验收

本任务提供一个仅监听本机回环地址的配置中心，用于保存 GitLab、Jira、Confluence 的 HTTPS 端点、项目映射，以及 Windows/Linux 测试机的连接元数据。配置可在重启后读取，格式版本固定为 `schema_version: 1`。

验收条件：

1. 缺少配置文件时返回安全的空默认值；有效配置能原子写入并重新读取。
2. 配置仅允许声明环境变量名（例如 `JIRA_TOKEN`）作为 `credential_env`；任何未定义字段（包括 `token`、`password`、`cookie`、`private_key`）都被拒绝。
3. 服务端点只能是无用户信息、查询或片段的 HTTPS URL；机器必须标明 `windows` 或 `linux`、受支持传输方式和环境变量引用。
4. `python -m qa_master.config_ui --config <path> --port <port>` 只提供本机配置查看和保存，不连接 GitLab/Jira/Confluence/SynapseRT，也不执行测试。
5. 读取和写入请求的 `Host` 都必须是本服务端口上的回环地址；写入还需要该进程生成的 CSRF token，且 `Origin` 必须与该 `Host` 一致。非回环绑定、跨源、DNS rebinding Host 或超限请求被拒绝。

## 设计

`qa_master.configuration` 是唯一的持久化边界。它执行严格 schema 校验、限制大小，并用同目录临时文件、`fsync` 和 `os.replace` 保存 JSON。未知字段被拒绝，避免凭据或未来未经审计的字段被悄悄落盘。该模块不读取环境变量的值，也不实现凭据保管库。

`qa_master.config_ui` 仅使用 Python 标准库 HTTP 服务。进程启动时固定一个配置路径和随机会话 CSRF token；浏览器不能提交文件名或请求外部 URL。每个 GET 都要求本服务端口上的回环 `Host`，避免 DNS rebinding 读取配置；页面以 `frame-ancestors 'none'` 和 `form-action 'self'` CSP 禁止嵌入和外部表单目标。页面只显示和编辑已经校验的 JSON，所有回显均 HTML 转义。请求体上限为 64 KiB，访问日志被抑制，防止错误输出或日志意外包含配置内容。

该 UI 不含执行、连接测试或第三方凭据收集。环境变量引用只说明操作员应在操作系统或批准的 secret manager 中提供值；认证凭据库、多用户身份和企业端实际读回仍未实现。

## 配置示例

```json
{
  "schema_version": 1,
  "services": {
    "gitlab": {"base_url": "https://gitlab.example.test", "credential_env": "GITLAB_TOKEN"},
    "jira": {"base_url": "", "credential_env": ""},
    "confluence": {"base_url": "", "credential_env": ""}
  },
  "project_mappings": {
    "gitlab_project": "group/project",
    "jira_project": "QA",
    "confluence_space": "QA",
    "synapsert_project": "QA"
  },
  "machines": [
    {"id": "win-lab-01", "platform": "windows", "host": "192.0.2.10", "transport": "winrm", "credential_env": "QA_WINRM_SECRET", "exclusive": true}
  ]
}
```

The values above are examples only. Do not put a credential value, secret URL, token, password, cookie, or private key in this JSON.

## Verification

Run `python -m unittest tests.test_configuration -v` for the configuration and local HTTP security contract. This verification does not contact enterprise systems and does not establish a project Gate, release, or acceptance result.
