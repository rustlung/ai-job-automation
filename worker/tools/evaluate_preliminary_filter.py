import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = WORKER_ROOT / "api"
sys.path.insert(0, str(API_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.schemas.hh import HHSearchVacancy  # noqa: E402
from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance  # noqa: E402
from app.schemas.preliminary_filter import PreliminaryDecision  # noqa: E402
from app.services.preliminary_filter import PreliminaryVacancyFilterService  # noqa: E402

EXPECTED_LABELS = {"P1", "P2", "P3", "ALT", "REJECT"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate preliminary local AI vacancy filter on a local JSON dataset.")
    parser.add_argument("dataset", type=Path, help="Path to local evaluation JSON. Do not commit this file.")
    args = parser.parse_args()

    try:
        return asyncio.run(_run(args.dataset))
    except Exception as exc:
        print(f"technical_failure: {exc}", file=sys.stderr)
        return 1


async def _run(dataset_path: Path) -> int:
    started_at = time.perf_counter()
    items = _load_items(dataset_path)
    service = PreliminaryVacancyFilterService.from_settings(get_settings())
    result = await service.filter_vacancies([item["vacancy"] for item in items])
    expected_by_id = {item["vacancy"].external_id: item["expected"] for item in items}

    exact_matches = 0
    critical_false_negatives = 0
    main_total = 0
    main_kept = 0
    alt_total = 0
    alt_kept = 0
    reject_total = 0
    reject_correct = 0

    for item in result.items:
        expected = expected_by_id[item.vacancy.external_id]
        decision = item.assessment.decision
        if _is_exact_match(expected["decision"], decision):
            exact_matches += 1
        if expected["label"] in {"P1", "P2"}:
            main_total += 1
            if decision == PreliminaryDecision.KEEP_MAIN:
                main_kept += 1
            if decision == PreliminaryDecision.REJECT:
                critical_false_negatives += 1
        if expected["label"] == "ALT":
            alt_total += 1
            if decision == PreliminaryDecision.KEEP_ALT:
                alt_kept += 1
            if decision == PreliminaryDecision.REJECT:
                critical_false_negatives += 1
        if expected["label"] == "REJECT":
            reject_total += 1
            if decision == PreliminaryDecision.REJECT:
                reject_correct += 1

    duration_ms = round((time.perf_counter() - started_at) * 1000)
    report = {
        "total": len(items),
        "exact_decision_matches": exact_matches,
        "critical_false_negatives": critical_false_negatives,
        "main_recall": _ratio(main_kept, main_total),
        "alt_recall": _ratio(alt_kept, alt_total),
        "reject_precision": _ratio(reject_correct, reject_total),
        "uncertain_count": result.uncertain_count,
        "fallback_count": result.fallback_count,
        "average_ms_per_vacancy": _ratio(duration_ms, len(items)),
        "duration_ms": duration_ms,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _load_items(dataset_path: Path) -> list[dict[str, Any]]:
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("dataset must contain items list")

    items: list[dict[str, Any]] = []
    for raw in raw_items:
        vacancy = HHSearchVacancy.model_validate(raw["vacancy"])
        expected = raw["expected"]
        if expected.get("label") not in EXPECTED_LABELS:
            raise ValueError("unexpected expected label")
        provenance = HHSearchVacancyProvenance(
            profile_ids=raw.get("profile_ids", ["evaluation"]),
            query_variant_ids=raw.get("query_variant_ids", []),
            tracks=raw.get("tracks", ["main"]),
            first_profile_id=raw.get("profile_ids", ["evaluation"])[0],
            first_query_variant_id=(raw.get("query_variant_ids") or [None])[0],
            occurrence_count=raw.get("occurrence_count", 1),
        )
        items.append(
            {
                "vacancy": HHSearchCollectedVacancy(**vacancy.model_dump(), provenance=provenance),
                "expected": expected,
            }
        )
    return items


def _is_exact_match(expected_decision: str, decision: PreliminaryDecision) -> bool:
    return expected_decision == decision.value


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


if __name__ == "__main__":
    raise SystemExit(main())
