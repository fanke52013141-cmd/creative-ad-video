# 开发与试用状态

记录框架与 Skill 的真实执行进展。合成单元测试通过不代表创作质量；本文件只记录真实子 Agent 试用的流程行为与门禁结果。

## 2026-10-24 第二次真实试用：shortfilm 路线（script-shortfilm 首次执行）

- Run：`../video-flow-runs/shortfilm-demo`（run_id `0e2148476c574f2cb01b4de926d0e521`，仓库外），交付包 `PKG-07f22e722a914a99b8a42fb8a953497c`。
- Brief：`examples/video_flow/shortfilm-brief.json`（《最后一盏灯》：art/standalone/realism，90 秒横屏、无对白、一景两人）。
- 模式与协议同首次试用（automatic；dispatch → 全新上下文 spawn → bind → 回执 → submit）。12 个任务、12 个独立子 Agent、10 阶段全部 accepted 并 package。
- 产物：《最后一盏灯》story 5 场 90.0s（包子铺双路灯，父亲摸黑干活、女儿按下主灯接手、围裙让渡）；style 修订版七轴（光账本/声账本）；storyboard 21 镜（S04 六镜选择链，接杖在拖凳之前的次序三方互锁）；assets 22 项（双路灯具为核心资产）；edit_sound 21 条（无对白无配乐，两声开关咔哒可辨）。

### 修订回环（第二次触发）

style 首版被判 revise（1×P1：STY-07 S04 声事件序列把凳子拖地排在接杖之前，与锁定剧本及自身光账本矛盾；2×P2）。修订版重排声事件并加防回退禁令，复审 pass（story_fit 3 / coherence 3 / executability 3，残留 2×P2）。两次 run 的 revise 都发生在 style 阶段且都是「声画次序与锁定事实矛盾」类缺陷，提示 art-direction 技能对跨轴次序一致性的自检是最值得加固的环节。

### 门禁与执行情况

- 本轮无回执哈希/字段类型拦截（工作者均已按协议用脚本复制哈希、按标量类型写字段——首次试用的两条改进在第二次全部见效）。
- 遇到三次宿主 `model concurrency limit exceeded`，等待后重试 spawn 均成功；未影响产物完整性。
- 一次 style 修订轮 spawn 在并发限制下中断留下草稿，新工作者按任务包核验后收编覆写；框架按候选最终字节验收，无影响。

### Skill 执行登记

script-shortfilm 首次真实执行（story 首轮 pass：constraints 4 / causality 4 / visualization 4 / duration 3 / route_fit 4）；其余 8 个已试 Skill 均完成第二次执行，第二次评分最低仍为 3。各 package.json 已更新（`2_real_trials_passed` / script-shortfilm `initial_real_trial_passed`）。

### 诚实边界

- 两次 run 均为 90 秒内短片/广告、realism、单空间小人物数；多场景、多人物、长时长、非写实仍未试。
- retry/invalidate/invalidate 级联与越权篡改测试仍未演练；无任何真实媒体生成。
- 第二次 run 的评审分数是当轮评审员的判断；仍不据此宣称创作质量优秀。

## 2026-10-24 首次真实子 Agent 端到端试用

- Run：`../video-flow-runs/demo`（run_id `9255ece84f3d452590414885138db9e9`，仓库外）。
- Brief：`examples/video_flow/coffee-brief.json`（虚构品牌「同桌咖啡」，brand/standalone/realism，30 秒竖屏）。
- 模式：`--approval automatic`；pass 评审自动过人工门禁，协调器未伪造用户批准理由（尝试显式 `approve` 时按设计被拒：stage not awaiting approval）。
- 执行方式：主 Agent 按 `adapters/codex.md` 协调——dispatch → 以全新上下文 spawn 子 Agent（只传任务包、`docs/contracts.md`、锁定 Skill 快照）→ `bind` 真实 agent_id → 工作者补写回执 → `submit`。
- 规模：12 个任务、12 个独立子 Agent；10 阶段全部 accepted；`package` 生成 `PKG-a7319325a0c4432aaada73f387d9bba9`，含 brief/route/5 个创作产物/5 个评审共 12 个文件与限制声明（preproduction_text、acceptance 级）。

### 修订回环

