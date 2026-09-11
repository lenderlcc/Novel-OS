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


def start(database, lease):
    with database.session() as session:
        return AgentQueue(session).start(lease)


def complete(database, lease, execution):
    with database.session() as session:
        return AgentResultHandler(session, retry_seconds=0).complete(lease, execution)


def worker(database, scenario="SUCCESS", **options):
    return AgentWorker(
        database, AgentRuntime(MockModelProvider(scenario)), retry_seconds=0, **options
    )
