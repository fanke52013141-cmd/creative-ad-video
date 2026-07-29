# Skill: asset_executor
**Version**: 2.0.0

## Purpose
从 `story.md` 和 `storyboard.json` 中固定后续生产需要的稳定资产：人物身份与持续变体、场景空间与结构变体、必要核心道具。

本 Skill 是资产命名、素材绑定和分镜资产映射的唯一来源。它不写图片提示词，不生成图片，不决定视频合并。

核心目标不是把资产拆成身份包，而是把每个需要生成图片提示词的资产固定成最小单位：

```text
asset_type + asset_name + output_prompt_path
```

人物资产只在身份可见特征发生持续变化时拆分。情绪、动作、景别、光线和机位不是人物资产变体理由。

## Inputs
```json
{
  "story_markdown_path": "./outputs/story.md",
  "storyboard_json_path": "./outputs/storyboard.json",
  "reference_media": []
}
```

## Outputs
```json
{
  "asset_manifest_path": "./outputs/asset_manifest.json",
  "shot_asset_map_path": "./outputs/shot_asset_map.json"
}
```

## Character Asset Naming

人物基础资产采用稳定人物名；确有持续变体时采用：

```text
人物稳定名_变体名
```

示例：

```text
林小满
林小满_雨夜居家装
林小满_受伤后
林小满_十年后
```

规则：

- `林小满` 是稳定人物名。
- 只有年龄、持续服装、持续发型、持续伤痕、身份转变或用户明确要求才拆变体。
- 哭泣、愤怒、接电话、走路、坐下等临时表演写入分镜，不拆资产。
- 中景、全景、俯视等镜头表达不拆资产。
- 资产名禁止包含或以“状态”二字结尾。
- 禁止默认输出 `林小满_人脸大头特写` 和 `林小满_全身妆造` 两个资产。
- 禁止用 `CHAR_001`、`AssetA` 之类内部 ID 当人物名。

同一人物变体仍共享稳定人物身份锚点，不得重新设计五官、骨相和基础体型。

## Scene Asset Naming

场景资产名采用稳定场景名：

```text
雨夜客厅场景
宿舍场景
悬崖竹林场景
```

不因为普通光线、时间、天气变化拆新场景资产。只有地点、空间结构或不可兼容的持续布景变化，才新建场景变体。

## Prop Handling

不需要把画面所有道具逐一生成或描述。只管控核心剧情道具。

道具分三类：

1. `inherited_from_reference`
   - 参考素材里已有的普通道具。
   - 默认保留，不单独生成，不额外描述。

2. `text_prompt_control`
   - 需要新增、出现、移动或被人物交互的关键道具。
   - 不生成独立道具图，后续在视频提示词正文中描述。

3. `generate_independent_prop`
   - 剧情关键、反复出现、需要特写、外形复杂或状态变化明显的道具。
   - 才生成独立道具资产提示词。

## Key Item Marking

对于道具资产（props），在 `asset_manifest.json` 中额外标记关键物品和出现次数：

- `is_key_item`（布尔）：是否为关键物品。关键物品 = 贯穿全片、多次出现、对剧情推进有作用的道具（如信件、钥匙、礼物等）。
- `recurrence_count`（整数）：该道具在分镜中出现的总次数。
- `appearances`（字符串数组）：该道具出现的 `shot_id` 列表。

判断规则：
- 道具在 2 个及以上分镜出现，且对剧情有推进作用 → `is_key_item: true`
- 道具只在 1 个分镜出现，或仅为背景物件 → `is_key_item: false`
- `recurrence_count` 和 `appearances` 从 `shot_asset_map.json` 统计得出

这些字段供下游 `prop_prompt_generator` 和 `storyboard_prompt_generator` 使用：
- 关键物品的提示词强调外观一致性锁定
- 分镜提示词的资产引用区会标注关键物品及其出现次数

## asset_manifest.json Contract

```json
{
  "naming_policy": "asset_name_with_state_when_needed",
  "characters": [
    {
      "asset_id": "character.lin-xiaoman.rainy-home",
      "asset_type": "character",
      "canonical_name": "林小满",
      "variant_name": "雨夜居家装",
      "asset_name": "林小满_雨夜居家装",
      "seedance_label": "林小满",
      "variant_reasons": ["persistent_costume_change"],
      "generation_required": true,
      "handling_policy": "generate_character_state_reference",
      "reference_layout": "character_identity_quad_v1",
      "output_prompt_path": "./outputs/assets/characters/prompts/林小满_雨夜居家装.md",
      "canonical_path": null,
      "approval_status": "pending",
      "notes": "同一人物变体，身份锚点继承林小满"
    }
  ],
  "scenes": [
    {
      "asset_type": "scene",
      "asset_name": "雨夜客厅场景",
      "seedance_label": "雨夜客厅场景",
      "generation_required": true,
      "handling_policy": "generate_scene_reference",
      "output_prompt_path": "./outputs/assets/scenes/雨夜客厅场景.md"
    }
  ],
  "props": [
    {
      "asset_type": "prop",
      "asset_name": "手机",
      "seedance_label": "手机",
      "generation_required": false,
      "handling_policy": "text_prompt_control",
      "is_key_item": false,
      "recurrence_count": 1,
      "appearances": ["S001"],
      "output_prompt_path": null,
      "notes": "普通手机不生成独立道具图，后续视频提示词正文控制"
    },
    {
      "asset_type": "prop",
      "asset_name": "信件",
      "seedance_label": "信件",
      "generation_required": true,
      "handling_policy": "generate_independent_prop",
      "is_key_item": true,
      "recurrence_count": 3,
      "appearances": ["S001", "S005", "S012"],
      "output_prompt_path": "./outputs/assets/props/prompts/信件.md",
      "notes": "关键物品，贯穿全片3次出现，需一致性锁定"
    }
  ]
}
```

