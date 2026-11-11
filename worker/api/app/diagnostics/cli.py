from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.services.hh_auth_state import HHAuthStateStore
from app.services.hh_transport_diagnostic import HHTransportDiagnosticService


def _headers(settings: Settings) -> dict[str, str]:
    return {"X-Orchestrator-Internal-Token": settings.orchestrator_internal_api_token}


async def _get(settings: Settings, path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        async with httpx.AsyncClient(timeout=settings.orchestrator_request_timeout_seconds) as client:
            response = await client.get(f"{settings.orchestrator_api_url.rstrip('/')}{path}", headers=_headers(settings))
        if response.status_code == 404:
            return None, "not_found"
        response.raise_for_status()
        return response.json(), None
    except httpx.HTTPError:
        return None, "unavailable"


def _duration(started_at: str | None, completed_at: str | None) -> str:
    if not started_at or not completed_at:
        return "unavailable"
    try:
        seconds = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds())
    except ValueError:
        return "unavailable"
    return f"{seconds // 60}m {seconds % 60:02d}s"


def _stats(report: dict[str, Any]) -> dict[str, Any]:
    return report.get("stats_snapshot") or {}


def _value(data: dict[str, Any], key: str, fallback: Any = None) -> Any:
    return data[key] if key in data and data[key] is not None else fallback


def _check(expected: int | None, actual: int | None, summary: str) -> dict[str, Any]:
    if expected is None or actual is None:
        return {"status": "unavailable", "expected": expected, "actual": actual, "summary": summary}
    return {"status": "pass" if expected == actual else "fail", "expected": expected, "actual": actual, "summary": summary}


def _report(run: dict[str, Any] | None, backlog: dict[str, Any] | None, worker_error: str | None) -> dict[str, Any]:
    if run is None:
        return {"availability": worker_error or "not_found", "run": None, "backlog": backlog, "findings": []}
    stats = _stats(run)
    collection = stats.get("collection_stats") or {}
    preliminary = stats.get("preliminary_stats") or {}
    enrichment = stats.get("enrichment_stats") or {}
    discovered = _value(stats, "discovered_count", _value(collection, "unique_vacancy_count"))
    processed = _value(preliminary, "processed_count", _value(stats, "preliminary_processed_count"))
    selected = _value(enrichment, "selected_count", _value(stats, "enrichment_selected_count"))
    enriched = _value(enrichment, "enriched_count", _value(stats, "enriched_count"))
    failure_groups = enrichment.get("failure_groups") or {}
    full_fetch_failed = _value(enrichment, "failed_fetch_count", _value(stats, "failed_fetch_count", failure_groups.get("full_fetch_failed", {}).get("count", 0)))
    terminal_preliminary = preliminary.get("processed_count")
    enrichment_failed = sum(group.get("count", 0) for group in failure_groups.values())
    if not failure_groups:
        enrichment_failed = full_fetch_failed
    findings: list[dict[str, str]] = []
    if selected and full_fetch_failed / selected >= 0.8:
        findings.append({"level": "ERROR", "code": "mass_full_fetch_failure", "message": "Mass full vacancy fetch failure."})
    if selected and enriched is not None and enriched / selected < 0.1:
        findings.append({"level": "WARN", "code": "low_enrichment_success", "message": "Enrichment success rate is critically low."})
    if selected and enrichment.get("analysis_count") == 0:
        findings.append({"level": "WARN", "code": "analysis_missing", "message": "No final analyses were persisted for selected vacancies."})
    if collection.get("unique_vacancy_count") and collection.get("pages_succeeded") == 0:
        findings.append({"level": "ERROR", "code": "collection_failed", "message": "HH collection did not succeed."})
    state_counts = (backlog or {}).get("state_counts") or {}
    active_backlog = sum(state_counts.get(name, 0) for name in ("preliminary_pending", "preliminary_running", "enrichment_pending", "enrichment_running"))
    if run.get("status") in {"completed", "completed_with_errors", "failed"} and active_backlog:
        findings.append({"level": "WARN", "code": "unfinished_terminal_backlog", "message": "Terminal run still has pending or running durable work."})
    persisted = _value(enrichment, "persisted_count", _value(stats, "persisted_count"))
    if enriched is not None and persisted is not None and enriched > persisted:
        findings.append({"level": "ERROR", "code": "persistence_gap", "message": "More enriched items than persisted final results."})
    return {
        "availability": "available",
        "run": run,
        "collection": collection,
        "preliminary": preliminary,
        "enrichment": enrichment,
        "backlog": backlog,
        "checks": {
            "preliminary_coverage": _check(discovered, terminal_preliminary, "discovered == terminal preliminary outcomes"),
            "enrichment_coverage": _check(selected, (enriched or 0) + enrichment_failed if selected is not None else None, "selected == enriched + terminal failures"),
            "backlog_conservation": _check((backlog or {}).get("total"), sum(state_counts.values()) if backlog else None, "sum(states) == total"),
            "persistence_consistency": _check(enriched, persisted, "enriched == persisted final results"),
        },
        "findings": findings,
    }


