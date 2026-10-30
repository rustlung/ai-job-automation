from __future__ import annotations

import argparse
import json

from app.database.session import SessionLocal
from app.services.stale_pipeline_run_repair import DEFAULT_OLDER_THAN_HOURS, StalePipelineRunRepairService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Close stale accepted/running PipelineRun records after a dry-run review.")
    parser.add_argument(
        "--older-than-hours",
        type=float,
        default=DEFAULT_OLDER_THAN_HOURS,
        metavar="N",
        help="Repair only runs older than N hours (default: 24)",
    )
    parser.add_argument("--apply", action="store_true", help="Write the planned terminal failures in one database transaction")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.older_than_hours <= 0:
        raise SystemExit("--older-than-hours must be greater than zero")
    session = SessionLocal()
    try:
        report = StalePipelineRunRepairService(session).run(
            older_than_hours=args.older_than_hours,
            apply=args.apply,
        )
    finally:
        session.close()
    print(json.dumps(report.as_dict(), ensure_ascii=False, default=lambda value: value.isoformat(), indent=2))


if __name__ == "__main__":
    main()
