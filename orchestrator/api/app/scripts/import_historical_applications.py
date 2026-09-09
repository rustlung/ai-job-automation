from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.database.session import SessionLocal
from app.services.historical_application_import import HistoricalApplicationImportService, read_csv_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical HH applications from local Google Sheets CSV exports.")
    parser.add_argument("--applications-csv", type=Path, required=True, help="CSV export of the technical 'Отклики' sheet")
    parser.add_argument("--crm-csv", type=Path, required=True, help="CSV export of the main 'Вакансии' sheet")
    parser.add_argument("--apply", action="store_true", help="Write only explicitly planned Applications to the configured database")
    parser.add_argument("--report", type=Path, help="Write the structured report to this JSON file")
    args = parser.parse_args()

    historical_rows = read_csv_rows(args.applications_csv)
    crm_rows = read_csv_rows(args.crm_csv)
    session = SessionLocal()
    try:
        report = HistoricalApplicationImportService(session).run(historical_rows, crm_rows, apply=args.apply)
    finally:
        session.close()
    output = report.as_dict()
    serialized = json.dumps(output, ensure_ascii=False, indent=2)
    print(serialized)
    if args.report:
        args.report.write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
