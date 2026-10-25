---
name: run-video-flow
description: 当用户要求运行视频创作流程时，按Video Flow标准协调路由、独立子Agent、阶段审查和前期交付；支持广告与单篇叙事短片。
metadata:
  version: "0.1.0"
---

# Video Flow 协调

读取本项目AGENTS.md、adapters/codex.md与docs/contracts.md。用户选择本流程即授权按规定委派子Agent；未配置付费媒体生成与发布。

用户选择外部平台制作包时，用 --media --production-config 启用v0.2，读取docs/contracts-v02.md并执行preflight。此模式以毫秒分镜、三类资产、制作计划、已审图片和逐V片段提示词交接；默认图片导入。import-input可在首次story派发前登记已有剧本，作者和评审都必须读取原文并保留已知事实与对白。图片导入使用import-media及真实导入身份，仍需独立目检。generate能力未注册时报告缺口，不擅自调用付费工具。

修订媒体前用impact查看消费者，按reference_key局部invalidate；旧图和旧交付包保持可追溯。所有阶段accepted后用package --format external-production导出，再verify-package。mock包仅为合成协议样例；真实图片质量和外部视频效果分别记录。

先收集需求与事实来源，按examples/video_flow的brief结构归一，未知关键字段询问；不要虚构事实。运行doctor确认能力，init创建独立run并锁定工作流与Skill快照。默认关键决策由用户批准；用户明确选择自动模式时可在init使用automatic，质量审查仍独立执行。

按status的ready节点dispatch，用全新上下文spawn指定Skill任务，仅给packet与必要规范。bind真实agent_id后告诉工作者；等待完成，检查candidate与receipt再submit。独立review使用全新Agent，不能复用作者。review要求revise时修复回环有预算；缺输入/工具失败记录retry原因，预算耗尽报告阻塞。

awaiting_approval时展示作品及验收结果，只有用户具体决定后才approve，不把启动流程当作批准未来作品。全部accepted后package。交付前验证manifest每个文件大小/hash并展示文本作品与限制；不能把合成单测通过说成创作质量保证。

本版支持brand/conversion广告和standalone艺术/娱乐/公共短片，realism风格；连载、纪录片、未知风格需能力建设，返回具体缺口。开发新能力时调用skill-building-expert，研究→方法卡→编译→独立试用→发布；不要在现有run中静默替换锁定Skill。