def _human(report: dict[str, Any]) -> str:
    if report["availability"] != "available":
        return f"RUN\n  availability: {report['availability']}"
    run = report["run"]
    collection = report["collection"]
    preliminary = report["preliminary"]
    enrichment = report["enrichment"]
    def field(name: str, value: Any) -> str:
        return f"  {name}: {value if value is not None else 'unavailable'}"

    lines = ["RUN", field("id", run.get("run_id")), field("status", run.get("status")), field("trigger", run.get("trigger_source")), field("profiles", run.get("profile_ids")), field("duration", _duration(run.get("started_at"), run.get("completed_at"))), field("error_code", run.get("error_code")), field("error_summary", run.get("error_summary"))]
    lines += ["COLLECTION", field("availability", collection.get("availability", "available")), field("raw", collection.get("raw_vacancy_count")), field("unique/discovered", collection.get("unique_vacancy_count")), field("profiles", collection.get("profile_count")), field("query_variants", collection.get("query_variant_count")), field("page_size", collection.get("page_size")), field("pages", f"{_value(collection, 'pages_attempted', 'unavailable')} attempted / {_value(collection, 'pages_succeeded', 'unavailable')} succeeded / {_value(collection, 'pages_failed', 'unavailable')} failed"), field("stop_reasons", collection.get("stop_reason_counts")), field("transport", collection.get("transport")), field("duration", collection.get("duration_ms"))]
    lines += ["DISCOVERY", field("input", _value(_stats(run), "discovery_input_count")), field("created", _value(_stats(run), "discovery_created_count")), field("updated", _value(_stats(run), "discovery_updated_count")), field("persisted", _value(_stats(run), "discovery_persisted_count"))]
    for key in ("rejected_by_policy", "rejected_by_ai", "keep_main", "keep_alt", "uncertain", "preliminary_fallback", "preliminary_failed"):
        preliminary.setdefault(key, (preliminary.get("outcome_counts") or {}).get(key))
    lines += ["PRELIMINARY", field("processed", preliminary.get("processed_count")), *[field(key, preliminary.get(key)) for key in ("rejected_by_policy", "rejected_by_ai", "keep_main", "keep_alt", "uncertain", "preliminary_fallback", "preliminary_failed")], field("selected_for_enrichment", preliminary.get("enrichment_selected_count")), field("duration", preliminary.get("duration_ms"))]
    selected = enrichment.get("selected_count")
    enriched = enrichment.get("enriched_count")
    rate = "unavailable" if not selected else f"{(enriched or 0) / selected:.1%}"
    transport = report.get("full_fetch_transport") or {}
    lines += ["ENRICHMENT", field("selected", selected), field("enriched", enriched), field("failed", sum(group.get("count", 0) for group in (enrichment.get("failure_groups") or {}).values())), field("success_rate", rate), field("full_fetch_transport", f"{transport.get('value', 'unknown')} ({transport.get('source', 'unknown')})"), field("duration", enrichment.get("duration_ms"))]
    failures = report.get("failure_samples") or enrichment.get("failure_groups") or {}
    lines += ["FAILURES"]
    if not failures:
        lines.append("  unavailable")
    for code, group in failures.items():
        lines += [field(code, group.get("count")), field("summary", group.get("summary"))]
        for sample in group.get("samples", []):
            lines.append(f"    - {sample.get('company') or 'unavailable'} / {sample.get('title') or 'unavailable'} / {sample.get('external_id') or 'unavailable'} / {sample.get('url') or 'unavailable'}")
    states = (report.get("backlog") or {}).get("state_counts") or {}
    lines += ["BACKLOG", *[field(name, states.get(name)) for name in ("preliminary_pending", "preliminary_running", "preliminary_rejected", "enrichment_pending", "enrichment_running", "enriched", "processing_failed")]]
    lines += ["CHECKS"]
    for name, check in report["checks"].items():
        lines.append(f"  [{check['status'].upper()}] {name}: {check['actual']}/{check['expected']}")
    if report["findings"]:
        lines += ["FINDINGS"] + [f"  [{item['level']}] {item['message']}" for item in report["findings"]]
    return "\n".join(lines)


async def _run(args: argparse.Namespace, settings: Settings) -> int:
    diagnostic, run_error = await _get(settings, f"/internal/diagnostics/runs/{args.run_id}")
    if diagnostic is not None:
        run = diagnostic["run"]
        stats = run.get("stats_snapshot") or {}
        stats["preliminary_stats"] = {**(stats.get("preliminary_stats") or {}), **diagnostic.get("preliminary", {})}
        stats["enrichment_stats"] = {
            **(stats.get("enrichment_stats") or {}),
            **diagnostic.get("enrichment", {}),
            "selected_count": diagnostic.get("preliminary", {}).get("enrichment_selected_count"),
            "failure_groups": diagnostic.get("failures", {}),
        }
        stats["collection_stats"] = {
            **(stats.get("collection_stats") or {}),
            **diagnostic.get("pagination", {}),
        }
        run["stats_snapshot"] = stats
        report = _report(run, diagnostic.get("backlog"), None)
        report["failure_samples"] = diagnostic.get("failures", {})
        report["full_fetch_transport"] = diagnostic.get("full_fetch_transport")
    else:
        report = _report(None, None, run_error)
    print(json.dumps(report, ensure_ascii=False, default=str, indent=2) if args.json else _human(report))
    return 0 if report["availability"] == "available" else 2


