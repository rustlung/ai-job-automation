import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "workflows" / "n8n"
V7 = DIR / "AI Job Automation — Daily Search CRM Digest v7.json"
V8 = DIR / "AI Job Automation — Daily Search CRM Digest v8.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def crm_rows(workflow: dict, analyses: list[dict]) -> list[dict]:
    code = node(workflow, "Prepare CRM Rows")["parameters"]["jsCode"]
    harness = f"""
const code = {json.dumps(code)};
const values = {{
  'Get Current Run': {{ run_id: 'run-1', analyses: {json.dumps(analyses)} }},
  'Build Run Context': {{ config: {{ crm_sync_priorities: ['P1', 'P2', 'ALT'] }} }}
}};
const getItems = (name) => [{{ json: values[name] || {{}} }}];
const execute = new Function('$', '$items', '$input', code);
console.log(JSON.stringify(execute((name) => ({{ all: () => getItems(name) }}), (name) => getItems(name), {{ all: () => [] }})));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return [item["json"] for item in json.loads(result.stdout)]


def analysis(*, presentation_key: str | None, profile_ids: list[str] | None = None) -> dict:
    item = {
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
    if presentation_key is not None:
        item["presentation_key"] = presentation_key
    return item


def test_v7_is_preserved_and_v8_uses_grouped_run_endpoint() -> None:
    v7 = load(V7)
    v8 = load(V8)

    assert v7["name"] == "AI Job Automation — Daily Search CRM Digest v7"
    assert v8["name"] == "AI Job Automation — Daily Search CRM Digest v8"
    assert node(v7, "Get Current Run")["parameters"]["url"].endswith("/{{ $json.run_id }}")
    assert node(v8, "Get Current Run")["parameters"]["url"].endswith("/{{ $json.run_id }}/grouped")


def test_v8_uses_business_key_with_source_identity_fallback_and_keeps_profile_column() -> None:
    workflow = load(V8)
    grouped = crm_rows(workflow, [analysis(presentation_key="business:abc", profile_ids=["vibecoding_keywords", "ai_automation_keywords"])])[0]
    fallback = crm_rows(workflow, [analysis(presentation_key=None)])[0]

    assert grouped["CRM Key"] == "business:abc"
    assert grouped["Профили поиска"] == "vibecoding_keywords, ai_automation_keywords"
    assert fallback["CRM Key"] == "hh:1"


def test_v8_preserves_v7_topology_and_canvas_layout() -> None:
    v7 = load(V7)
    v8 = load(V8)

    assert v8["connections"] == v7["connections"]
    assert [(item["name"], item["position"]) for item in v8["nodes"]] == [
        (item["name"], item["position"]) for item in v7["nodes"]
    ]
    positions = [tuple(item["position"]) for item in v8["nodes"]]
    assert len(positions) == len(set(positions))
