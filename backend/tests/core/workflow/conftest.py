import pytest
from fastapi.testclient import TestClient

from novel_os.main import create_app
from tests.core.workflow.workflow_test_support import Driver


@pytest.fixture
def workflow_client(core_settings):
    settings = core_settings.model_copy(update={"workflow_fake_executor_enabled": True})
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def driver(workflow_client, chapter_api):
    return Driver(workflow_client, chapter_api)


@pytest.fixture
def planning_driver(core_client, chapter_api):
    from tests.core.workflow.test_planning_vertical_slice import PlanningDriver

    return PlanningDriver(core_client, chapter_api)
