"""Canonical, provenance-preserving snapshots and model DATA. No database access."""

from dataclasses import replace

from pydantic import TypeAdapter

from novel_os.domain.context import ContextItem, ContextPackage, ContextRequest
from novel_os.domain.planning import exploration_required_refs
from novel_os.prompts.contracts import canonical, digest

PACKAGE_ADAPTER = TypeAdapter(ContextPackage)
ITEM_ADAPTER = TypeAdapter(ContextItem)
REQUEST_ADAPTER = TypeAdapter(ContextRequest)


def item_data(item, *, deduplicate_plan=False):
    data = ITEM_ADAPTER.dump_python(item, mode="json")
    data["structured_payload"] = data.pop("payload_json")
    data["structured_payload"] = item.structured_payload
    if deduplicate_plan and item.source_type.value == "CHAPTER_PLAN":
        payload = data["structured_payload"]
        planning = payload.get("planning")
        if isinstance(planning, dict):
            for name, value in tuple(payload.items()):
                target = name
                if target not in planning and name == "scene_plans":
                    target = "scenes"
                if name == "planning" or target not in planning:
                    continue
                if canonical(value) == canonical(planning[target]):
                    del payload[name]
                    continue
                if (
                    name in {"character_progression", "plot_progression"}
                    and isinstance(value, dict)
                    and set(value) == {"items"}
                ):
                    value = value["items"]
                elif (
                    name == "ending_state"
                    and isinstance(value, dict)
                    and set(value) == {"description"}
                ):
                    value = value["description"]
                if canonical(value) == canonical(planning[target]):
                    del payload[name]
    return data


class ContextSerializer:
    @staticmethod
    def payload(request, profile, items, package_hash="0" * 64):
        # Version the model projection; historical snapshots and prompt hashes retain
        # their original shape. Token budgeting and final prompts share this path.
        deduplicate_plan = (
            request.task_type == "WRITE_CHAPTER"
            and profile.profile_id == "CP-005"
            and profile.version >= 8
        ) or (
            request.task_type in {"REVIEW_CHAPTER_COMPLIANCE", "REVIEW_CHAPTER_NARRATIVE"}
            and profile.profile_id == "CP-006"
            and profile.version >= 6
        )
        data = {
            "context_package_hash": package_hash,
            "profile": {
                "id": profile.profile_id,
                "version": profile.version,
                "hash": profile.profile_hash,
            },
            "task_id": str(request.task_id),
            "chapter_id": str(request.chapter_id),
            "future_knowledge_policy": profile.future_knowledge_policy.value,
            "items": [item_data(item, deduplicate_plan=deduplicate_plan) for item in items],
        }
        if (
            request.task_type == "EXPLORE_CHAPTER_CONCEPTS"
            and profile.profile_id == "CP-004E"
            and profile.version >= 3
        ):
            data["required_source_refs"] = [
                {
                    "source_type": ref.source_type,
                    "logical_id": str(ref.logical_id),
                    "version": ref.version,
                }
                for ref in sorted(
                    exploration_required_refs(items),
                    key=lambda ref: (ref.source_type, str(ref.logical_id), ref.version),
                )
            ]
            if profile.version >= 4:
                data["brief_record_id"] = next(
                    (str(item.source_id) for item in items if item.source_type == "CREATIVE_BRIEF"),
                    None,
                )
        return data

    @classmethod
    def serialize(cls, package):
        from novel_os.context.profiles import ContextProfile
        from novel_os.domain.context import ContextStatus

        if package.build_status != ContextStatus.READY:
            raise ValueError("Only READY context can enter a prompt")
        return cls.payload(
            package.request,
            ContextProfile.model_validate_json(package.profile_json),
            package.items,
            package.package_hash,
        )

    @staticmethod
    def snapshot(package):
        return PACKAGE_ADAPTER.dump_python(package, mode="json")

    @staticmethod
    def restore(snapshot):
        return PACKAGE_ADAPTER.validate_python(snapshot)

    @staticmethod
    def hash(package):
        data = PACKAGE_ADAPTER.dump_python(package, mode="json")
        for key in ("context_package_id", "created_at", "package_hash"):
            data.pop(key)
        data["request"].pop("request_id")
        return digest(canonical(data))

    @classmethod
    def seal(cls, package):
        return replace(package, package_hash=cls.hash(package))
