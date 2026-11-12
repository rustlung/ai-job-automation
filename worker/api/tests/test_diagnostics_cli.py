from app.diagnostics.cli import _report


def test_run_report_detects_mass_full_fetch_failure_and_conservation() -> None:
    report = _report(
        {
            "run_id": "n8n-test",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:01:00+00:00",
            "stats_snapshot": {
                "collection_stats": {"unique_vacancy_count": 300, "pages_succeeded": 15, "pages_failed": 0},
                "preliminary_stats": {"processed_count": 300},
                "enrichment_stats": {"selected_count": 247, "enriched_count": 3, "failed_fetch_count": 244},
            },
        },
        {"total": 300},
        None,
    )

    assert report["checks"]["preliminary_coverage"]["status"] == "pass"
    assert report["checks"]["enrichment_coverage"]["status"] == "pass"
    assert report["findings"][0]["code"] == "mass_full_fetch_failure"


def test_run_report_is_partial_when_orchestrator_is_unavailable() -> None:
    report = _report(None, None, "unavailable")

    assert report == {"availability": "unavailable", "run": None, "backlog": None, "findings": []}


def test_production_shaped_report_finds_mass_full_fetch_failure() -> None:
    report = _report(
        {
            "run_id": "n8n-fd412062-d8ef-4370-b313-3e8d21dbec9d",
            "status": "completed",
            "started_at": "2026-11-11T10:00:00+00:00",
            "completed_at": "2026-11-11T10:26:00+00:00",
            "stats_snapshot": {
                "collection_stats": {"unique_vacancy_count": 300},
                "preliminary_stats": {"processed_count": 300},
                "enrichment_stats": {
                    "selected_count": 247,
                    "enriched_count": 3,
                    "analysis_count": 3,
                    "failure_groups": {"full_fetch_failed": {"count": 244, "summary": "Safe failure.", "samples": []}},
                },
            },
        },
        {"total": 300, "state_counts": {"preliminary_rejected": 53, "enriched": 3, "processing_failed": 244}},
        None,
    )

    codes = {finding["code"] for finding in report["findings"]}
    assert "mass_full_fetch_failure" in codes
    assert report["checks"]["preliminary_coverage"]["status"] == "pass"
    assert report["checks"]["enrichment_coverage"]["status"] == "pass"


def test_resume_report_uses_durable_backlog_total_for_discovered_coverage() -> None:
    report = _report(
        {
            "run_id": "n8n-resumed",
            "status": "completed",
            "stats_snapshot": {"collection_stats": {"unique_vacancy_count": None}, "preliminary_stats": {"processed_count": 18}},
        },
        {"total": 18, "state_counts": {"enriched": 14, "processing_failed": 1, "preliminary_rejected": 3}},
        None,
    )

    check = report["checks"]["preliminary_coverage"]
    assert check["status"] == "pass"
    assert check["expected"] == 18
    assert check["actual"] == 18


def test_report_leaves_discovered_unavailable_without_explicit_or_durable_source() -> None:
    report = _report(
        {"run_id": "n8n-legacy", "status": "completed", "stats_snapshot": {"collection_stats": {"unique_vacancy_count": None}}},
        {"total": 0, "state_counts": {}},
        None,
    )

    assert report["checks"]["preliminary_coverage"]["status"] == "unavailable"
