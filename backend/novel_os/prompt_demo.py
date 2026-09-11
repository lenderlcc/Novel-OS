"""Run an isolated structured extraction smoke test; no database use or business commands."""

import argparse
from pathlib import Path

from novel_os.core.config import Settings
from novel_os.core.logging import configure_logging
from novel_os.runtime_factory import build_agent_runtime


def main():
    parser = argparse.ArgumentParser(description="NOVEL-005 isolated RequirementSpec smoke demo")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--text", default="A short hopeful story set beside the sea.")
    args = parser.parse_args()
    settings = Settings.from_file(args.config)
    configure_logging(settings.log_level)
    execution = build_agent_runtime(settings).execute_smoke(args.text)
    if execution.error_code:
        print(execution.error_code)
        raise SystemExit(1)
    print(execution.result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
