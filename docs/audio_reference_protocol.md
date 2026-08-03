# Audio Reference Protocol

Seedance 等多模态视频工具支持音频作为声音参考。凡是镜头中有台词、旁白、录音留言或可听见人声，都必须管理音色参考。

## 音色资产类型

```text
父亲音色参考
母亲音色参考
成年儿子音色参考
旁白音色参考
```

## 何时必须 @AUDIO

必须 `@AUDIO` 的情况：

- 角色对白。
- 旁白。
- 电话录音。
- 视频留言。
- 新闻播报或广播中需要稳定音色的声音。

不需要 `@AUDIO` 的情况：

- 纯环境音。
- 无人声的动作镜头。
- 只需要写“远处嘈杂人声”且不要求具体音色。

## 缺失音色时的处理

如果某个 shot 有人声，但缺少对应音频参考：

1. 停止生成该 shot 的最终视频提示词。
2. 向用户索要对应角色的音频参考。
3. 如果用户允许临时继续，使用文字音色占位，并在状态表中标记：

```text
audio_reference_status=missing
next_action=需要用户提供音色参考
```

占位版不可标记为最终可生产。

## 音色清单

每个项目应建立：

```text
outputs/assets/audio/voice_reference_manifest.json
outputs/assets/audio/voice_reference_assets.md
```

字段建议：

```json
{
  "name": "父亲音色参考",
  "speaker_asset_name": "父亲",
  "reference_file": "./references/audio/father.wav",
  "status": "provided | needed | missing | placeholder",
  "voice_direction": "低声、疲惫、克制、愧疚",
  "required_for_videos": ["V007", "V011"]
}
```

## 视频提示词写法

资产声明：

```text
@父亲音色参考（声音参考）
```

正文：

```text
@父亲_受伤状态 使用 @父亲音色参考，声音压低，语速偏慢，句尾下沉：
“对不起。”
```

## 状态表字段

`production_status.csv` 至少包含：

```text
dialogue_required,audio_reference_status,audio_reference_id
```

有台词但 `audio_reference_status != provided` 的 shot 不能进入最终视频生成。