## Minimal Asset Prompt Input

资产提示词生成器每次只需要：

```json
{
  "story_markdown_path": "./outputs/story.md",
  "style_bible_path": "./outputs/style_bible.md",
  "asset_type": "character",
  "asset_name": "林小满_雨夜居家装",
  "output_prompt_path": "./outputs/assets/characters/prompts/林小满_雨夜居家装.md"
}
```

不需要：

- `task_id`
- `asset_payload`
- `usage_context`
- `generation_brief`
- `prompt_outputs` 数组
- 单独的 `asset_prompt_tasks.json`

## shot_asset_map.json Contract

```json
{
  "shot_assets": [
    {
      "shot_id": "S001",
      "characters": ["林小满_雨夜居家装"],
      "scenes": ["雨夜客厅场景"],
      "props": ["手机"]
    }
  ]
}
```

`shot_asset_map.json` 是资产与镜头关系的唯一事实源，只映射稳定资产名，不写动作、不写提示词、不写素材分析。`asset_manifest.json` 不重复保存 `appears_in_shots`。

## Procedure

1. 读取 `story.md`，识别剧情中的人物、地点、关键道具和用户参考素材关系。
2. 读取 `storyboard.json`，按 shot 判断实际出现的人物状态、场景和核心剧情道具。
3. 只按持续可见变化拆人物变体，命名为 `人物稳定名_变体名`，禁止"状态"后缀。
4. 不默认拆出人脸大头特写和全身妆造。
5. 为场景选择稳定场景名，不因普通光影、时间、天气变化新建场景资产。
6. 只保留核心剧情道具；普通背景小物件不进资产清单。
7. 判断 `generation_required` 和 `handling_policy`。
8. 统计每个道具在分镜中的出现次数和出现位置，标记 `is_key_item`、`recurrence_count`、`appearances`。
9. 为需要生成提示词的资产写入单个 `output_prompt_path`。
10. 写入 `asset_manifest.json`。
11. 为每个 shot 写入 `shot_asset_map.json`。
12. 校验所有映射资产都存在于资产清单。

## Quality Gate

- [ ] 人物资产只因持续身份可见变化而拆分。
- [ ] 人物资产名不含“状态”后缀。
- [ ] 临时动作、情绪、景别、光线和机位没有被拆成人物资产。
- [ ] 没有默认输出 `人脸大头特写` 和 `全身妆造` 两个资产。
- [ ] 未使用 `CHAR_001`、`ENV_001`、`PROP_001` 或抽象 Asset ID 作为主名称。
- [ ] 场景没有因为普通光线、时间、天气变化被拆分。
- [ ] 只有空间结构或地点变化才新建场景资产。
- [ ] 道具只保留核心剧情道具。
- [ ] 普通背景道具没有强行生成独立资产图。
- [ ] 道具资产包含 `is_key_item`、`recurrence_count`、`appearances` 字段。
- [ ] 关键物品（出现≥2次且有剧情作用）被正确标记为 `is_key_item: true`。
- [ ] 每个需要生成提示词的资产只有一个 `output_prompt_path`。
- [ ] 没有输出 `asset_prompt_tasks.json`、`task_id`、`asset_payload` 或 `prompt_outputs` 数组。
- [ ] 每个 shot 都存在映射记录。
- [ ] `shot_asset_map.json` 中的所有资产都存在于 `asset_manifest.json`。

## Checkpoint Update
通过质量门后更新：
- `current_phase`: `asset_executor`
- `completed_phases`: 追加 `asset_executor`
- `artifacts.asset_manifest`: `./outputs/asset_manifest.json`
- `artifacts.shot_asset_map`: `./outputs/shot_asset_map.json`
- `next_phase.skill`: `asset_prompt_generation`

## Failure Handling

- 分镜动作太抽象导致无法判断人物状态：返回 `storyboard_director` 修正 `action_desc`。
- 人物变体被命名成另一个人物：改回 `人物稳定名_持续变体` 并继承身份锚点。
- 默认拆成大头特写和全身妆造：合并为一个状态资产。
- 场景因光线/时间变化被拆成多个资产：合并为同一个场景资产，光影交给提示词控制。
- 普通道具被强行独立生成：改为 `text_prompt_control` 或从资产清单移除。
- 某 shot 缺少映射：补写该 shot 的人物状态、场景、关键道具关系。
