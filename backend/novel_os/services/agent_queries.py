from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.workflows import WorkflowRepository


class AgentQueries:
    def __init__(self, session):
        self.repo = AgentTaskRepository(session)
        self.workflows = WorkflowRepository(session)

    def get(self, task_id):
        return self.repo.get(task_id)

    def runs(self, task_id, limit, offset):
        self.repo.get(task_id)
        return self.repo.list_runs(task_id, limit, offset)

    def tasks(self, workflow_id, limit, offset):
        self.workflows.get(workflow_id)
        return self.repo.list_tasks(workflow_id, limit, offset)

    def character_reports(self, project_id, character_id, limit, offset):
        from novel_os.services.character_profiles import CharacterProfileService

        CharacterProfileService(self.repo.session).state(project_id, character_id)
        return self.repo.list_character_reports(project_id, character_id, limit, offset)
