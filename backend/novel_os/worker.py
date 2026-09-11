"""Independent polling worker: python -m novel_os.worker [--once] [--config config.toml]."""

import argparse
import logging
import signal
import threading
from pathlib import Path
from uuid import uuid4

from novel_os.agents.runtime import ExecutionResult
from novel_os.core.config import Settings
from novel_os.core.logging import configure_logging
from novel_os.db.session import Database
from novel_os.domain.errors import DomainError
from novel_os.runtime_factory import build_agent_runtime
from novel_os.services.agent_queue import AgentQueue
from novel_os.services.agent_results import AgentResultHandler
from novel_os.services.prompt_lineages import PromptLineageService

logger = logging.getLogger(__name__)


class AgentWorker:
    def __init__(
        self,
        database,
        runtime,
        *,
        worker_id=None,
        lease_seconds=30,
        heartbeat_seconds=5,
        retry_seconds=1,
    ):
        if not 0 < heartbeat_seconds < lease_seconds:
            raise ValueError("Heartbeat interval must be shorter than the lease")
        self.database = database
        self.runtime = runtime
        self.worker_id = worker_id or "worker-" + uuid4().hex
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.retry_seconds = retry_seconds

    def run_once(self):
        with self.database.session() as session:
            lease = AgentQueue(session, lease_seconds=self.lease_seconds).claim(
                self.worker_id, profile_for_task=self.runtime.profile_for_task
            )
        if lease is None:
            return False
        with self.database.session() as session:
            task = AgentQueue(session, lease_seconds=self.lease_seconds).start(lease)
        if task is None:
            return True
        stopped = threading.Event()
        lease_lost = threading.Event()

        def maintain_lease():
            while not stopped.wait(self.heartbeat_seconds):
                try:
                    with self.database.session() as session:
                        renewed = AgentQueue(session, lease_seconds=self.lease_seconds).heartbeat(
                            lease
                        )
                    if not renewed:
                        lease_lost.set()
                        return
                except Exception:
                    # Completion rechecks DB ownership; never trust a failed heartbeat.
                    lease_lost.set()
                    logger.warning(
                        "agent_heartbeat_failed", extra={"request_id": str(lease.run_id)}
                    )
                    return

        heartbeat = threading.Thread(target=maintain_lease, daemon=True)
        heartbeat.start()
        try:
            prepared = self.runtime.prepare(task)
            if isinstance(prepared, ExecutionResult):
                execution = prepared
            else:
                try:
                    with self.database.session() as session:
                        bound = PromptLineageService(session).bind(lease, prepared)
                except DomainError:
                    execution = ExecutionResult(error_code="PROMPT_CONFIGURATION_ERROR")
                else:
                    if not bound:
                        return True
                    execution = self.runtime.execute(task, prepared)
        finally:
            stopped.set()
            heartbeat.join()
        if lease_lost.is_set():
            return True  # Recovery owns this unfinished attempt after the lease expires.
        with self.database.session() as session:
            disposition = AgentResultHandler(session, retry_seconds=self.retry_seconds).complete(
                lease, execution
            )
        logger.info(
            "agent_attempt_finished",
            extra={"request_id": str(lease.run_id), "disposition": disposition},
        )
        return True


def main():
    parser = argparse.ArgumentParser(description="Novel OS agent worker")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--once", action="store_true", help="Claim and handle at most one task")
    args = parser.parse_args()
    settings = Settings.from_file(args.config)
    configure_logging(settings.log_level)
    database = Database(settings)
    stopped = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopped.set())
    worker = AgentWorker(
        database,
        build_agent_runtime(settings),
        lease_seconds=settings.agent_lease_seconds,
        heartbeat_seconds=settings.agent_heartbeat_seconds,
        retry_seconds=settings.agent_retry_seconds,
    )
    try:
        while not stopped.is_set():
            try:
                claimed = worker.run_once()
            except Exception:
                # A crash/DB failure leaves a lease to recover; do not expose raw exceptions.
                logger.error("agent_worker_iteration_failed")
                if args.once:
                    raise SystemExit(1) from None
                claimed = False
            if args.once:
                break
            if not claimed:
                stopped.wait(settings.agent_poll_seconds)
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
