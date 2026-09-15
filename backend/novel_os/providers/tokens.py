"""Provider-neutral local budgeting. A conservative UTF-8 byte bound, not billing usage."""

from typing import Protocol


class TokenEstimator(Protocol):
    def estimate(self, text: str) -> int: ...


class Utf8TokenEstimator:
    def estimate(self, text: str) -> int:
        return len(text.encode("utf-8"))


def prompt_overhead(request, estimator=None):
    """Conservative envelope cost, including role frames and native output schema."""
    estimator = estimator or Utf8TokenEstimator()
    cost = sum(estimator.estimate(message.content) + 64 for message in request.prompt.messages)
    if request.profile.structured_output:
        cost += estimator.estimate(request.prompt.output.schema_json)
    return cost
