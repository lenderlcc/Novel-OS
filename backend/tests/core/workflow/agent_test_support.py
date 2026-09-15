from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.services.agent_queue import AgentQueue
from novel_os.services.agent_results import AgentResultHandler
from novel_os.worker import AgentWorker


def pending_task(driver):
    response = driver.client.get(driver.url + "/agent-tasks")
    assert response.status_code == 200, response.text
    return next(task for task in response.json() if task["status"] == "PENDING")


def task_record(database, task_id):
    with database.session() as session:
        return AgentTaskRepository(session).get(task_id)


def runs(database, task_id):
    with database.session() as session:
        return AgentTaskRepository(session).list_runs(task_id)


def claim(database, worker_id="test-worker"):
    with database.session() as session:
        return AgentQueue(session).claim(worker_id)


def start(database, lease, *, bind_context=True):
    with database.session() as session:
        task = AgentQueue(session).start(lease)
    if task is not None and bind_context:
        from novel_os.services.context import ContextService
        from tests.context_support import BOUND_CONTEXT

        with database.session() as session:
            built = ContextService(session).build_for_run(lease)
        if built.package is not None:
            BOUND_CONTEXT[task.task_id] = built.package
    return task


def complete(database, lease, execution):
    with database.session() as session:
        return AgentResultHandler(session, retry_seconds=0).complete(lease, execution)


def worker(database, scenario="SUCCESS", **options):
    return AgentWorker(
        database, AgentRuntime(MockModelProvider(scenario)), retry_seconds=0, **options
    )
