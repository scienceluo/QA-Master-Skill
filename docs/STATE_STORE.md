# 本地状态存储并发契约

- Scope: campaign and workflow local JSON persistence
- Requirements: `REQ-001`, `REQ-006`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`

## 设计与验收

`qa_master.state_store` 为 `Campaign` 和 `Workflow` 提供单文件互斥锁、revision compare-and-swap（CAS）和唯一临时文件的原子替换。每个对象保存时都提交它加载或新建时持有的 revision；磁盘版本不同即抛出 `StateConflictError`，调用方必须重新读取、合并并重试，不能静默覆盖。

新的对象 revision 从 0 开始。首次保存不存在的文件会写为 revision 1；一个新对象不能覆盖已经存在 revision 的不同状态。旧版无 `revision` JSON 可以读取为 revision 0，并在下一次保存时迁移到 revision 1。临时文件与目标同目录，写入后 `fsync` 并以 `os.replace` 发布，避免固定 `.tmp` 名称竞争。

验收条件：

1. Campaign 和 Workflow 的新文件保存/读取后均保留 revision。
2. 两个从同一 revision 读取的写者中，先完成保存者递增版本；后完成者被拒绝。
3. 旧无 revision 文件可读取并在一次保存后获得 revision 1。
4. 新对象不会覆盖已存在的不同状态，临时文件不会残留。

这是本地单机并发保护，不是多机分布式一致性、用户身份验证、企业审计或外部执行授权。
