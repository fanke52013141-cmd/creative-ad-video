# 开发与试用状态

记录框架与 Skill 的真实执行进展。合成单元测试通过不代表创作质量；本文件只记录真实子 Agent 试用的流程行为与门禁结果。

## 2026-10-25 v0.2 离线实施与验证

本节例外记录工程验证，明确区别于下文真实创作试用：116项单元/集成/故障测试通过（49.328秒），doctor验证16个原流程阶段与18个制作阶段，流程契约、文档引用、仓库政策检查退出码均为0。

仓库外证据：`../video-flow-runs/v02-implementation-checks/verification-r001/result.json`，逐条测试输出在同目录unit-tests.stderr.txt。固定F01包：`../video-flow-runs/v02-acceptance-F01-r001/delivery`；证据evidence.json记录18阶段、29个合成任务、10张合成图、4份视频提示词及audit clean。样例标签为synthetic_package_ready；图片是色块协议夹具。

已验证：详细文本与三类图片目录导出、板格与片段覆盖、相对路径迁移、名称/哈希/时序拦截、素材导入、原剧本来源校验、精确局部返修、旧任务拒收与旧包保留。视频生成无调用。

待完成：真实图像provider执行与超时请求去重、真实人物/物品连续性目检、正式Skill行为试用、Codex与DeepSeek完整新版本创作试跑。默认图片导入；generate路线当前明确阻断，不因为有模型名称就宣称自动生成可用。新专业Skill为draft，研究深度与行为评估未满足全部发布目标。

## 2026-10-24 第三次真实试用：媒体扇出层（--media run 全链路）

- Run：`../video-flow-runs/shortfilm-media`（仓库外），交付包 `PKG-992cd52647b34b32b95628f90a867737`，交付等级 `preproduction_text_and_reference_media`，manifest 25 文件（16 JSON + 9 张带 SHA256 的参考图）。
- 内容：《最后一盏灯》第二稿（新故事：宿舍楼断电夜，门卫老周与电工小马，台灯-扳闸-赠灯）。文本 10 阶段 + asset_media 4 项（值班室/老周/小马/窗与窗外）+ board_media 5 板 + 两份媒体评审，全部 accepted。
- 生成纪律实测：9 张图全部由全新上下文子 Agent 按 generate-media 技能逐项生成——一任务一图、任务包只含单项切片与全局约束、图片哈希进 manifest；主 Agent 全程未生成任何一张图。每次媒体调用 low 质量（约 $0.005/张）。

### 单项修订回环（媒体层首次触发）

board_media 首轮评审（评审员用 Read 真实目检 5 张图）判 revise：P1×2——BOARD-S02 小马手搭老周肩背违背「未触及」锁定；BOARD-S03 闸箱被画到画左且变形为高体立柜，违背「桌左箱右不翻转」与跨板道具同一性。引擎按预期只重开被点名项（S04/S05 保留 done 状态），三个修订任务包正确携带 repair_feedback。修订工作者各自迭代：S02 以「横向并排+两身影间必须可见背景」的构图约束根治肢体粘连；S03 三版迭代修正空间锁；S01 消化 P2（闸箱形制）。复审 pass（4/4/4，残留 2×P2 限 S02 光束指向与悬停距离，留给下游视频提示词阶段）。

### 生成式图像的典型缺陷模式（实测记录）

- **人物肢体粘连**：双人接触类动作（僵持/交接）易被生成模型画成实际肢体接触——S02 首版与 S03 修订第一版均复现，需在提示词中用几何约束（间隙可见、背景穿缝）显式排除。
- **道具空间漂移**：连续性道具（闸箱）跨板生成时位置/形制漂移（画左→高体立柜），需逐板重复「桌左箱右+挂壁扁平箱体」锚点并目检。
- 工作者自主目检（Read 图片）在修订轮成为有效质检手段；首轮图未目检直接交卷的两板正是被判 P1 的两板。

### 诚实边界

- 参考图为 low 质量初始稿：人物跨图一致性（老周/小马在 4 张不同图中的面孔差异）未做一致性约束（无 reference_images 串联），仅提示词锚点；进入视频提示词阶段前如需一致性需引入图生图。
- 评审员的目检是子 Agent 判断，非用户验收；automatic 模式下媒体评审 pass 直接过门禁，用户可对任何单项 `invalidate --item` 重生成。
- 视频提示词、音频、视频生成本身仍不在范围内。

## 2026-10-24 首次真实媒体生成（资产参考图，宿主 skill 通道）

- 通道：宿主 `toapis-image-gen` skill → ToAPIs `gpt-image-2.5-flare-vip`（质量 low、像素尺寸直传、按 token 后付费）；密钥存于宿主 skill 目录 `api_key.txt`，不进 git、不在文档回显。冒烟测试一张（1024x1024，~$0.005）通过：提交→轮询→下载链路完整。
- 产物：shortfilm-demo run 首批三张资产参考图，存于 run 目录 `media/asset_images/`（按仓库策略不入 git）：
  - `ASSET-001_father_laozhou.png`（1024x1536，2.3MB）——父亲老周人物参考
  - `ASSET-002_daughter_xiaoman.png`（1024x1536，2.1MB）——女儿小满人物参考
  - `ASSET-005_shop_space.png`（1280x720，1.2MB）——店堂空间参考（S01 状态：小灯亮、街道全黑）
- 提示词从 run 已打包的 assets.json 逐字派生（一任务一图，未合并资产）；机械校验通过：PNG 有效、尺寸正确、亮度分布与光设定一致（人物图 63–65% 暗部+点状高光；空间图 94% 暗部、0.7% 高光，符合「一盏小灯照案板」）。
- 诚实边界：本批为像素级人工目检前的机械核验；尚未接入 workflow 媒体阶段与 manifest 哈希体系（V1 仍为 preproduction_text），接入需要新的 workflow 阶段、provider profile 与媒体审批设计——这是媒体生成层的下一项工作。

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
