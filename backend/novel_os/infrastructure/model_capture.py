"""Opt-in local provider output capture for manual diagnosis, before parsing.

Never stores credentials, HTTP headers or provider error bodies. These private
files are separate from business persistence and are not served by an API.
"""

import json
import logging
import os
from contextlib import suppress
from pathlib import Path

from novel_os.providers.base import ModelProvider

logger = logging.getLogger(__name__)


class CapturingModelProvider(ModelProvider):
    def __init__(self, provider, directory: Path):
        self.provider = provider
        self.provider_id = provider.provider_id
        self.directory = directory
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        directory.chmod(0o700)

    def get_capabilities(self):
        return self.provider.get_capabilities()

    def generate(self, request):
        return self._capture(request, self.provider.generate(request))

    def generate_structured(self, request):
        return self._capture(request, self.provider.generate_structured(request))

    def _capture(self, request, response):
        try:
            record = {
                "task_id": str(request.task_id),
                "task_type": request.task_type,
                "attempt_number": request.attempt_number,
                "provider": self.provider_id,
                "model": request.profile.model,
                "model_profile": request.profile.profile_id,
                "compiled_prompt_hash": request.prompt.compiled_hash,
                "schema_id": request.prompt.output.schema_id,
                "schema_version": request.prompt.output.version,
                "schema_hash": request.prompt.output.schema_hash,
                "model_summary": response.safe_summary(),
                "output": response.content,
            }
            path = self.directory / f"{request.task_id}-{request.attempt_number}.json"
            # Exclusive creation prevents replacement of earlier attempt evidence.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as file:
                json.dump(record, file, ensure_ascii=False, indent=2)
                file.write("\n")
        except Exception:
            # A diagnostic sink failure must never repeat a successful paid request.
            with suppress(Exception):
                logger.warning("model_output_capture_failed")
        return response
