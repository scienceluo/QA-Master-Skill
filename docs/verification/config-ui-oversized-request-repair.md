# 配置 UI 超限 POST 修复验证

- Task: `TASK-030`
- Bug: `BUG-008`
- Change: `CR-009`
- Evidence Status: `OBSERVED`

## 修复范围

配置 UI 对 `Content-Length` 超过 64 KiB 的 POST 在回复 HTTP 413 前，最多丢弃 64 KiB 加 1 字节，并设置 0.25 秒的读取时限。随后该连接明确关闭。这样可让实际边界超限正文完成传输，避免 Windows 客户端在服务端未读正文时连接中止；声明很大但不发送正文的客户端也不会让处理线程无限等待。

该处理不接受或解析超限内容，也不会按声明长度无限读取。若实际正文大于有界丢弃上限，服务端仍会关闭该连接，客户端可能观察到连接关闭；客户端应以 HTTP 413 为拒绝信号，不应依赖此连接继续传输或复用。

## 本地回归

运行：

```powershell
python -m unittest tests.test_configuration -v
```

覆盖：

1. 65,537 字节实际 POST 收到 HTTP 413。
2. 声明 1 MiB、只发送 HTTP 头的 POST 在短时限内收到 HTTP 413。

实际结果：2026-10-15 本机运行完成 12 项测试，全部通过。

该记录仅说明本地 HTTP 回归；不代表企业系统联调、Gate 结论或验收。
