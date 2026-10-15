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


def test_v12_is_preserved_and_v13_is_a_separate_versioned_export() -> None:
    v12 = load(V12)
    v13 = load(V13)

    assert v12["name"] == "AI Job Automation — Daily Search CRM Digest v12"
    assert v13["name"] == "AI Job Automation — Daily Search CRM Digest v13"
    assert V12.read_bytes() != V13.read_bytes()


def test_v13_keeps_existing_email_branch_and_adds_one_independent_telegram_branch() -> None:
    v12 = load(V12)
    workflow = load(V13)
    targets = workflow["connections"]["Prepare Success Email"]["main"][0]

    assert node(workflow, "Gmail Send Digest") == node(v12, "Gmail Send Digest")
    assert {target["node"] for target in targets} == {
        "Gmail Send Digest",
        "Prepare Telegram Completion Notification",
    }
    assert workflow["connections"]["Prepare Telegram Completion Notification"]["main"][0][0]["node"] == (
        "Telegram Send Completion Notification"
    )
    assert "Telegram Send Completion Notification" not in workflow["connections"].get("Gmail Send Digest", {})


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
