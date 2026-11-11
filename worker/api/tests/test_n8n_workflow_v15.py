import json
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / "workflows" / "n8n"
V14 = WORKFLOWS / "AI Job Automation — Daily Search Digest v14.json"
V15 = WORKFLOWS / "AI Job Automation — Daily Search Digest v15.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def execute_code(code: str, payload: dict, values: dict[str, dict]) -> dict:
    harness = f"""
const code = {json.dumps(code)};
const values = {json.dumps(values)};
const execute = new Function('$', '$input', code);
console.log(JSON.stringify(execute(
  (name) => ({{ first: () => ({{ json: values[name] || {{}} }}), item: {{ json: values[name] || {{}} }} }}),
  {{ first: () => ({{ json: {json.dumps(payload)} }}) }},
)));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)[0]["json"]


def test_v14_is_preserved_and_v15_adds_a_distinct_recovery_workflow() -> None:
    assert load(V14)["name"] == "AI Job Automation — Daily Search Digest v14"
    assert load(V15)["name"] == "AI Job Automation — Daily Search Digest v15"
    assert V14.read_bytes() != V15.read_bytes()


def test_v15_is_valid_connected_and_has_unique_node_ids_and_positions() -> None:
    workflow = load(V15)
    names = {item["name"] for item in workflow["nodes"]}
    ids = [item["id"] for item in workflow["nodes"]]
    positions = [tuple(item["position"]) for item in workflow["nodes"]]

    assert len(ids) == len(set(ids))
    assert len(positions) == len(set(positions))
    serialized = json.dumps(workflow, ensure_ascii=False)
    assert "n8n-nodes-base.googleSheets" not in serialized
    assert "crm_sync_failed" not in serialized
    for source, connection in workflow["connections"].items():
        assert source in names
        for branch in connection.get("main", []):
            for target in branch:
                assert target["node"] in names


def test_v15_recovery_branch_uses_backlog_then_internal_worker_resume_without_new_search() -> None:
    workflow = load(V15)
    assert workflow["connections"]["Evaluate Worker Run"]["main"][0][0]["node"] == "Worker Recovery Needed?"
    assert workflow["connections"]["Worker Recovery Needed?"]["main"][0][0]["node"] == "Wait 60s Before Worker Recovery"
    assert workflow["connections"]["Resume Backlog Available?"]["main"][0][0]["node"] == "Invoke Worker Resume"
    resume = node(workflow, "Invoke Worker Resume")
    assert "/hh/pipeline-runs/{{ $(\"Build Full Run Context\").first().json.run_id }}/resume" in resume["parameters"]["url"]
    assert any(item["name"] == "X-Worker-Internal-Token" and "WORKER_INTERNAL_API_TOKEN" in item["value"] for item in resume["parameters"]["headerParameters"]["parameters"])
    assert "/internal/processing-runs/" in node(workflow, "Check Processing Backlog")["parameters"]["url"]
    recovery_sources = {
        "Worker Recovery Needed?",
        "Wait 60s Before Worker Recovery",
        "Check Processing Backlog",
        "Evaluate Recovery Backlog",
        "Worker Recovery Terminal?",
        "Resume Backlog Available?",
        "Invoke Worker Resume",
        "Evaluate Worker Resume",
    }
    for source in recovery_sources:
        targets = [target["node"] for branch in workflow["connections"][source]["main"] for target in branch]
        assert "Start Worker Pipeline" not in targets

    config_snapshot = node(workflow, "Register Manual Pipeline Run")["parameters"]["jsonBody"]
    for key in ("processing_versions", "preliminary_model", "full_analysis_model", "preliminary_prompt_version"):
        assert key in config_snapshot


def test_v15_polling_classifies_temporary_worker_outage_as_recoverable_after_three_attempts() -> None:
    workflow = load(V15)
    code = node(workflow, "Evaluate Worker Run")["parameters"]["jsCode"]
    context = {"run_id": "run-1", "orchestration_started_at_ms": round(time.time() * 1000), "config": {"worker_recovery_max_attempts": 10}}

    first = execute_code(code, {"statusCode": 503}, {"Build Full Run Context": context, "Wait 20s for Worker Run": {}})
    third = execute_code(code, {"statusCode": 503}, {"Build Full Run Context": context, "Wait 20s for Worker Run": {"consecutive_polling_errors": 2}})
    fatal = execute_code(code, {"statusCode": 401}, {"Build Full Run Context": context, "Wait 20s for Worker Run": {}})

    assert first["terminal"] is False and first["recovery_needed"] is False
    assert third["terminal"] is False and third["recovery_needed"] is True
    assert fatal["terminal"] is True
    assert fatal["failure_code"] == "worker_polling_contract_failed"


def test_v15_active_lease_and_nothing_to_resume_are_not_false_terminal_failures() -> None:
    workflow = load(V15)
    code = node(workflow, "Evaluate Worker Resume")["parameters"]["jsCode"]
    previous = {"run_id": "run-1", "config": {"worker_recovery_max_attempts": 10}, "recovery_attempt_count": 1}

    active = execute_code(code, {"status": "completed", "result_available": False, "summary": {"resume_status": "in_progress"}}, {"Evaluate Recovery Backlog": previous})
    complete = execute_code(code, {"status": "completed", "result_available": True, "summary": {"resume_status": "nothing_to_resume"}}, {"Evaluate Recovery Backlog": previous})

    assert active["recovery_needed"] is True and active["terminal"] is False
    assert complete["terminal"] is True and complete["result_available"] is True


def test_v15_backlog_recovery_has_bounded_window_and_fatal_internal_contract_errors() -> None:
    workflow = load(V15)
    code = node(workflow, "Evaluate Recovery Backlog")["parameters"]["jsCode"]
    base = {"run_id": "run-1", "config": {"worker_recovery_max_attempts": 10}}

    available = execute_code(code, {"summary": {"total": 3, "preliminary_pending": 2}}, {"Wait 60s Before Worker Recovery": base})
    timeout = execute_code(code, {"summary": {"total": 0}}, {"Wait 60s Before Worker Recovery": {**base, "recovery_attempt_count": 9}})
    fatal = execute_code(code, {"statusCode": 401}, {"Wait 60s Before Worker Recovery": base})

    assert available["resume_allowed"] is True and available["terminal"] is False
    assert timeout["terminal"] is True and timeout["failure_code"] == "worker_recovery_timeout"
    assert fatal["terminal"] is True and fatal["failure_code"] == "worker_recovery_failed"


def test_v15_keeps_one_post_processing_path_and_records_recovery_stats() -> None:
    workflow = load(V15)
    completed = node(workflow, "Mark Pipeline Run Completed")["parameters"]["jsonBody"]
    assert "recovery_attempted" in completed
    assert "recovery_attempt_count" in completed
    assert "recovery_duration_ms" in completed
    assert workflow["connections"]["Worker Result Available?"]["main"][0][0]["node"] == "Mark Pipeline Run Completed"
    assert workflow["connections"]["Evaluate Worker Resume"]["main"][0][0]["node"] == "Worker Recovery Needed?"
