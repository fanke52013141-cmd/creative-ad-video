# 广告剧本输入输出契约

本契约是广告专业层的字段说明。运行时以项目通用 artifact Schema 和锁定任务包为准；新增通用字段时由主代理协调，作者不能另建一套阶段标准。这里的例子是合成输入，不代表实际客户与真实投放。

## 输入来源与消费者

`task_id` 来自调度任务；`objective` 来自需求中已经明确的传播目标；`audience` 来自客户研究或被标记为假设的受众描述；`facts` 来自被允许使用的证据原文及引用；`constraints` 来自需求、制作资源和渠道 profile；`input_refs` 保存上游 artifact 路径、revision 与 hash；`skill_ref` 保存已选 Skill 的版本与 hash。没有研究时只能说“暂定受众”，不能创造调查百分比。

主目标至少要能写成“让某人在看完后知道、相信或去做什么”。品牌认知可接受“认出品牌与使用处境的关联”，不要求每条认知广告都强行下单。公益主目标需要行动主体、动作和适用边界；“让世界更美好”不足以成为可执行目标。若无法确定传播对象是公众还是内部员工，剧本语气与行动入口都会改变，应先请求该字段。

## 候选骨架

```json
{
  "task_id": "synthetic-coffee-story-r1",
  "type": "story",
  "revision": 1,
  "status": "candidate",
  "title": "先把这句说完",
  "objective": "让通勤者理解门店支持提前下单后到店取杯",
  "input_refs": [],
  "skill_ref": {"id": "script-ad", "version": "0.1.0"},
  "assumptions": [],
  "items": [
    {
      "id": "sc01",
      "scene_goal": "让观众识别被催促打断的处境",
      "location": "办公楼一层取餐台",
      "characters": ["林澄", "店员"],
      "duration_seconds": 5,
      "action": "林澄刚开口说明杯型，手机会议提醒响起。店员抬手指向已贴名字的纸杯。",
      "dialogue": [{"speaker": "林澄", "text": "我先说完这句。"}],
      "voiceover": "",
      "onscreen_text": [],
      "brand_role": "取杯流程触发动作变化",
      "evidence_refs": ["brief.fact.preorder"],
      "transition_reason": "已准备好的杯让她从等待转向确认领取",
      "production_notes": "使用虚构门店与包装，演员和店员在室内完成"
    }
  ],
  "total_duration": 5,
  "open_questions": []
}
```

上例只演示字段，不是完整广告。`duration_seconds` 必须为大于零的有限数值；所有场时长之和与 `brief.duration_seconds` 的差不得超过半秒。`dialogue` 可为空数组，但不能用“自行发挥”隐藏关键台词。`action` 必须包含可拍摄的主体、行为与结果；“氛围高级，用户感动”不是实质动作。`scene_goal` 服务评审，`action` 服务导演与分镜，`brand_role` 服务广告关联检查，`evidence_refs` 服务事实追溯。

## 可选补充与权限

可按任务附 `strategy`、`logline`、`characters`、`claim_map`、`cta`、`alternatives`，但不得把这些补充当成分场的替代品。`claim_map` 建议逐条记录主张、出现的 item、证据与表述边界。情绪承诺如“放心”仍可能暗示安全或效果，应检查上下文；没有写数字并不意味着没有主张。

receipt 必填 `task_id`、`agent_id`、`skill_sha256`、`input_hashes`、`output_sha256`，并可记录产物路径、执行的检查和未执行的检查。它表达“我交付了什么、我检查了什么”，不能表达独立评审已通过。作者不能填写 `approved_by`、不能复制用户的签名、不能创建 review 产物或更新 approval registry。若任务包要求的 receipt 路径与本例不同，服从任务包。

## 失败返回

`needs_input` 说明阻塞字段、为何影响剧本和最小所需资料，例如缺少实际领取方式会导致片尾动作不可兑现。允许同时提交明确标为 exploratory 的路线建议，但不能把未知领取方式写进正式 candidate。事实冲突时引用两个来源位置并请求主代理裁定；时长冲突时给出删减方案。所有失败都要保留任务编号，便于调度继续，不应只说“资料不够”。
