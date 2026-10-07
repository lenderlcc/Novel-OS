# NOVEL-014 Character Depth & Voice evaluation

这些离线合成材料用于后续真实模型与人工验收。当前 **Real Provider: NOT_RUN；Human Behavior Acceptance: NOT_EVALUATED**。文件存在、Schema 校验通过或 Mock 回归通过，都不能证明人物表现已改善。

- `characters.json`：三个固定人物身份，A/B 两份稀疏 Profile，以及 A 面对 B/C 的关系修饰。Body 使用 `novel_os.characters.schemas.CharacterBehaviorProfileBody`，没有独立评估 Schema。
- `cases.json`：五个场景及 Review、Revision、Feedback 后续评估材料。
- `weak-character-source.txt`：人工编写、故意缺乏人物差异的短正文，供诊断与局部修订评估。它不是模型结果。
- `manual-evaluation.md`：运行信息、Context 证据和人工判断模板。

## 输入边界与准备

不新增 runner、评分服务或自动重试。使用现有角色/Profile API、章节工作流、Worker、Review、Revision 和 Human Feedback 链路。真实调用需用户明确授权；本次未调用 Provider、未创建运行时 Project，也未写开发数据库。

材料中的 UUID 只用于互相引用，不能当成真实数据库对象。若实际执行，先在隔离项目创建角色，把固定 ID 映射到真实 ID，尤其替换 `relationship_modifiers[].other_character_id`。通过现有 `/drafts` 创建，再由用户 `/approve`；不能直接写 APPROVED 行。保存实际 Profile version/hash 与审批记录。C 没有 Profile 也应正常工作。

每个运行变体都提供点名人物的 `raw_requirement`。将所选变体的这段文字提交到现有章节需求入口；若实际角色改名，同步改文字里的姓名。`involved_character_ids` 是评估控制说明，不是 API 绑定，不能指望只提交 UUID 或“主角”就选中 Profile。批准 Scene Plan 时保留实际人物姓名，并核对唯一 POV 的真实 `pov_character_id`。通过已有 Context 构建/Debug 先确认 `approved-character-behavior-profiles` selector 的角色、source ID、version/hash 和相应关系 Modifier，再进行真实模型工作；选择遗漏时先修正正常输入，不手工注入 Context。

仅把所选 Case 的 `input`、相关人物身份/状态/知识和实际已批准 Profile 放入 Context。`evaluator_only`、验收状态、对照输出、预期观察、未涉及的关系 Modifier 和其余 Case 都不进入 Prompt。CDV-04 的 Secret X 只供人工核查，不能发送给 Writer。CDV-05 使用另一个没有任何 BehaviorProfile 的历史兼容项目，不能靠在已有批准 Profile 的项目中漏传它来模拟。

CDV-01 的两次运行保持同一情境、工具、目标、知识与必需结果；只切换焦点人物。比较前冻结同一份已批准 WritingProfile，并将 narrative_perspective 设为 THIRD_PERSON，与原始需求及批准 POV 保持一致。CDV-02 保持 A 的目标与外部条件，记录 A 对 B/C 的表达差异，也单独记录 B 自身 Profile 对回应的影响。两例都允许出现相同事件结果；人物差异应从注意、选择、回避和防御中判断。

## 离线 Schema 校验

在仓库根目录运行以下检查即可验证 Profile Body 和关系引用。它不连接数据库或调用模型。

```bash
backend/.venv/bin/python - <<'PY'
import json
import sys
from pathlib import Path
sys.path.insert(0, 'backend')
from novel_os.characters.schemas import CharacterBehaviorProfileBody
fixture = json.loads(Path('evals/character-depth/characters.json').read_text())
ids = {character['id'] for character in fixture['characters']}
for character in fixture['characters']:
    record = character['behavior_profile']
    if record is None:
        continue
    body = CharacterBehaviorProfileBody.model_validate(record['body'])
    assert all(str(m.other_character_id) in ids for m in body.relationship_modifiers)
    assert all(str(m.other_character_id) != character['id'] for m in body.relationship_modifiers)
print('Profile fixtures valid; behavioral evaluation remains NOT_RUN.')
PY
```

## 人工方法

先核对真实 ContextPackage、SourceVersions、PromptLineage 和批准 Plan，再通读 Plan/Draft。遮去姓名，比较人物为何这样观察、判断、回应；不规定必须说哪句话，不按关键词或逐句文本计算分数。沉默、打断、误会和玩笑都不是每场必须出现的动作。

每项判断附具体段落和影响。结果可用 `PASS / CONCERN / FAIL / NOT_EVALUATED`，不要把未执行项填成 PASS。一次输出也不能证明长期稳定性。NOVEL-013 的真实创意效果仍为 PENDING；本评估不调整 Candidate 数量或 Selection Policy，也不开始 NOVEL-015。
