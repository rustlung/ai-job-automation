import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / "workflows" / "n8n" / "AI Job Automation — Application CRM Sync v1.json"


def load() -> dict:
    return json.loads(WORKFLOW.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def prepare_update(request: dict, rows: list[dict]) -> dict:
    code = node(load(), "Prepare Application CRM Update")["parameters"]["jsCode"]
    harness = f"""
const execute = new Function('$', '$input', {json.dumps(code)});
const result = execute(
  (name) => ({{ first: () => ({{ json: {json.dumps(request)} }}) }}),
  {{ all: () => {json.dumps([{'json': row} for row in rows])} }},
);
console.log(JSON.stringify(result));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)[0]["json"]


def test_application_crm_sync_workflow_is_a_narrow_existing_row_adapter() -> None:
    workflow = load()
    update = node(workflow, "Update Application CRM Row")
    prepare_code = node(workflow, "Prepare Application CRM Update")["parameters"]["jsCode"]

    assert workflow["name"] == "AI Job Automation — Application CRM Sync v1"
    assert "Daily Search CRM Digest" not in workflow["name"]
    assert "legacy_crm_key_fallback" in prepare_code
    assert "crm_row_not_found" in prepare_code
    assert update["parameters"]["operation"] == "appendOrUpdate"
    assert update["parameters"]["columns"]["value"].keys() == {
        "№", "CRM Key", "Отклик", "Ответ", "Интервью", "Итог",
        "Дата отклика", "Текст отклика", "Ответ работодателя", "Дата ответа",
        "Дата интервью", "Комментарий / заметки",
    }
    assert "Respond Application CRM Row Missing" in workflow["connections"]["Application CRM Row Found?"]["main"][1][0]["node"]


def test_main_daily_crm_workflow_v12_is_not_changed_by_application_adapter() -> None:
    daily = ROOT / "workflows" / "n8n" / "AI Job Automation — Daily Search CRM Digest v12.json"
    assert json.loads(daily.read_text(encoding="utf-8-sig"))["name"] == "AI Job Automation — Daily Search CRM Digest v12"


def test_application_crm_adapter_prefers_business_key_then_uses_member_legacy_key() -> None:
    request = {
        "presentation_key": "business:fingerprint",
        "canonical_member_keys": ["hh:kazan", "hh:samara"],
        "columns": {"Отклик": "Да", "Итог": None},
    }
    primary = prepare_update(request, [{"№": 1, "CRM Key": "business:fingerprint", "Итог": "Старый итог"}, {"№": 2, "CRM Key": "hh:kazan"}])
    legacy = prepare_update(request, [{"№": 2, "CRM Key": "hh:kazan", "Итог": "Старый итог"}])
    missing = prepare_update(request, [])

    assert primary["№"] == 1
    assert primary["match_strategy"] == "business_key"
    assert legacy["№"] == 2
    assert legacy["CRM Key"] == "business:fingerprint"
    assert legacy["match_strategy"] == "legacy_crm_key_fallback"
    assert legacy["Итог"] == "Старый итог"
    assert missing == {"found": False, "error_code": "crm_row_not_found"}