async def _recent(args: argparse.Namespace, settings: Settings) -> int:
    payload, error = await _get(settings, f"/internal/diagnostics/runs?limit={args.limit}")
    if payload is None:
        print(json.dumps({"availability": error}, ensure_ascii=False) if args.json else f"RECENT\n  availability: {error}")
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))
    else:
        lines = ["RECENT"]
        for item in payload["runs"]:
            lines.append(
                f"  {item.get('started_at')}  {item.get('status')}  {item.get('run_id')}  "
                f"profiles={item.get('profile_ids')}  duration={_duration(item.get('started_at'), item.get('completed_at'))}  "
                f"error={item.get('error_code') or '-'}"
            )
        print("\n".join(lines))
    return 0


async def _health(args: argparse.Namespace, settings: Settings) -> int:
    report: dict[str, dict[str, str]] = {"worker_runtime": {"status": "PASS", "summary": "CLI runs inside the Worker image."}}
    auth_ok = bool(settings.orchestrator_internal_api_token)
    state = "PASS"
    try:
        HHAuthStateStore(settings.hh_auth_storage_state_path).validate_available()
    except Exception:
        state = "FAIL"
    report["hh_storage_state"] = {"status": state, "summary": "storage state is readable" if state == "PASS" else "storage state is unavailable or invalid"}
    payload, orchestrator_error = await _get(settings, "/internal/diagnostics/runs/diagnostics-health-probe")
    report["orchestrator_diagnostics"] = {
        "status": "PASS" if orchestrator_error == "not_found" else "FAIL",
        "summary": "internal diagnostic endpoint is reachable" if orchestrator_error == "not_found" else (orchestrator_error or "unexpected response"),
    }
    report["worker_to_orchestrator_auth"] = {
        "status": "PASS" if auth_ok and orchestrator_error == "not_found" else "FAIL",
        "summary": "internal token configured and accepted" if auth_ok and orchestrator_error == "not_found" else "token missing or request rejected",
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            ollama = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        models = {item.get("name") for item in ollama.json().get("models", [])} if ollama.is_success else set()
        report["ollama"] = {"status": "PASS" if ollama.is_success else "FAIL", "summary": "reachable" if ollama.is_success else f"HTTP {ollama.status_code}"}
        report["ollama_model"] = {"status": "PASS" if settings.ollama_model in models else "WARN", "summary": "configured model available" if settings.ollama_model in models else "configured model not listed"}
    except (httpx.HTTPError, ValueError):
        report["ollama"] = {"status": "FAIL", "summary": "unavailable"}
        report["ollama_model"] = {"status": "unavailable", "summary": "Ollama unavailable"}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("HEALTH\n" + "\n".join(f"  [{value['status']}] {key}: {value['summary']}" for key, value in report.items()))
    return 0 if all(value["status"] in {"PASS", "WARN"} for value in report.values()) else 2


async def _config(args: argparse.Namespace, settings: Settings) -> int:
    report = {"hh_collection_max_raw_vacancies": settings.hh_collection_max_raw_vacancies, "preliminary_outer_chunk": settings.preliminary_filter_max_items, "preliminary_llm_batch": settings.preliminary_filter_batch_size, "enrichment_outer_chunk": settings.full_enrichment_max_items, "full_analysis_batch": settings.full_analysis_batch_size, "processing_claim_lease_seconds": settings.processing_claim_lease_seconds, "hh_auth_storage_state_configured": bool(settings.hh_auth_storage_state_path), "orchestrator_token_configured": bool(settings.orchestrator_internal_api_token)}
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else "\n".join(f"{key}: {value}" for key, value in report.items()))
    return 0


async def main_async(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Worker operational diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("run_id"); run.add_argument("--json", action="store_true"); run.add_argument("--verbose", action="store_true")
    recent = sub.add_parser("recent"); recent.add_argument("--limit", type=int, default=10); recent.add_argument("--json", action="store_true")
    for name in ("health", "config", "limits"):
        command = sub.add_parser(name); command.add_argument("--json", action="store_true")
    hh = sub.add_parser("hh"); hh.add_argument("--profile-id"); hh.add_argument("--query-variant-id"); hh.add_argument("--json", action="store_true")
    args = parser.parse_args(argv); settings = Settings()
    if args.command == "run": return await _run(args, settings)
    if args.command == "recent": return await _recent(args, settings)
    if args.command == "health": return await _health(args, settings)
    if args.command in {"config", "limits"}: return await _config(args, settings)
    result = await HHTransportDiagnosticService.from_settings(settings).compare(args.profile_id, args.query_variant_id)
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
