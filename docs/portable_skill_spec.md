# Portable Skill Contract

## 结论

各 Agent 平台的安装目录、frontmatter、工具调用和触发机制并不完全一致，因此不存在可以原样复制到所有平台的单一原生 Skill 文件。项目采用“两层规范”：平台无关核心契约 + 平台适配封装。

## 平台无关核心契约

每个能力必须定义：

- `id`：稳定的小写连字符标识。
- `purpose`：单一职责。
- `triggers` 与 `non_triggers`：何时调用、何时不调用。
- `inputs`：字段、格式、必需性、来源和信任边界。
- `outputs`：机器产物路径、Schema 和人类审阅产物。
- `config_keys`：可配置业务参数。
- `procedure`：有顺序的执行步骤和决策分支。
- `quality_gates`：阶段内检查点。
- `failure_policy`：阻塞、回退、询问和重试规则。
- `tool_dependencies`：图片生成、浏览器、文件系统或外部系统能力。
- `version`：契约版本。

下游只能依赖机器产物和 Schema，不依赖某个平台的自然语言展示格式。

## Codex 适配

- 路径：`.agents/skills/<id>/SKILL.md`。
- frontmatter：`name` 和 `description`。
- 可选界面元数据：`agents/openai.yaml`。
- 长方法论：`references/`。
- 确定性操作：`scripts/`。

## 其他平台适配

转换时保留核心契约，只映射：安装路径、元数据字段、触发方式、工具名称、权限声明和资源加载语法。若平台不支持自动触发，用显式命令或主 Agent 路由器调用；不得复制一套新的业务输出格式。

## 本项目的一致性规则

1. 所有平台共享 `config/pipeline.yaml` 和 `schemas/`。
2. 垂类只覆盖策略槽。
3. `story.md`、`style_bible.md`、`storyboard.json`、资产 manifest、图片 queue/result manifest 是跨平台稳定接口。
4. 表格、段落、XML 标签或 Markdown 标题只是展示方式，不能成为节点之间唯一的数据接口。
5. 平台适配器不得改变业务字段语义。

