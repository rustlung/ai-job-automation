import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / "workflows" / "n8n"
V13 = WORKFLOWS / "AI Job Automation — Daily Search CRM Digest v13.json"
V14 = WORKFLOWS / "AI Job Automation — Daily Search Digest v14.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def execute_digest(workflow: dict, context: dict, run: dict) -> dict:
    code = node(workflow, "Prepare Success Email")["parameters"]["jsCode"]
    harness = f"""
const code = {json.dumps(code)};
const values = {{
  'Build Run Context': [{json.dumps(context)}],
  'Get Current Run': [{json.dumps(run)}],
}};
const getItems = (name) => (values[name] || []).map(value => ({{ json: value }}));
const execute = new Function('$', '$items', code);
console.log(JSON.stringify(execute(
  (name) => ({{ all: () => getItems(name) }}),
  (name) => getItems(name),
)));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)[0]["json"]


def execute_integration_code(code: str, response: dict, run_context: dict) -> dict:
    harness = f"""
const code = {json.dumps(code)};
const execute = new Function('$', '$input', code);
console.log(JSON.stringify(execute(
  () => ({{ first: () => ({{ json: {json.dumps(run_context)} }}) }}),
  {{ first: () => ({{ json: {json.dumps(response)} }}) }},
)));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)[0]["json"]


def test_v13_is_preserved_and_v14_is_a_new_daily_digest_successor() -> None:
    assert load(V13)["name"] == "AI Job Automation — Daily Search CRM Digest v13"
    assert load(V14)["name"] == "AI Job Automation — Daily Search Digest v14"
    assert V13.read_bytes() != V14.read_bytes()


def test_v14_is_valid_connected_and_has_no_google_sheets_or_crm_runtime_nodes() -> None:
    workflow = load(V14)
    node_names = {item["name"] for item in workflow["nodes"]}
    ids = [item["id"] for item in workflow["nodes"]]
    positions = [tuple(item["position"]) for item in workflow["nodes"]]
    serialized = json.dumps(workflow, ensure_ascii=False)

    assert len(ids) == len(set(ids))
    assert len(positions) == len(set(positions))
    assert "n8n-nodes-base.googleSheets" not in serialized
    for forbidden in ("Google Sheets", "GOOGLE_SHEETS", "CRM Key", "crm_sync_failed", "Prepare CRM Rows", "Legacy CRM"):
        assert forbidden not in serialized
    for source, connection in workflow["connections"].items():
        assert source in node_names
        for branch in connection.get("main", []):
            for target in branch:
                assert target["node"] in node_names


def test_v14_prepares_gmail_digest_from_grouped_orchestrator_run_data() -> None:
    v13 = load(V13)
    workflow = load(V14)
    prepare = node(workflow, "Prepare Success Email")["parameters"]["jsCode"]

    assert workflow["connections"]["Get Current Run"]["main"][0][0]["node"] == "Prepare Success Email"
    assert "Get Current Run" in prepare
    assert "run.analyses" in prepare
    assert "Prepare CRM Rows" not in prepare
    assert "spreadsheet_url" not in prepare
    assert node(workflow, "Gmail Send Digest")["type"] == "n8n-nodes-base.gmail"
    assert node(workflow, "Gmail Send Digest")["parameters"] == node(v13, "Gmail Send Digest")["parameters"]
    assert node(workflow, "Gmail Send Digest")["credentials"] == node(v13, "Gmail Send Digest")["credentials"]
    assert node(workflow, "Telegram Send Completion Notification")["type"] == "n8n-nodes-base.httpRequest"


def test_v14_digest_handles_empty_results_and_ranks_top_vacancies_deterministically() -> None:
    workflow = load(V14)
    context = {
        "run_id": "run-1",
        "config": {"email_to": "user@example.com", "top_vacancy_limit": 3},
        "worker": {
            "collection_stats": {"unique_vacancy_count": 5},
            "filter_stats": {"processed_count": 4},
            "enrichment_stats": {"enriched_count": 3},
            "persistence_stats": {"persisted_count": 3},
            "duration_ms": 1200,
        },
        "mode": "worker_pipeline",
        "warnings": [],
    }
    analyses = [
        {"id": 30, "priority": "ALT", "final_score": 99, "summary": "Alt", "vacancy_snapshot": {"company": "C", "title": "Alt", "url": "https://example.test/alt"}},
        {"id": 20, "priority": "P2", "final_score": 80, "summary": "P2", "risks": ["english_required"], "vacancy_snapshot": {"company": "B", "title": "P2", "url": "https://example.test/p2"}},
        {"id": 11, "priority": "P1", "final_score": 75, "semantic_snapshot": {"short_reason": "Причина"}, "vacancy_snapshot": {"company": "А", "title": "P1 earlier", "url": "https://example.test/p1a"}},
        {"id": 10, "priority": "P1", "final_score": 75, "vacancy_snapshot": {"company": "А", "title": "P1 first", "url": "https://example.test/p1b"}},
    ]

    digest = execute_digest(workflow, context, {"run_id": "run-1", "analyses": analyses})
    complete_digest = execute_digest(
        workflow,
        {**context, "config": {**context["config"], "top_vacancy_limit": 4}},
        {"run_id": "run-1", "analyses": analyses},
    )
    empty = execute_digest(workflow, context, {"run_id": "run-1", "analyses": []})
    top_html = digest["html"].split("<h3>Top vacancies</h3>", maxsplit=1)[1]
    complete_top_html = complete_digest["html"].split("<h3>Top vacancies</h3>", maxsplit=1)[1]

    assert "P1: 2, P2: 1, ALT: 1, P3: 0" in digest["html"]
    assert top_html.index("P1 first") < top_html.index("P1 earlier") < top_html.index("P2")
    assert "Alt" not in top_html
    assert complete_top_html.index("P2") < complete_top_html.index("Alt")
    assert "https://example.test/p1b" in digest["html"]
    assert "Причина: —" in digest["html"]
    assert "Требуется английский" in digest["html"]
    assert "Top vacancies" in empty["html"]
    assert "P1: 0, P2: 0, ALT: 0, P3: 0" in empty["html"]


def test_v14_keeps_concrete_gmail_and_telegram_integration_error_updates() -> None:
    workflow = load(V14)
    run_context = {"run_id": "run-1", "config": {"orchestrator_api_url": "http://orchestrator"}}
    gmail = execute_integration_code(
        node(workflow, "Prepare Gmail Integration Lifecycle Update")["parameters"]["jsCode"],
        {"error": {"message": "gmail unavailable"}},
        run_context,
    )
    telegram = execute_integration_code(
        node(workflow, "Prepare Telegram Integration Lifecycle Update")["parameters"]["jsCode"],
        {"error": {"message": "gateway unavailable"}},
        run_context,
    )

    assert gmail["integration_error"]["code"] == "gmail_digest_failed"
    assert telegram["integration_error"]["code"] == "telegram_notification_failed"
    for name in ("Mark Pipeline Run Gmail Integration Failed", "Mark Pipeline Run Telegram Integration Failed"):
        body = node(workflow, name)["parameters"]["jsonBody"]
        assert "completed_with_errors" in body
        assert "integration_errors" in body
    assert node(workflow, "Gmail Send Digest")["continueOnFail"] is True
    assert node(workflow, "Telegram Send Completion Notification")["continueOnFail"] is True
