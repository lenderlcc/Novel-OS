class DatabaseUnavailableError(Exception):
    """The database readiness probe could not complete."""


class DomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
