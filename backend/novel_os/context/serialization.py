"""Canonical, provenance-preserving snapshots and model DATA. No database access."""

from dataclasses import replace

from pydantic import TypeAdapter

from novel_os.domain.context import ContextItem, ContextPackage, ContextRequest
from novel_os.prompts.contracts import canonical, digest

PACKAGE_ADAPTER = TypeAdapter(ContextPackage)
ITEM_ADAPTER = TypeAdapter(ContextItem)
REQUEST_ADAPTER = TypeAdapter(ContextRequest)


def item_data(item):
    data = ITEM_ADAPTER.dump_python(item, mode="json")
    data["structured_payload"] = data.pop("payload_json")
    data["structured_payload"] = item.structured_payload
    return data


class ContextSerializer:
    @staticmethod
    def payload(request, profile, items, package_hash="0" * 64):
        return {
            "context_package_hash": package_hash,
            "profile": {
                "id": profile.profile_id,
                "version": profile.version,
                "hash": profile.profile_hash,
            },
            "task_id": str(request.task_id),
            "chapter_id": str(request.chapter_id),
            "future_knowledge_policy": profile.future_knowledge_policy.value,
            "items": [item_data(item) for item in items],
        }

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
