from sqlalchemy.exc import SQLAlchemyError

from novel_os.domain.errors import DatabaseUnavailableError
from novel_os.repositories.health import HealthRepository


class HealthService:
    def __init__(self, repository: HealthRepository) -> None:
        self.repository = repository

    def check_database(self) -> None:
        try:
            self.repository.ping()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError from exc
