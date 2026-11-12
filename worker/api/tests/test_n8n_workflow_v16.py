import json
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / "workflows" / "n8n"
V15 = WORKFLOWS / "AI Job Automation — Daily Search Digest v15.json"
V16 = WORKFLOWS / "AI Job Automation — Daily Search Digest v16.json"


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


def run_context() -> dict:
    return {"run_id": "run-1", "orchestration_started_at_ms": round(time.time() * 1000), "config": {}}


def test_v15_is_preserved_and_v16_is_new_recovery_workflow() -> None:
    assert load(V15)["name"] == "AI Job Automation — Daily Search Digest v15"
    assert load(V16)["name"] == "AI Job Automation — Daily Search Digest v16"
    assert V15.read_bytes() != V16.read_bytes()


def test_v16_is_valid_connected_and_has_unique_node_ids_and_positions() -> None:
    workflow = load(V16)
    names = {item["name"] for item in workflow["nodes"]}
    ids = [item["id"] for item in workflow["nodes"]]
    positions = [tuple(item["position"]) for item in workflow["nodes"]]

    assert len(ids) == len(set(ids))
    assert len(positions) == len(set(positions))
    for source, connection in workflow["connections"].items():
        assert source in names
        for branch in connection.get("main", []):
            for target in branch:
                assert target["node"] in names


def test_v16_recovery_uses_existing_resume_endpoint_without_new_collection() -> None:
    workflow = load(V16)
    resume = node(workflow, "Invoke Worker Resume")

    assert "/hh/pipeline-runs/{{ $(\"Build Full Run Context\").first().json.run_id }}/resume" in resume["parameters"]["url"]
    assert any(
        item["name"] == "X-Worker-Internal-Token" and "WORKER_INTERNAL_API_TOKEN" in item["value"]
        for item in resume["parameters"]["headerParameters"]["parameters"]
    )
    recovery_nodes = {"Worker Recovery Needed?", "Wait 60s Before Worker Recovery", "Invoke Worker Resume", "Evaluate Worker Resume"}
    for source in recovery_nodes:
        targets = [target["node"] for branch in workflow["connections"][source]["main"] for target in branch]
        assert "Start Worker Pipeline" not in targets


def test_v16_normal_completed_run_never_enters_recovery() -> None:
    workflow = load(V16)
    output = execute_code(
        node(workflow, "Evaluate Worker Run")["parameters"]["jsCode"],
        {"status": "completed", "result_available": True, "summary": {}},
        {"Build Full Run Context": run_context(), "Wait 20s for Worker Run": {}},
    )

    assert output["terminal"] is True
    assert output["result_available"] is True
    assert output["recovery_attempted"] is False
    assert output["recovery_needed"] is False


def test_v16_polling_treats_transient_failures_and_restart_as_recoverable() -> None:
    workflow = load(V16)
    code = node(workflow, "Evaluate Worker Run")["parameters"]["jsCode"]
    context = run_context()

    first = execute_code(code, {"statusCode": 503}, {"Build Full Run Context": context, "Wait 20s for Worker Run": {}})
    third = execute_code(code, {"statusCode": 504}, {"Build Full Run Context": context, "Wait 20s for Worker Run": {"consecutive_polling_errors": 2}})
    restarted = execute_code(code, {"statusCode": 404}, {"Build Full Run Context": context, "Wait 20s for Worker Run": {}})

    assert first["terminal"] is False and first["recovery_needed"] is False
    assert third["terminal"] is False and third["recovery_needed"] is True
    assert restarted["terminal"] is False and restarted["recovery_needed"] is True


def test_v16_auth_and_contract_polling_errors_are_fatal_immediately() -> None:
    workflow = load(V16)
    code = node(workflow, "Evaluate Worker Run")["parameters"]["jsCode"]
    values = {"Build Full Run Context": run_context(), "Wait 20s for Worker Run": {}}

    for status_code, expected in ((401, "worker_recovery_auth_failed"), (403, "worker_recovery_auth_failed"), (422, "worker_resume_contract_failed")):
        output = execute_code(code, {"statusCode": status_code}, values)
        assert output["terminal"] is True
        assert output["failure_code"] == expected
        assert output["recovery_needed"] is False


