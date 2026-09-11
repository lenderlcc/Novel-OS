from dataclasses import asdict

from sqlalchemy import select, text

from novel_os.domain.prompts import PromptLineage
from novel_os.models.prompts import PromptLineageModel
from novel_os.prompts.contracts import canonical
from novel_os.repositories.core import to_domain


class PromptLineageRepository:
    def __init__(self, session):
        self.session = session

    def add(self, lineage: PromptLineage):
        self.session.add(PromptLineageModel(**asdict(lineage)))
        self.session.flush()
        return lineage

    def for_run(self, run_id):
        row = self.session.scalar(
            select(PromptLineageModel).where(PromptLineageModel.agent_run_id == run_id)
        )
        return to_domain(row, PromptLineage) if row else None

    def matches_historical_pins(self, pins):
        # Serialize first publication of the same version across projects/workers.
        # Only the application transaction owns these locks; no commit in this repository.
        for pin in sorted(pins, key=lambda item: (item["module_id"], item["version"])):
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(current_schema() || :key, 0))"),
                {"key": canonical([pin["module_id"], pin["version"]])},
            )
        return not self.session.scalar(
            text("""
            SELECT 1 FROM prompt_lineages,
                LATERAL jsonb_array_elements(jsonb_build_array(
                    system_policy, agent_role, task_template, quality_profile) || skills) old_pin,
                jsonb_array_elements(CAST(:pins AS jsonb)) new_pin
            WHERE old_pin->>'module_id' = new_pin->>'module_id'
              AND old_pin->>'version' = new_pin->>'version'
              AND (old_pin->>'content_hash' IS DISTINCT FROM new_pin->>'content_hash'
                   OR old_pin->>'execution_hash' IS DISTINCT FROM new_pin->>'execution_hash')
            LIMIT 1
        """),
            {"pins": canonical(pins)},
        )
