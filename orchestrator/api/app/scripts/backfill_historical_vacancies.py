from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.database.session import SessionLocal
from app.services.historical_application_import import read_csv_rows
from app.services.historical_vacancy_backfill import HistoricalVacancyBackfillService


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill only missing canonical HH vacancies required by historical Applications.")
    parser.add_argument("--applications-csv", type=Path, required=True, help="CSV export of the technical 'Отклики' sheet")
    parser.add_argument("--crm-csv", type=Path, required=True, help="CSV export of the main 'Вакансии' sheet")
    parser.add_argument("--apply", action="store_true", help="Create only preplanned missing Vacancies in the configured database")
    parser.add_argument("--report", type=Path, help="Write the structured report to this JSON file")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        report = HistoricalVacancyBackfillService(session).run(
            read_csv_rows(args.applications_csv),
            read_csv_rows(args.crm_csv),
            apply=args.apply,
        )
    finally:
        session.close()
    output = json.dumps(report.as_dict(), ensure_ascii=False, indent=2)
    print(output)
    if args.report:
        args.report.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
