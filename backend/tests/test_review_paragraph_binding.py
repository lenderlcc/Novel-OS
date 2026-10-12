"""Multi-paragraph reasoning must retain exact individual paragraph evidence."""

import pytest

from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.quality.policy import check_evidence
from novel_os.quality.schemas import ParagraphEvidence


def test_review_uses_versioned_evidence_protocol_without_changing_old_pin():
    prompts = PromptRegistry()
    assert prompts.resolve(
        ModuleRef(module_id="quality-evidence", version=2)
    ).module.content_hash == ("7d56a09ff1512b1185e69017ed1a1910de74b37a42a9ec938eabf43e4f4cc40f")
    for task_type in ("REVIEW_CHAPTER_COMPLIANCE", "REVIEW_CHAPTER_NARRATIVE"):
        definition = TaskDefinitionRegistry().get(task_type)
        selected = prompts.resolve(definition.skills[0])
        assert selected.module.version == 3
        assert "separate evidence entries" in selected.content


def test_separate_quotes_support_dialogue_pattern_without_loosening_validator():
    first = "“带上地图。”她把灯压低。"
    second = "“路不是已经封了吗？”他没有伸手。"
    content = first + "\n\n" + second + "\n\n窗外传来脚步声。"
    entries = [
        ParagraphEvidence(paragraph_index=1, excerpt=first, reason="提出行动"),
        ParagraphEvidence(paragraph_index=2, excerpt=second, reason="回应及迟疑"),
    ]
    check_evidence(entries, content)
    with pytest.raises(ValueError, match="identified Draft paragraph"):
        check_evidence(
            [ParagraphEvidence(paragraph_index=1, excerpt=first + "\n\n" + second, reason="跨段")],
            content,
        )
    with pytest.raises(ValueError, match="identified Draft paragraph"):
        check_evidence([entries[1].model_copy(update={"paragraph_index": 1})], content)
