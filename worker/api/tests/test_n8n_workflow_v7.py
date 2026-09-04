import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "workflows" / "n8n"
V6 = DIR / "AI Job Automation — Daily Search CRM Digest v6.json"
V7 = DIR / "AI Job Automation — Daily Search CRM Digest v7.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def crm_rows(workflow: dict, analyses: list[dict]) -> list[dict]:
    code = node(workflow, "Prepare CRM Rows")["parameters"]["jsCode"]
    harness = f"""
const code = {json.dumps(code)};
const run = {{ run_id: 'run-1', analyses: {json.dumps(analyses)} }};
const context = {{ config: {{ crm_sync_priorities: ['P1', 'P2', 'ALT'] }} }};
const values = {{ 'Get Current Run': run, 'Build Run Context': context }};
const getItems = (name) => [{{ json: values[name] || {{}} }}];
const execute = new Function('$', '$items', '$input', code);
const result = execute(
  (name) => ({{ all: () => getItems(name) }}),
  (name) => getItems(name),
  {{ all: () => [] }},
);
console.log(JSON.stringify(result));
"""
    completed = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return [item["json"] for item in json.loads(completed.stdout)]


def analysis(profile_ids: list[str] | None) -> dict:
    return {
        "priority": "P1",
        "run_id": "run-1",
        "created_at": "2026-09-04T00:00:00Z",
        "final_score": 80,
        "vacancy_snapshot": {
            "source": "hh",
            "external_id": "1",
            "title": "Python Developer",
            "company": "Test",
            "url": "https://hh.ru/vacancy/1",
        },
        "provenance": {} if profile_ids is None else {"profile_ids": profile_ids},
    }


def test_v6_is_preserved_and_v7_is_a_separate_versioned_export() -> None:
    assert load(V6)["name"] == "AI Job Automation — Daily Search CRM Digest v6"
    assert load(V7)["name"] == "AI Job Automation — Daily Search CRM Digest v7"
    assert V6 != V7


def test_v7_crm_mapping_appends_search_profile_provenance_without_changing_existing_fields() -> None:
    v6 = load(V6)
    v7 = load(V7)

    for upsert_name in ["CRM Upsert by CRM Key", "CRM Upsert Legacy by URL"]:
        before = node(v6, upsert_name)["parameters"]["columns"]["value"]
        after = node(v7, upsert_name)["parameters"]["columns"]["value"]
        assert list(after)[:-1] == list(before)
        assert list(after)[-1] == "Профили поиска"
        assert after["Профили поиска"] == "={{ $json['Профили поиска'] }}"

    schema = node(v7, "CRM Upsert by CRM Key")["parameters"]["columns"]["schema"]
    assert schema[-1]["id"] == "Профили поиска"
    assert schema[-1]["displayName"] == "Профили поиска"


def test_v7_formats_one_many_and_missing_profile_provenance() -> None:
    workflow = load(V7)

    assert crm_rows(workflow, [analysis(["vibecoding_keywords"])])[0]["Профили поиска"] == "vibecoding_keywords"
    assert crm_rows(workflow, [analysis(["vibecoding_keywords", "ai_automation_keywords"])])[0]["Профили поиска"] == (
        "vibecoding_keywords, ai_automation_keywords"
    )
    assert crm_rows(workflow, [analysis(None)])[0]["Профили поиска"] == ""
    assert crm_rows(workflow, [analysis([])])[0]["Профили поиска"] == ""


def test_v7_preserves_provenance_order_and_deduplicates_repeat_ids() -> None:
    workflow = load(V7)

    row = crm_rows(workflow, [analysis(["vibecoding_keywords", "ai_automation_keywords", "vibecoding_keywords"])])[0]

    assert row["Профили поиска"] == "vibecoding_keywords, ai_automation_keywords"


def test_v7_preserves_v6_topology_and_canvas_layout() -> None:
    v6 = load(V6)
    v7 = load(V7)

    assert v7["connections"] == v6["connections"]
    assert [(item["name"], item["position"]) for item in v7["nodes"]] == [
        (item["name"], item["position"]) for item in v6["nodes"]
    ]
    positions = [tuple(item["position"]) for item in v7["nodes"]]
    assert len(positions) == len(set(positions))
