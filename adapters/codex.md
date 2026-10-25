# Codex 协调适配

本标准依赖宿主提供子 Agent 工具。Python CLI 负责契约与状态，不能从普通 Python 代码调用聊天中的 spawn 工具。没有宿主调度时只能准备任务，不能声称已经执行。

1. `python -m video_flow protocol` 读取强制协议；`python -m video_flow status RUN` 查看 ready。
2. `python -m video_flow dispatch RUN STAGE` 生成并登记 packet。
3. 主 Agent 以新上下文（当前工具 `fork_turns="none"`）spawn；只传 packet 绝对路径、`docs/contracts.md`、选定 Skill 与任务目的。不得复制整个历史。并行只启动互不依赖的 ready 节点。
4. 取得真实 agent ID后 `python -m video_flow bind RUN TASK_ID AGENT_ID`，向工作者告知ID；工作者只写候选和回执。
5. 完成后 `python -m video_flow submit RUN TASK_ID`；这只接受候选，独立review任务需要再次spawn全新Agent，不能复用作者。
6. 用户门禁由主Agent展示具体作品并收取决定后 `approve`；禁止自动编造批准理由。用户在init选择automatic时质量验收仍必需。
7. revise后状态自动回到作者，任务包含本次反馈；按预算修复再独立复审。工具故障用retry记录；耗尽预算停止并报告。
8. 全部accepted后 `package`。v0.1按锁定流程交付前期文本或参考图；v0.2可导出TXT、三类资产、分镜板、片段提示词及映射，交付清单声明平台绑定与外部视频效果未验证。

启用v0.2时读取 [制作契约](../docs/contracts-v02.md)。图片采用import模式时使用import-media真实本地操作身份，保留独立看图审查；不能伪装成宿主已启动的工作者。generate通道未注册时返回具体缺口。先用preflight核实模式，再派发；--production-config不自动授权付费。

启动示例：`python -m video_flow init ../video-flow-runs/my-run --brief examples/video_flow/coffee-brief.json`。

本地共享文件系统中的写入边界是约定，验收检查能够拒绝错误回执、过期输入与缺陷报告，但不能阻止拥有全盘权限的Agent篡改代码/总状态。需要强制隔离时由宿主加只读挂载、受限状态工具与独立批准身份。

参考：[OpenAI 子Agent文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)、[Skill文档](https://learn.chatgpt.com/docs/build-skills)。