style 首版被独立评审判 revise（2×P1：S03 声音事件次序与锁定剧本倒置；苏晓笔记本状态缺失导致中央道具连续性断裂，另 4×P2）。修订任务包正确携带 `repair_feedback`；修订版对 P1 逐条修复并三方互锁，复审 pass（story_fit 4 / coherence 3 / executability 3，残留 3×P2）。回环按 repair_limit 预算内完成。

### 门禁拦截到的真实缺陷

验收门禁在本次试用中拦下四类真实问题，均为子 Agent 实际产出缺陷，非构造用例：

1. assets 首次 submit 被拒：回执 `input_hashes.brief` 手抄错 1 字符（`4db9a12a`→`4db9a12c`）。
2. assets 再次 submit 被拒：`continuity_rules` 写成结构化对象，可执行契约要求非空字符串（docs/contracts.md 未写明标量类型，工作者按专业直觉产出结构化账本；后把结构挪入附加字段 `continuity_detail` 通过）。
3. edit_sound_review 首次 submit 被拒：`target_sha256` 手抄错 1 字符（`dc55f`→`dc55d`）。
4. style 首版内容缺陷（见上）被独立评审拦下。

另有一次子 Agent 唤醒遇到宿主 provider 临时故障（stream 恢复重试上限），重发消息后成功，未影响产物完整性。

### 各 Skill 实际执行

| Skill | 本次执行 | 结果 |
| --- | --- | --- |
| script-ad | 是（story 作者） | 首轮 pass（constraints 4 / causality 4 / visualization 4 / duration 3 / route_fit 4，3×P2） |
| script-review | 是（story 评审） | 如上给出 pass，附 3×P2 |
| art-direction | 是，两轮（作者） | 首版 revise（2×P1）；修订版复审 pass |
| production-review | 是，四次（style 首审 revise、style 复审 pass、assets_review pass、edit_sound_review pass） | 评分最低 3，无放水性 pass |
| storyboard-direction | 是（storyboard 作者） | 8 镜 30.0s；评审 pass（narrative 4 / space 4 / continuity 3 / rhythm 3 / style 4 / sound 4 / feasibility 4，4×P2） |
| storyboard-review | 是（storyboard 评审） | 如上给出 pass |
| asset-planning | 是（assets 作者） | 16 项资产；经两次门禁修复后 pass（coverage 3 / identity 4 / state 3） |
| edit-sound-plan | 是（edit_sound 作者） | 8 条；pass（coverage 4 / motivation 4 / sound_space 4） |
| run-video-flow | 是（主 Agent 协调，按 SKILL 执行） | 流程完整走通 |
| script-shortfilm | 否 | 本次路线为 advertising，未触发 |
| skill-building-expert | 否 | 本次未建设新 Skill |

### 试用暴露的缺口与本次改进

- `docs/contracts.md` 已补一句字段类型说明：除 `shot_ids` 为字符串数组外，其余必填字段均为非空字符串。
- 哈希手抄错误出现两次；协议上已要求工作者用脚本复制哈希而非手抄（adapters 建议级，不改引擎）。
- 试用后的仓库级 `scripts/audit_video_skills.py` 复查发现 storyboard-direction 包声明与内容不符：SKILL.md 与两个案例引用的契约模式、四份合成样例 JSON 与包内验证脚本从未创建（schemas、scripts 目录为空）。已按案例文本补齐：两份合成输入与两份分镜样例（coffee 8 镜 30s、silent 10 镜 60s）、契约模式、对接 `video_flow/contracts.py` 的机械回归脚本 `.agents/skills/storyboard-direction/scripts/validate_package.py`（六类故障注入全部被拒），并把 evaluation/README 的验证状态改为与实际一致。此前 run 的锁定快照不受影响。

### 诚实边界与未完成

- 这是 1 次 run、1 条路线（advertising/realism）、1 个 brief 的试用；不是多路线、多风格、故障注入、并发或越权场景的系统性评估。
- 评审分数是子 Agent 评审员的判断，本记录不据此宣称创作质量优秀。
- 专业 Skill 仍为 baseline：单次真实试用通过不等于完成行为评估；`script-shortfilm`、连载、纪录片、非写实风格路线仍未试。
- `retry`/`invalidate` 未走完整用例（仅一次宿主故障重试）；无任何真实媒体生成，交付物为前期文本包。
