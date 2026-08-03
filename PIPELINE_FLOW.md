# AI 广告视频前期生产流程

> 版本：v8.0

## DAG

```mermaid
flowchart TD
    A[需求输入] --> B[创意简报 + 剧本]
    B --> C{创意审批}
    C --> D[艺术方向]
    D --> E{视觉审批}
    E --> F[分镜导演]
    F --> G{分镜结构与广告文字审批}
    G --> H[资产执行]
    H --> I[资产提示词]
    I --> J[资产生图或人工导入]
    H --> K[视频段规划]
    I --> L[Board Packet + Board Manifest]
    K --> L
    L --> M[分镜板提示词]
    M --> N[分镜板生图或人工导入]
    J --> O[视频提示词 + Video Prompt Manifest]
    N --> R{Board 文字与额外文字核验}
    R --> O
    O --> P[Manifest 驱动打包]
    P --> Q{Delivery 校验}
```

## 状态与数据职责

| 层 | 事实源 | 职责 |
|---|---|---|
| 流程 | `config/pipeline.yaml` | DAG、executor、审批、skip、输出 |
| 执行 | `checkpoint.json` + tasks | 阶段和任务状态 |
| 产物 | `artifact_registry.json` | revision、path、hash、依赖 |
| 审批 | `approval_registry.json` | 谁批准了哪个 revision/hash |
| 镜头关系 | Board/Video Manifest | V、SB、S 和媒体引用 |
| 交付 | `final_package_manifest.json` | 包文件、hash、blocker |

## Skip 规则

图片执行器可被人工导入替代，但媒体产物不是无条件可缺失。`skip_effect=draft_only` 只允许继续生成内部草稿；production 必须有已登记、已批准的必需资产图和分镜板图。

## V8 视频生成规则

- 每个 `V###` 为 4–30 秒；原子 `S###` 可以更短，但只能在同一场景内合并。
- 未声明画幅时使用 `16:9`。
- 场景、构图、装饰、静态特效和广告文字在 Board 阶段固定。
- 视频模型只接收 Board、人物和广告商品参考。

## 回退规则

批准后的 canonical artifact 发生 hash 变化时，当前 approval 失效，依赖该 revision 的所有下游进入 `invalidated`。修改必须生成新 revision，禁止覆盖已批准快照。
