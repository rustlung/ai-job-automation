import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / "workflows" / "n8n"
V12 = WORKFLOWS / "AI Job Automation — Daily Search CRM Digest v12.json"
V13 = WORKFLOWS / "AI Job Automation — Daily Search CRM Digest v13.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def telegram_message(workflow: dict, run_context: dict, run: dict) -> str:
    code = node(workflow, "Prepare Telegram Completion Notification")["parameters"]["jsCode"]
    harness = f"""
const code = {json.dumps(code)};
const values = {{
  'Build Run Context': {json.dumps(run_context)},
  'Get Current Run': {json.dumps(run)},
}};
const getItems = (name) => [{{ json: values[name] || {{}} }}];
const execute = new Function('$', '$items', '$input', code);
console.log(JSON.stringify(execute(
  (name) => ({{ all: () => getItems(name) }}),
  (name) => getItems(name),
  {{ first: () => ({{ json: {{}} }}) }},
)));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)[0]["json"]["text"]


def execute_input_code(code: str, value: dict) -> dict:
    harness = f"""
const code = {json.dumps(code)};
const execute = new Function('$input', code);
console.log(JSON.stringify(execute({{ first: () => ({{ json: {json.dumps(value)} }}) }})));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)[0]["json"]


def execute_integration_code(code: str, value: dict, run_context: dict) -> dict:
    harness = f"""
const code = {json.dumps(code)};
const execute = new Function('$', '$input', code);
console.log(JSON.stringify(execute(
  (name) => ({{ first: () => ({{ json: {json.dumps(run_context)} }}) }}),
  {{ first: () => ({{ json: {json.dumps(value)} }}) }},
)));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)[0]["json"]


def test_v12_is_preserved_and_v13_is_a_separate_versioned_export() -> None:
    v12 = load(V12)
    v13 = load(V13)

    assert v12["name"] == "AI Job Automation — Daily Search CRM Digest v12"
    assert v13["name"] == "AI Job Automation — Daily Search CRM Digest v13"
    assert V12.read_bytes() != V13.read_bytes()


def test_v13_keeps_email_delivery_and_runs_telegram_after_its_result_is_known() -> None:
    v12 = load(V12)
    workflow = load(V13)
    targets = workflow["connections"]["Prepare Success Email"]["main"][0]

    assert node(workflow, "Gmail Send Digest")["parameters"] == node(v12, "Gmail Send Digest")["parameters"]
    assert node(workflow, "Gmail Send Digest")["credentials"] == node(v12, "Gmail Send Digest")["credentials"]
    assert [target["node"] for target in targets] == ["Gmail Send Digest"]
    assert workflow["connections"]["Gmail Send Digest"]["main"][0][0]["node"] == "Prepare Gmail Integration Lifecycle Update"
    assert workflow["connections"]["Gmail Integration Failed?"]["main"][1][0]["node"] == "Prepare Telegram Completion Notification"
    assert workflow["connections"]["Prepare Telegram Completion Notification"]["main"][0][0]["node"] == (
        "Telegram Send Completion Notification"
    )
    assert workflow["connections"]["Telegram Send Completion Notification"]["main"][0][0]["node"] == "Prepare Telegram Integration Lifecycle Update"


def test_v13_telegram_gateway_request_uses_environment_credentials_and_is_non_blocking() -> None:
    workflow = load(V13)
    request = node(workflow, "Telegram Send Completion Notification")
    message_code = node(workflow, "Prepare Telegram Completion Notification")["parameters"]["jsCode"]
    parameters = request["parameters"]
    authorization = parameters["headerParameters"]["parameters"][0]

    assert request["type"] == "n8n-nodes-base.httpRequest"
    assert request["continueOnFail"] is True
    assert parameters["method"] == "POST"
    assert "$env.AI_JOB_GATEWAY_BASE_URL" in parameters["url"]
    assert "/ai-job/sendMessage" in parameters["url"]
    assert authorization["name"] == "Authorization"
    assert "$env.AI_JOB_GATEWAY_KEY" in authorization["value"]
    assert parameters["jsonBody"] == "={{ { text: $json.text } }}"
    assert "AI_JOB_GATEWAY_KEY=" not in V13.read_text(encoding="utf-8-sig")
    assert "spreadsheet_url" not in message_code
    assert "P1:" not in message_code


def test_v13_telegram_message_uses_only_available_completion_counts_without_links() -> None:
    workflow = load(V13)
    message = telegram_message(
        workflow,
        {
            "mode": "worker_pipeline",
            "config": {"spreadsheet_url": "https://docs.google.com/spreadsheets/d/example"},
            "worker": {
                "enrichment_stats": {"enriched_count": 9},
            },
        },
        {"analyses": [{"priority": "P1"}, {"priority": "P2"}, {"priority": "ALT"}, {"priority": "P3"}]},
    )

    assert "AI Job Automation: обработка вакансий завершена." in message
    assert "Обработано: 9" in message
    assert "Отобрано: 3" in message
    assert "https://" not in message
    assert "P1:" not in message
    assert "P2:" not in message
    assert "ALT:" not in message
    assert "vacancy_snapshot" not in message


def test_v13_telegram_message_omits_unavailable_optional_fields() -> None:
    message = telegram_message(load(V13), {"mode": "existing_run_replay", "config": {}, "worker": {}}, {"analyses": []})

    assert message == "AI Job Automation: синхронизация завершена.\nОтобрано: 0"


def test_v13_has_unique_node_ids_and_positions() -> None:
    workflow = load(V13)
    ids = [item["id"] for item in workflow["nodes"]]
    positions = [tuple(item["position"]) for item in workflow["nodes"]]

    assert len(ids) == len(set(ids))
    assert len(positions) == len(set(positions))


def test_v13_marks_web_preflight_failures_terminal_before_stopping_execution() -> None:
    workflow = load(V13)
    preflight_targets = workflow["connections"]["Preflight OK?"]["main"][1]
    update = node(workflow, "Mark Pipeline Run Preflight Failed")
    prepare = node(workflow, "Prepare Preflight Failure Lifecycle Update")

    assert preflight_targets[0]["node"] == "Web Pipeline Run Exists?"
    assert workflow["connections"]["Web Pipeline Run Exists?"]["main"][0][0]["node"] == "Prepare Preflight Failure Lifecycle Update"
    assert workflow["connections"]["Prepare Preflight Failure Lifecycle Update"]["main"][0][0]["node"] == "Mark Pipeline Run Preflight Failed"
    assert workflow["connections"]["Mark Pipeline Run Preflight Failed"]["main"][0][0]["node"] == "Stop Preflight Failed"
    assert "hh_auth_failed" in prepare["parameters"]["jsCode"]
    assert "status: 'failed'" in update["parameters"]["jsonBody"]
    assert "error_code" in update["parameters"]["jsonBody"]
    assert "error_summary" in update["parameters"]["jsonBody"]
    assert "failure.detail" not in update["parameters"]["jsonBody"]

    payload = execute_input_code(
        prepare["parameters"]["jsCode"],
        {
            "run_id": "web-run-001",
            "trigger_source": "web_ui",
            "safe_error": "Preflight failed: HH auth storage state not configured",
            "failures": [{"component": "HH auth"}],
        },
    )
    assert payload["error_code"] == "hh_auth_failed"
    assert payload["error_summary"] == "Preflight failed: HH auth storage state not configured"


def test_v13_records_processing_diagnostics_without_turning_core_success_into_terminal_error() -> None:
    workflow = load(V13)
    evaluate = node(workflow, "Evaluate Worker Run")["parameters"]["jsCode"]
    completed = node(workflow, "Mark Pipeline Run Completed")["parameters"]["jsonBody"]
    failed = node(workflow, "Mark Pipeline Run Failed")["parameters"]["jsonBody"]

    assert "summary.warnings" in evaluate
    assert "summary.partial_failures" in evaluate
    assert "warnings: result.warnings" in completed
    assert "partial_failures: result.partial_failures" in completed
    assert "status: 'completed'" in completed
    assert "error_code" not in completed
    assert "error_summary" not in completed
    assert "failure_code" in failed
    assert "failure_summary" in failed


def test_v13_marks_only_concrete_post_run_integration_failures_as_completed_with_errors() -> None:
    workflow = load(V13)
    crm = node(workflow, "Record Legacy CRM Key Migration Stats")["parameters"]["jsonBody"]
    gmail_prepare = node(workflow, "Prepare Gmail Integration Lifecycle Update")["parameters"]["jsCode"]
    telegram_prepare = node(workflow, "Prepare Telegram Integration Lifecycle Update")["parameters"]["jsCode"]

    assert "crm_sync_failed" in crm
    assert "integration_errors" in crm
    assert "completed_with_errors" in crm
    assert "gmail_digest_failed" in gmail_prepare
    assert "Не удалось отправить Gmail-дайджест." in gmail_prepare
    assert "telegram_notification_failed" in telegram_prepare
    assert "Не удалось отправить Telegram-уведомление." in telegram_prepare
    for name in ("Gmail Send Digest", "Telegram Send Completion Notification"):
        assert node(workflow, name)["continueOnFail"] is True
    for name in ("Mark Pipeline Run Gmail Integration Failed", "Mark Pipeline Run Telegram Integration Failed"):
        body = node(workflow, name)["parameters"]["jsonBody"]
        assert "completed_with_errors" in body
        assert "integration_errors" in body

    run_context = {"run_id": "run-001", "config": {"orchestrator_api_url": "http://orchestrator"}}
    telegram_failure = execute_integration_code(telegram_prepare, {"error": {"message": "gateway unavailable"}}, run_context)
    gmail_success = execute_integration_code(gmail_prepare, {"id": "message-001"}, run_context)

    assert telegram_failure["integration_error"] == {
        "code": "telegram_notification_failed",
        "count": 1,
        "summary": "Не удалось отправить Telegram-уведомление.",
    }
    assert gmail_success["integration_error"] is None
