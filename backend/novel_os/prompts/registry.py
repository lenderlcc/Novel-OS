import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from novel_os.prompts.contracts import (
    ModuleRef,
    ModuleStatus,
    PromptConfigurationError,
    PromptModule,
    digest,
    normalize,
)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


@dataclass(frozen=True)
class ResolvedModule:
    module: PromptModule
    content: str


class PromptRegistry:
    def __init__(self, root: Path | None = None):
        self.root = (root or Path(__file__).parent / "library").resolve()
        self._modules: dict[tuple[str, int], ResolvedModule] = {}
        try:
            manifests = sorted(self.root.rglob("manifest.json"))
            if not manifests:
                raise ValueError
            for path in manifests:
                metadata = PromptModule.model_validate(
                    json.loads(path.read_text(), object_pairs_hook=unique_object)
                )
                content_path = (path.parent / metadata.content_path).resolve()
                if not content_path.is_relative_to(self.root) or content_path.suffix != ".md":
                    raise ValueError
                content = normalize(content_path.read_text(encoding="utf-8"))
                if not content.strip() or digest(content) != metadata.content_hash:
                    raise ValueError
                key = (metadata.module_id, metadata.version)
                if key in self._modules:
                    raise ValueError
                self._modules[key] = ResolvedModule(metadata, content)
            self._validate_dependencies()
        except (OSError, ValueError, ValidationError, RecursionError):
            raise PromptConfigurationError(
                "Invalid prompt library metadata, content or dependency"
            ) from None

    def _validate_dependencies(self):
        visited, visiting = set(), set()

        def visit(key):
            if key in visiting or key not in self._modules:
                raise ValueError
            if key in visited:
                return
            visiting.add(key)
            for dependency in self._modules[key].module.dependencies:
                visit((dependency.module_id, dependency.version))
            visiting.remove(key)
            visited.add(key)

        for key in self._modules:
            visit(key)

    def reload(self):
        """Publish new stable selections atomically, retaining immutable resolved objects.

        Status may advance without changing the version. Content and execution metadata
        must get a new version. Historical pins also support verification after restart.
        """
        replacement = PromptRegistry(self.root)
        for key, previous in self._modules.items():
            current = replacement._modules.get(key)
            if current is None or previous.module.execution_hash != current.module.execution_hash:
                raise PromptConfigurationError("Existing prompt version changed or disappeared")
        self._modules = replacement._modules

    def resolve(
        self,
        ref: ModuleRef,
        *,
        expected_hash: str | None = None,
        expected_execution_hash: str | None = None,
    ) -> ResolvedModule:
        if ref.version is None:
            candidates = [
                item
                for (name, _), item in self._modules.items()
                if name == ref.module_id and item.module.status == ModuleStatus.STABLE
            ]
            result = max(candidates, key=lambda item: item.module.version, default=None)
        else:
            result = self._modules.get((ref.module_id, ref.version))
        if result is None:
            raise PromptConfigurationError("Prompt version not found")
        if expected_hash is not None and result.module.content_hash != expected_hash:
            raise PromptConfigurationError("Historical prompt hash conflict")
        if (
            expected_execution_hash is not None
            and result.module.execution_hash != expected_execution_hash
        ):
            raise PromptConfigurationError("Historical prompt execution hash conflict")
        return result
