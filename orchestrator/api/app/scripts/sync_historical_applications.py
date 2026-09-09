from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.schemas.application import ApplicationCrmSyncRead, ApplicationCrmSyncStatus
from app.services.application_crm_sync import ApplicationCrmSyncService
from app.services.web_gateway import ApplicationCrmSyncWebhookClient


async def run_sync(application_ids: list[int], *, apply: bool, service: ApplicationCrmSyncService | None = None) -> dict[str, object]:
    session = None
    try:
        if service is None:
            session = SessionLocal()
            service = ApplicationCrmSyncService(session, ApplicationCrmSyncWebhookClient(get_settings()))
        report: dict[str, object] = {"requested": len(application_ids), "would_sync": 0, "already_synced": 0, "synced": 0, "failed": 0, "details": []}
        for application_id in application_ids:
            current = service.get_state(application_id)
            if current.status.value == "synced":
                report["already_synced"] += 1
                continue
            if not apply:
                report["would_sync"] += 1
                continue
            result = await service.sync(application_id, retry=True)
            if result.status.value == "synced":
                report["synced"] += 1
            else:
                report["failed"] += 1
                report["details"].append({"application_id": application_id, "error_code": result.error_code})
        return report
    finally:
        if session is not None:
            session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize imported historical Applications to CRM after DB verification.")
    parser.add_argument("--import-report", type=Path, required=True, help="JSON report produced by import_historical_applications --apply")
    parser.add_argument("--apply", action="store_true", help="Call the existing Application CRM sync adapter")
    args = parser.parse_args()
    source = json.loads(args.import_report.read_text(encoding="utf-8"))
    application_ids = [value for value in source.get("created_application_ids", []) if isinstance(value, int)]
    print(json.dumps(asyncio.run(run_sync(application_ids, apply=args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
