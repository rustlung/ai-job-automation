import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / "workflows" / "n8n" / "AI Job Automation — Application CRM Sync v1.json"
WORKFLOW_V2 = ROOT / "workflows" / "n8n" / "AI Job Automation — Application CRM Sync v2.json"
WORKFLOW_V3 = ROOT / "workflows" / "n8n" / "AI Job Automation — Application CRM Sync v3.json"


def load(path: Path = WORKFLOW) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def prepare_update(request: dict, rows: list[dict], workflow_path: Path = WORKFLOW) -> dict:
    code = node(load(workflow_path), "Prepare Application CRM Update")["parameters"]["jsCode"]
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


def normalize_request(request: dict) -> dict:
    code = node(load(WORKFLOW_V2), "Validate and Normalize Application CRM Sync")["parameters"]["jsCode"]
    harness = f"""
const execute = new Function('$input', '$env', {json.dumps(code)});
const result = execute(
  {{ first: () => ({{ json: {json.dumps({'headers': {'x-ai-job-automation-webhook-secret': 'test-secret'}, 'body': request})} }}) }},
  {{ N8N_WEBHOOK_SECRET: 'test-secret' }},
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


def test_application_crm_sync_v2_preserves_v1_and_adds_exact_hh_url_fallback() -> None:
    v1 = load()
    workflow = load(WORKFLOW_V2)
    prepare_code = node(workflow, "Prepare Application CRM Update")["parameters"]["jsCode"]
    positions = [tuple(item["position"]) for item in workflow["nodes"]]

    assert v1["name"] == "AI Job Automation — Application CRM Sync v1"
    assert workflow["name"] == "AI Job Automation — Application CRM Sync v2"
    assert node(workflow, "Application CRM Sync Webhook")["parameters"]["path"] == "ai-job-automation-application-crm-sync-v2"
    assert "exact_hh_url_fallback" in prepare_code
    assert "crm_row_ambiguous" in prepare_code
    assert "candidate['Ссылка']" in prepare_code
    assert "!request.source" in node(workflow, "Validate and Normalize Application CRM Sync")["parameters"]["jsCode"]
    assert "!request.external_id" in node(workflow, "Validate and Normalize Application CRM Sync")["parameters"]["jsCode"]
    assert len(positions) == len(set(positions))
    assert workflow["connections"]["Application CRM Row Ambiguous?"]["main"][0][0]["node"] == "Respond Application CRM Row Ambiguous"
    assert workflow["connections"]["Application CRM Row Ambiguous?"]["main"][1][0]["node"] == "Respond Application CRM Row Missing"


def test_application_crm_sync_v2_normalizes_required_canonical_identity() -> None:
    request = {
        "application_id": 3,
        "presentation_key": "hh:134482249",
        "canonical_member_keys": ["hh:134482249"],
        "source": "hh",
        "external_id": "134482249",
        "sheet_name": "Вакансии",
        "columns": {},
    }

    normalized = normalize_request(request)

    assert normalized["source"] == "hh"
    assert normalized["external_id"] == "134482249"


def test_application_crm_sync_v3_normalizes_markdown_wrapped_hh_url_for_production_case() -> None:
    workflow = load(WORKFLOW_V3)
    request = {
        "application_id": 3,
        "presentation_key": "hh:134482249",
        "canonical_member_keys": ["hh:134482249"],
        "source": "hh",
        "external_id": "134482249",
        "sheet_name": "Вакансии",
        "columns": {},
    }
    rows = [
        {"№": 26, "row_number": 26, "Компания": "ЭОС", "Ссылка": "https://samara.hh.ru/vacancy/134683242", "CRM Key": ""},
        {
            "№": 14,
            "row_number": 14,
            "Компания": "beoma",
            "Ссылка": "[https://samara.hh.ru/vacancy/134482249](https://samara.hh.ru/vacancy/134482249)",
            "CRM Key": "",
        },
        {"№": 40, "row_number": 40, "Компания": "Other", "Ссылка": "https://hh.ru/vacancy/134000000", "CRM Key": ""},
    ]

    resolved = prepare_update(request, rows, WORKFLOW_V3)

    assert workflow["name"] == "AI Job Automation — Application CRM Sync v3"
    assert node(workflow, "Application CRM Sync Webhook")["parameters"]["path"] == "ai-job-automation-application-crm-sync-v3"
    assert "function normalizeUrl" in node(workflow, "Prepare Application CRM Update")["parameters"]["jsCode"]
    assert resolved["found"] is True
    assert resolved["match_strategy"] == "exact_hh_url_fallback"
    assert resolved["№"] == 14
    assert resolved["CRM Key"] == "hh:134482249"


def test_application_crm_sync_v3_accepts_only_raw_or_whole_markdown_hh_links() -> None:
    request = {
        "presentation_key": "hh:134060247",
        "canonical_member_keys": ["hh:134060247"],
        "source": "hh",
        "external_id": "134060247",
        "columns": {},
    }
    supported_urls = [
        "https://hh.ru/vacancy/134060247",
        "https://samara.hh.ru/vacancy/134060247?hhtmFrom=vacancy_search_list",
        "https://kazan.hh.ru/vpncheeck?backUrl=%2Fvacancy%2F134060247",
        "[vacancy](https://samara.hh.ru/vacancy/134060247)",
        "[https://samara.hh.ru/vacancy/134060247](https://samara.hh.ru/vacancy/134060247?hhtmFrom=vacancy_search_list)",
    ]
    unsupported_urls = [
        "[vacancy](not-a-url)",
        "[vacancy](https://example.com/vacancy/134060247)",
        "see [vacancy](https://hh.ru/vacancy/134060247)",
    ]

    for url in supported_urls:
        assert prepare_update(request, [{"№": 1, "Ссылка": url, "CRM Key": ""}], WORKFLOW_V3)["found"] is True
    for url in unsupported_urls:
        assert prepare_update(request, [{"№": 1, "Ссылка": url, "CRM Key": ""}], WORKFLOW_V3) == {"found": False, "error_code": "crm_row_not_found"}


def test_application_crm_sync_v3_rejects_duplicate_exact_markdown_links() -> None:
    request = {
        "presentation_key": "hh:134482249",
        "canonical_member_keys": ["hh:134482249"],
        "source": "hh",
        "external_id": "134482249",
        "columns": {},
    }
    rows = [
        {"№": 14, "Ссылка": "[beoma](https://samara.hh.ru/vacancy/134482249)", "CRM Key": ""},
        {"№": 15, "Ссылка": "[beoma copy](https://hh.ru/vacancy/134482249)", "CRM Key": ""},
    ]

    assert prepare_update(request, rows, WORKFLOW_V3) == {"found": False, "error_code": "crm_row_ambiguous"}


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


def test_application_crm_adapter_v2_falls_back_to_one_exact_hh_url_and_repairs_key() -> None:
    request = {
        "presentation_key": "hh:134482249",
        "canonical_member_keys": ["hh:134482249"],
        "source": "hh",
        "external_id": "134482249",
        "columns": {"Отклик": "Да", "Итог": None},
    }
    row = {"№": 13, "CRM Key": "", "Ссылка": "https://samara.hh.ru/vacancy/134482249?from=history", "О": "Не менять", "Итог": "Старый итог"}

    resolved = prepare_update(request, [row], WORKFLOW_V2)
    repaired = prepare_update(request, [{**row, "CRM Key": resolved["CRM Key"]}], WORKFLOW_V2)

    assert resolved["found"] is True
    assert resolved["№"] == 13
    assert resolved["match_strategy"] == "exact_hh_url_fallback"
    assert resolved["CRM Key"] == "hh:134482249"
    assert "О" not in resolved
    assert repaired["match_strategy"] == "business_key"


def test_application_crm_adapter_v2_exact_hh_url_supports_regional_query_and_encoded_back_url() -> None:
    request = {
        "presentation_key": "hh:134060247",
        "canonical_member_keys": ["hh:134060247"],
        "source": "hh",
        "external_id": "134060247",
        "columns": {},
    }
    urls = [
        "https://kazan.hh.ru/vacancy/134060247?hhtmFrom=vacancy_search_list",
        "https://samara.hh.ru/vpncheeck?backUrl=%2Fvacancy%2F134060247",
    ]

    for url in urls:
        resolved = prepare_update(request, [{"№": 1, "CRM Key": "", "Ссылка": url}], WORKFLOW_V2)
        assert resolved["found"] is True
        assert resolved["match_strategy"] == "exact_hh_url_fallback"


def test_application_crm_adapter_v2_returns_controlled_missing_or_ambiguous_results() -> None:
    request = {
        "presentation_key": "hh:134482249",
        "canonical_member_keys": ["hh:134482249"],
        "source": "hh",
        "external_id": "134482249",
        "columns": {},
    }
    duplicate_rows = [
        {"№": 1, "CRM Key": "", "Ссылка": "https://hh.ru/vacancy/134482249"},
        {"№": 2, "CRM Key": "", "Ссылка": "https://samara.hh.ru/vacancy/134482249"},
    ]

    assert prepare_update(request, [], WORKFLOW_V2) == {"found": False, "error_code": "crm_row_not_found"}
    assert prepare_update(request, duplicate_rows, WORKFLOW_V2) == {"found": False, "error_code": "crm_row_ambiguous"}
    assert prepare_update({**request, "source": "habr"}, [duplicate_rows[0]], WORKFLOW_V2) == {"found": False, "error_code": "crm_row_not_found"}
