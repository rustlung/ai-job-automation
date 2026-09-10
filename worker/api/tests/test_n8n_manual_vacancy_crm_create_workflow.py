import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / "workflows" / "n8n" / "AI Job Automation — Manual Vacancy CRM Create v1.json"


def load() -> dict:
    return json.loads(WORKFLOW.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def prepare(request: dict, rows: list[dict]) -> dict:
    code = node(load(), "Prepare Manual Vacancy CRM Create")["parameters"]["jsCode"]
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


def test_manual_vacancy_workflow_has_narrow_exact_key_topology() -> None:
    workflow = load()
    read = node(workflow, "Read Manual Vacancy CRM Rows")
    append = node(workflow, "Append Manual Vacancy CRM Row")
    prepare_code = node(workflow, "Prepare Manual Vacancy CRM Create")["parameters"]["jsCode"]
    positions = [tuple(item["position"]) for item in workflow["nodes"]]

    assert workflow["name"] == "AI Job Automation — Manual Vacancy CRM Create v1"
    assert node(workflow, "Manual Vacancy CRM Create Webhook")["parameters"]["path"] == "ai-job-automation-manual-vacancy-crm-create-v1"
    assert read["alwaysOutputData"] is True
    assert append["parameters"]["operation"] == "append"
    assert "['CRM Key']" in prepare_code
    assert "Компания" not in prepare_code
    assert "Ссылка" not in prepare_code
    assert "vacancy/" not in prepare_code
    assert len(positions) == len(set(positions))


def test_exact_manual_key_controls_append_existing_and_ambiguous() -> None:
    request = {"presentation_key": "manual:uuid-1", "sheet_name": "Вакансии", "columns": {"CRM Key": "manual:uuid-1"}}

    missing = prepare(request, [{"CRM Key": "manual:other", "Компания": "Same title"}])
    existing = prepare(request, [{"CRM Key": "manual:uuid-1"}])
    ambiguous = prepare(request, [{"CRM Key": "manual:uuid-1"}, {"CRM Key": "manual:uuid-1"}])

    assert missing["action"] == "append"
    assert existing == {"action": "already_exists", "status": "synced", "result": "already_exists"}
    assert ambiguous == {"action": "ambiguous", "error_code": "crm_row_ambiguous"}


def test_append_mapping_contains_only_expected_crm_values_and_empty_ai_fields() -> None:
    workflow = load()
    mapping = node(workflow, "Append Manual Vacancy CRM Row")["parameters"]["columns"]["value"]
    columns = {
        "Компания": "Manual Co", "Должность": "Manual role", "Тип": "Manual", "Приоритет": "",
        "ЗП": "", "Формат": "", "Стек": "", "Дата": "10.09.2026", "Отклик": "Нет",
        "Ответ": "Нет", "Интервью": "Нет", "Итог": "Нет", "Ссылка": "", "Комментарий": "",
        "Score": "", "AI причина": "", "Риски": "", "Hard blockers": "", "CRM Key": "manual:uuid-1",
        "Run ID": "", "Анализ обновлён": "", "Мой приоритет": "", "Профили поиска": "",
    }
    prepared = prepare({"presentation_key": "manual:uuid-1", "sheet_name": "Вакансии", "columns": columns}, [])

    assert prepared == {"action": "append", **columns}
    assert set(mapping) == set(columns)
    assert all(columns[name] == "" for name in ["Приоритет", "Score", "AI причина", "Риски", "Hard blockers", "Run ID", "Анализ обновлён", "Профили поиска"])


def test_workflow_validates_secret_and_manual_contract() -> None:
    workflow = load()
    code = node(workflow, "Validate Manual Vacancy CRM Create")["parameters"]["jsCode"]
    assert "x-ai-job-automation-webhook-secret" in code
    assert "N8N_WEBHOOK_SECRET" in code
    assert "startsWith('manual:')" in code
    assert "Invalid manual vacancy CRM create request" in code


def test_workflow_never_appends_for_existing_or_ambiguous_rows() -> None:
    workflow = load()
    ambiguous_targets = workflow["connections"]["Manual Vacancy CRM Row Ambiguous?"]["main"]
    existing_targets = workflow["connections"]["Manual Vacancy CRM Row Exists?"]["main"]

    assert ambiguous_targets[0][0]["node"] == "Respond Manual Vacancy CRM Ambiguous"
    assert existing_targets[0][0]["node"] == "Respond Manual Vacancy CRM Exists"
    assert existing_targets[1][0]["node"] == "Append Manual Vacancy CRM Row"
