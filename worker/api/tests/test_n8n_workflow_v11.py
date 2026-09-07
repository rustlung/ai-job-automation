import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / "workflows" / "n8n"
V10 = WORKFLOWS / "AI Job Automation — Daily Search CRM Digest v10.json"
V11 = WORKFLOWS / "AI Job Automation — Daily Search CRM Digest v11.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def test_v10_is_preserved_and_v11_removes_only_manual_sheet_fallback() -> None:
    v10 = load(V10)
    v11 = load(V11)
    manual_config = node(v11, "Config")["parameters"]["jsonOutput"]

    assert v10["name"] == "AI Job Automation — Daily Search CRM Digest v10"
    assert v11["name"] == "AI Job Automation — Daily Search CRM Digest v11"
    assert V10.read_bytes() != V11.read_bytes()
    assert "sheet_name: $env.GOOGLE_SHEETS_CRM_SHEET_NAME," in manual_config
    assert "Вакансии" + "_TEST" not in manual_config
    assert "GOOGLE_SHEETS_CRM_SHEET_NAME ||" not in manual_config


def test_v11_keeps_canonical_context_and_readable_canvas() -> None:
    workflow = load(V11)
    positions = [tuple(item["position"]) for item in workflow["nodes"]]

    assert "Build Full Run Context" in {item["name"] for item in workflow["nodes"]}
    assert len(positions) == len(set(positions))
