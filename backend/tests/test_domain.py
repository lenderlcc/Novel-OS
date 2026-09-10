import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4

import pytest

from novel_os.domain.core import ChapterVersion, CommandContext, Requirement, VersionToken
from novel_os.domain.enums import ActorType, Status
from novel_os.domain.errors import DomainError


@pytest.mark.parametrize("expected,actual", [(1, 2), (-1, 0), (True, 1), ("1", 1)])
def test_stale_or_invalid_version_token(expected, actual):
    with pytest.raises(DomainError, match="version has changed"):
        VersionToken(expected).check(actual)


def test_initial_version_token_and_immutable_domain_snapshot():
    VersionToken(0).check(0)
    version = ChapterVersion(
        project_id=uuid4(),
        chapter_id=uuid4(),
        content="Original",
        change_reason="First draft",
        created_by="user",
    )
    with pytest.raises(FrozenInstanceError):
        version.content = "Overwrite"


@pytest.mark.parametrize("status", [Status.APPROVED, Status.SUPERSEDED, Status.ARCHIVED])
def test_approved_and_historical_requirement_reject_direct_edit(status):
    requirement = Requirement(
        project_id=uuid4(), scope_id=uuid4(), created_by="user", content="Must", status=status
    )
    with pytest.raises(DomainError) as error:
        requirement.require_editable()
    assert error.value.code == "INVALID_STATE"


@pytest.mark.parametrize("actor", [ActorType.AGENT, ActorType.SYSTEM])
def test_system_and_agent_are_not_user_authority(actor):
    with pytest.raises(DomainError) as error:
        CommandContext("request", "actor", actor).require_user()
    assert error.value.code == "AUTHORITY_DENIED"


def test_domain_has_no_framework_or_orm_dependencies():
    directory = Path(__file__).resolve().parents[1] / "novel_os/domain"
    for path in directory.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("fastapi", "sqlalchemy", "novel_os.models")
                )
            elif isinstance(node, ast.Import):
                assert all(
                    not item.name.startswith(("fastapi", "sqlalchemy")) for item in node.names
                )
