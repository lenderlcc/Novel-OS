import pytest

from novel_os.agents.runtime import TECHNICAL_ERRORS, execution_failure
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.quality.policy import indexed_paragraphs, paragraphs
from novel_os.quality.schemas import ParagraphEvidence
from novel_os.revision.evidence import RevisionEvidenceError, check_revision_evidence


def evidence(index, text):
    return ParagraphEvidence(paragraph_index=index, excerpt=text, reason="原稿证据")


def test_one_hundred_paragraphs_use_server_indices_including_title_and_blank_lines():
    content = "  标题\r\n\r\n" + "\n \n".join(f"第{n}个段落。" for n in range(2, 101))
    table = indexed_paragraphs(content)
    assert len(table) == 100
    assert table[0] == {"paragraph_index": 1, "text": "标题"}
    for index in [1, 47, 48, 72, 73, 100]:
        entry = table[index - 1]
        check_revision_evidence([evidence(entry["paragraph_index"], entry["text"])], content)
    # Correct literal quote in the wrong paragraph remains invalid; no auto-rebinding.
    for claimed, actual in [(47, 48), (73, 72)]:
        with pytest.raises(RevisionEvidenceError) as exc:
            check_revision_evidence([evidence(claimed, table[actual - 1]["text"])], content)
        assert execution_failure(exc.value).error_code == "REVISION_EVIDENCE_MISMATCH"
        assert exc.value.code in TECHNICAL_ERRORS


def test_source_and_candidate_tables_have_independent_indices():
    source = "她推开门。\n\n他放下旧伞。\n\n雨还在下。"
    candidate = "她推开门。\n\n门轴响了一声。\n\n他放下旧伞。\n\n雨还在下。"
    old, new = indexed_paragraphs(source), indexed_paragraphs(candidate)
    assert old[1]["text"] == new[2]["text"]
    check_revision_evidence([evidence(2, old[1]["text"])], source)
    check_revision_evidence([evidence(3, new[2]["text"])], candidate)
    with pytest.raises(RevisionEvidenceError):
        check_revision_evidence([evidence(2, old[1]["text"])], candidate)


@pytest.mark.parametrize("quote", ["她说。\n\n他答。", "她说。……他答。", "她说了。", "伪造内容"])
def test_indexed_context_does_not_allow_cross_paragraph_or_invented_quotes(quote):
    with pytest.raises(RevisionEvidenceError):
        check_revision_evidence([evidence(1, quote)], "她说。\n\n他答。\n\n灯灭了。")


def test_repeated_quote_must_still_match_the_explicit_paragraph():
    content = "他停住了。\n\n灯亮着。\n\n他停住了。"
    for index in [1, 3]:
        check_revision_evidence([evidence(index, "他停住了。")], content)
    with pytest.raises(RevisionEvidenceError):
        check_revision_evidence([evidence(2, "他停住了。")], content)
    assert [entry["text"] for entry in indexed_paragraphs(content)] == paragraphs(content)


def test_current_prompts_use_tables_without_overwriting_prior_versions():
    registry, prompts = TaskDefinitionRegistry(), PromptRegistry()
    for task_type, current, old in [
        ("PLAN_CHAPTER_REVISION", 7, 3),
        ("REVISE_CHAPTER", 8, 3),
        ("VALIDATE_REVISION_FIDELITY", 5, 2),
    ]:
        module = prompts.resolve(registry.get(task_type).task_template)
        assert module.module.version == current
        assert "target-version.paragraphs" in module.content
        assert "Copy the paragraph_index" in module.content
        assert "proposed_changes=[]" in module.content
        previous = prompts.resolve(ModuleRef(module_id=module.module.module_id, version=old))
        assert "Indexed paragraph citation protocol (server supplied)" not in previous.content
