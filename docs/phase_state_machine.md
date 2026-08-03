# Phase State Machine v8.0

| 状态 | 含义 | 满足依赖 |
|---|---|---|
| `not_started` | 尚未开始 | 否 |
| `in_progress` | 正在执行 | 否 |
| `review_required` | Artifact 已注册，等待审批 | 否 |
| `approved` | 当前 revision/hash 已批准 | 是 |
| `completed` | 无审批阶段完成 | 是 |
| `skipped` | 配置允许且已记录原因 | 是，但 `draft_only` 不能通过 production |
| `failed` | 执行失败，可重试 | 否 |
| `blocked` | 存在不可继续的问题 | 否 |
| `invalidated` | 上游 revision 变化导致失效 | 否 |

## Rules

- 依赖来自 PipelineSpec 的 `depends_on`，不是阶段列表前缀。
- `ready` 是根据依赖和完整性动态计算的调度结果，不写入 stage status。
- `waiting_for_provider` 只属于图片任务队列，不是 pipeline stage status。
- Approval 必须绑定 Artifact Revision 和 SHA-256。
- Board Approval 还必须绑定广告文字逐字匹配和无额外文字证据。
- `ready_stages` 可以同时返回多个节点，用于并行执行。
- `invalidate` 沿 DAG 递归传播。
- 拒绝、hash 不匹配和 validator 失败必须写入 blockers。
- `completed_with_known_gaps` 不再作为阶段终态；已知缺口写入最终清单，且只允许在明确层级消费。
