from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from novel_os.repositories.health import HealthRepository
from novel_os.services.health import HealthService


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.database.session() as session:
        yield session


def get_health_service(session: Annotated[Session, Depends(get_session)]) -> HealthService:
    return HealthService(HealthRepository(session))