def test_v16_resume_handles_active_lease_nothing_to_resume_and_fatal_errors() -> None:
    workflow = load(V16)
    code = node(workflow, "Evaluate Worker Resume")["parameters"]["jsCode"]
    previous = {**run_context(), "recovery_attempt_count": 1, "recovery_started_at_ms": round(time.time() * 1000)}
    values = {"Wait 60s Before Worker Recovery": previous}

    accepted = execute_code(code, {"status": "running", "summary": {}}, values)
    active = execute_code(code, {"status": "completed", "result_available": False, "summary": {"resume_status": "in_progress"}}, values)
    nothing = execute_code(code, {"status": "completed", "result_available": True, "summary": {"resume_status": "nothing_to_resume"}}, values)
    auth = execute_code(code, {"statusCode": 401}, values)
    contract = execute_code(code, {"statusCode": 422}, values)

    assert accepted["terminal"] is False and accepted["recovery_needed"] is False and accepted["resume_status"] == "accepted"
    assert active["terminal"] is False and active["recovery_needed"] is True and active["resume_status"] == "in_progress"
    assert nothing["terminal"] is True and nothing["result_available"] is True and nothing["resume_status"] == "nothing_to_resume"
    assert auth["terminal"] is True and auth["failure_code"] == "worker_recovery_auth_failed"
    assert contract["terminal"] is True and contract["failure_code"] == "worker_resume_contract_failed"


def test_v16_resume_retry_is_bounded_and_timeout_is_specific() -> None:
    workflow = load(V16)
    code = node(workflow, "Evaluate Worker Resume")["parameters"]["jsCode"]
    base = {**run_context(), "recovery_started_at_ms": round(time.time() * 1000)}

    retry = execute_code(code, {"statusCode": 503}, {"Wait 60s Before Worker Recovery": {**base, "recovery_attempt_count": 1}})
    timeout = execute_code(code, {"statusCode": 503}, {"Wait 60s Before Worker Recovery": {**base, "recovery_attempt_count": 9}})

    assert retry["terminal"] is False and retry["recovery_needed"] is True
    assert timeout["terminal"] is True
    assert timeout["failure_code"] == "worker_recovery_timeout"
    assert timeout["resume_status"] == "timeout"


def test_v16_preserves_test_profiles_and_one_post_processing_path() -> None:
    workflow = load(V16)
    profile_code = node(workflow, "Build Selected Profile IDs")["parameters"]["jsCode"]
    completed_body = node(workflow, "Mark Pipeline Run Completed")["parameters"]["jsonBody"]
    failed_body = node(workflow, "Mark Pipeline Run Failed")["parameters"]["jsonBody"]

    assert "test_resume_recommendations" in profile_code
    assert "test_expanded_search" in profile_code
    assert "test_resume_recommendations" in profile_code.split("resumeProfileIds", 1)[1]
    assert workflow["connections"]["Worker Result Available?"]["main"][0][0]["node"] == "Mark Pipeline Run Completed"
    assert "recovery_attempted" in completed_body
    assert "recovery_duration_ms" in completed_body
    assert "recovery_attempted" in failed_body
    assert "Evaluate Worker Run" not in node(workflow, "Restore Completed Run Context")["parameters"]["jsCode"]
    assert "Evaluate Worker Run" not in node(workflow, "Restore Failed Run Context")["parameters"]["jsCode"]


def test_v16_restores_lifecycle_context_from_persisted_stats_after_recovery() -> None:
    workflow = load(V16)
    original = {**run_context(), "config": {"orchestrator_api_url": "http://orchestrator"}}
    completed = execute_code(
        node(workflow, "Restore Completed Run Context")["parameters"]["jsCode"],
        {
            "run_id": "run-1",
            "status": "completed",
            "stats_snapshot": {
                "collection_stats": {"unique_vacancy_count": 10},
                "recovery_attempted": True,
                "resume_status": "completed",
            },
        },
        {"Build Full Run Context": original},
    )
    failed = execute_code(
        node(workflow, "Restore Failed Run Context")["parameters"]["jsCode"],
        {"run_id": "run-1", "error_code": "worker_recovery_timeout", "error_summary": "Worker resume не стал доступен"},
        {"Build Full Run Context": original},
    )

    assert completed["config"] == original["config"]
    assert completed["worker"]["collection_stats"]["unique_vacancy_count"] == 10
    assert completed["resume_status"] == "completed"
    assert failed["failure_stage"] == "worker_recovery_timeout"
    assert failed["safe_error"] == "Worker resume не стал доступен"
