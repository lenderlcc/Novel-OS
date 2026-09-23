"""The immutable run snapshot can tighten, never expand, a task's retry budget."""


def attempt_limit(task, run=None, *, configured_limit=None):
    limits = [task.max_attempts]
    previous = run.input_metadata.get("attempt_limit") if run else None
    for limit in (previous, configured_limit):
        if limit is not None:
            if type(limit) is not int or limit < 1:
                raise ValueError("Attempt limit must be a positive integer")
            limits.append(limit)
    return min(limits)
