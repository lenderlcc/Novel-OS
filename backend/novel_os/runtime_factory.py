"""Composition root only: select transports from file-backed Settings."""

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.openai import OpenAIModelProvider
from novel_os.providers.profiles import ModelProfileRegistry


def build_agent_runtime(settings):
    profiles = ModelProfileRegistry()
    profile = profiles.get(settings.agent_model_profile)
    provider = (
        MockModelProvider(settings.agent_mock_scenario)
        if profile.provider == "mock"
        else OpenAIModelProvider(settings.openai_api_key)
    )
    return AgentRuntime(
        provider, profiles=profiles, tasks=TaskDefinitionRegistry(model_profile=profile.profile_id)
    )
