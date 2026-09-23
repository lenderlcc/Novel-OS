"""Composition root only: select transports from file-backed Settings."""

import logging
from pathlib import Path

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.infrastructure.model_capture import CapturingModelProvider
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.openai import LingzhiModelProvider, OpenAIModelProvider
from novel_os.providers.profiles import ModelProfileRegistry

logger = logging.getLogger(__name__)


def build_model_provider(settings, profile):
    if profile.provider == "mock":
        return MockModelProvider(settings.agent_mock_scenario)
    if profile.provider == "lingzhi":
        return LingzhiModelProvider(settings.lingzhi_api_key, base_url=settings.lingzhi_base_url)
    return OpenAIModelProvider(settings.openai_api_key)


def build_agent_runtime(settings, *, model_profile=None):
    profiles = ModelProfileRegistry()
    profile = profiles.get(model_profile or settings.agent_model_profile)
    provider = build_model_provider(settings, profile)
    if settings.agent_capture_outputs:
        try:
            provider = CapturingModelProvider(provider, Path(".runtime/agent-output"))
        except OSError:
            # Capture is diagnostic only. A filesystem problem must not prevent the
            # worker from claiming tasks or force the user to repeat a paid request.
            logger.warning("model_output_capture_initialization_failed")
    return AgentRuntime(
        provider, profiles=profiles, tasks=TaskDefinitionRegistry(model_profile=profile.profile_id)
    )
