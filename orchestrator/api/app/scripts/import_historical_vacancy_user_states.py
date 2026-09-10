from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.database.session import SessionLocal
from app.services.historical_application_import import read_csv_rows
from app.services.historical_vacancy_user_state_import import HistoricalVacancyUserStateImportService


def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical VacancyUserState data from a local 'Вакансии' CSV export.")
    parser.add_argument("--crm-csv", type=Path, required=True, help="CSV export of the main 'Вакансии' sheet")
    parser.add_argument("--report", type=Path, required=True, help="Write the structured report to this JSON file")
    parser.add_argument("--apply", action="store_true", help="Write only explicitly planned user-state records to the configured database")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        report = HistoricalVacancyUserStateImportService(session).run(read_csv_rows(args.crm_csv), apply=args.apply)
    finally:
        session.close()
    output = json.dumps(report.as_dict(), ensure_ascii=False, indent=2)
    print(output)
    args.report.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
