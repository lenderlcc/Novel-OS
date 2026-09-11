import json
import shutil

import pytest
from prompt_test_support import add_role_v2, edit_manifest

from novel_os.prompts.contracts import ModuleRef, ModuleStatus, PromptConfigurationError, digest
from novel_os.prompts.registry import PromptRegistry


def test_load_exact_and_stable(registry):
    stable = registry.resolve(ModuleRef(module_id="simulation-role"))
    assert stable.module.version == 1
    assert stable.module.status == ModuleStatus.STABLE
    assert stable == registry.resolve(ModuleRef(module_id="simulation-role", version=1))
    assert digest(stable.content) == stable.module.content_hash


@pytest.mark.parametrize(
    "field,value",
    [
        ("module_type", "CONTEXT"),
        ("version", 0),
        ("version", True),
        ("status", "APPROVED"),
        ("content_hash", "wrong"),
        ("created_at", "yesterday"),
        ("content_path", "../../../../../../outside.md"),
        ("compatible_agents", []),
        ("extra", "unrecognized"),
        ("module_id", "../../x"),
    ],
)
def test_invalid_metadata_rejected(library, role_manifest, field, value):
    edit_manifest(role_manifest, **{field: value})
    with pytest.raises(PromptConfigurationError):
        PromptRegistry(library)


def test_duplicate_identity_even_if_identical_rejected(library, role_manifest):
    shutil.copytree(role_manifest.parent, role_manifest.parent.with_name("duplicate"))
    with pytest.raises(PromptConfigurationError):
        PromptRegistry(library)


def test_duplicate_json_keys_rejected(library, role_manifest):
    role_manifest.write_text(
        role_manifest.read_text().replace('"version": 1', '"version": 1, "version": 2')
    )
    with pytest.raises(PromptConfigurationError):
        PromptRegistry(library)


def test_same_version_body_mutation_rejected(library, role_manifest):
    (role_manifest.parent / "content.md").write_text("Silently changed instructions")
    with pytest.raises(PromptConfigurationError):
        PromptRegistry(library)


@pytest.mark.parametrize(
    "dependency",
    [
        {"module_id": "missing", "version": 1},
        {"module_id": "novel-os-core", "version": 99},
        {"module_id": "simulation-role", "version": 1},
    ],
)
def test_unknown_or_cyclic_dependency_rejected(library, role_manifest, dependency):
    edit_manifest(role_manifest, dependencies=[dependency])
    with pytest.raises(PromptConfigurationError):
        PromptRegistry(library)


def test_stable_upgrade_preserves_prepared_versions_and_detects_new_hash(registry, library):
    ref = ModuleRef(module_id="simulation-role")
    v1 = registry.resolve(ref)
    manifest = add_role_v2(library)
    registry.reload()
    assert registry.resolve(ref) == v1
    edit_manifest(manifest, status="STABLE")
    registry.reload()
    assert registry.resolve(ref).module.version == 2
    assert v1.module.version == 1
    assert registry.resolve(ModuleRef(module_id="simulation-role", version=1)) == v1
    content = "Changed in place even with a new manifest hash\n"
    (manifest.parent / "content.md").write_text(content)
    edit_manifest(manifest, content_hash=digest(content))
    with pytest.raises(PromptConfigurationError, match="Existing prompt version"):
        registry.reload()
    # After process restart, an exact historical pin still detects tampering.
    fresh = PromptRegistry(library)
    with pytest.raises(PromptConfigurationError, match="Historical prompt hash"):
        fresh.resolve(
            ModuleRef(module_id="simulation-role", version=2), expected_hash=v1.module.content_hash
        )


@pytest.mark.parametrize("status", ["DRAFT", "EXPERIMENTAL", "DEPRECATED", "RETIRED"])
def test_nonstable_versions_do_not_become_default(library, role_manifest, status):
    edit_manifest(role_manifest, status=status)
    registry = PromptRegistry(library)
    with pytest.raises(PromptConfigurationError, match="version not found"):
        registry.resolve(ModuleRef(module_id="simulation-role"))
    assert (
        registry.resolve(ModuleRef(module_id="simulation-role", version=1)).module.status == status
    )


def test_line_endings_are_canonical(library, role_manifest):
    path = role_manifest.parent / "content.md"
    original = PromptRegistry(library).resolve(ModuleRef(module_id="simulation-role"))
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert PromptRegistry(library).resolve(ModuleRef(module_id="simulation-role")) == original
    assert json.loads(role_manifest.read_text())["content_hash"] == digest(original.content)
