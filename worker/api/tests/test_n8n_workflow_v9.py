import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "workflows" / "n8n"
V8 = DIR / "AI Job Automation — Daily Search CRM Digest v8.json"
V9 = DIR / "AI Job Automation — Daily Search CRM Digest v9.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def targets(workflow: dict, name: str) -> list[str]:
    return [target["node"] for branch in workflow["connections"][name]["main"] for target in branch]


def test_v8_is_preserved_and_v9_is_a_separate_versioned_export() -> None:
    v8 = load(V8)
    v9 = load(V9)

    assert v8["name"] == "AI Job Automation — Daily Search CRM Digest v8"
    assert v9["name"] == "AI Job Automation — Daily Search CRM Digest v9"
    assert V8.read_bytes() != V9.read_bytes()


def test_v9_preserves_manual_replay_and_adds_webhook_full_run_entry() -> None:
    workflow = load(V9)

    assert node(workflow, "Manual Trigger")["type"] == "n8n-nodes-base.manualTrigger"
    assert node(workflow, "Web UI Run Webhook")["type"] == "n8n-nodes-base.webhook"
    assert "Build Run Context" in targets(workflow, "Use Existing Run?")
    assert "Search Profiles — EDIT BEFORE RUN" in targets(workflow, "Use Existing Run?")
    assert targets(workflow, "Build Run Context") == ["Get Current Run"]
    assert "Generate Run ID" not in targets(workflow, "Use Existing Run?")


def test_v9_full_run_entries_converge_before_profile_selection_build() -> None:
    workflow = load(V9)

    assert targets(workflow, "Normalize Manual Input") == ["Build Selected Profile IDs"]
    assert targets(workflow, "Normalize Web Input") == ["Build Selected Profile IDs"]
    build_code = node(workflow, "Build Selected Profile IDs")["parameters"]["jsCode"]
    assert "input.profile_selection" in build_code
    assert "$('Config')" not in build_code
    assert "No search profiles selected" in build_code


def test_v9_web_path_reuses_orchestrator_run_id_and_manual_path_registers_its_own() -> None:
    workflow = load(V9)

    web_code = node(workflow, "Normalize Web Input")["parameters"]["jsCode"]
    assert "run_id: String(request.run_id)" in web_code
    assert "trigger_source: 'web_ui'" in web_code
    assert "Web Run ID Provided?" in targets(workflow, "Preflight OK?")
    assert "Build Web Worker Request" in targets(workflow, "Web Run ID Provided?")
    assert "Generate Run ID" in targets(workflow, "Web Run ID Provided?")
    assert "Register Manual Pipeline Run" in targets(workflow, "Generate Run ID")
    assert "/internal/pipeline-runs" in node(workflow, "Register Manual Pipeline Run")["parameters"]["url"]


def test_v9_preserves_async_worker_compute_preflight_and_grouped_crm_path() -> None:
    workflow = load(V9)

    assert node(workflow, "Start Worker Pipeline")["parameters"]["url"].endswith("/hh/pipeline-runs")
    assert node(workflow, "Start Worker Pipeline")["parameters"]["options"]["timeout"] <= 15000
    assert node(workflow, "Preflight Compute")["parameters"]["options"]["timeout"] >= 120000
    assert node(workflow, "Get Current Run")["parameters"]["url"].endswith("/grouped")
    assert "Профили поиска" in node(workflow, "Prepare CRM Rows")["parameters"]["jsCode"]
    assert "Mark Pipeline Run Completed" in targets(workflow, "Worker Result Available?")
    assert "Mark Pipeline Run Failed" in targets(workflow, "Worker Result Available?")


def test_v9_canvas_positions_are_unique_and_entry_modes_are_separated() -> None:
    workflow = load(V9)
    positions = [tuple(item["position"]) for item in workflow["nodes"]]

    assert len(positions) == len(set(positions))
    assert node(workflow, "Web UI Run Webhook")["position"][1] < node(workflow, "Manual Trigger")["position"][1]
    assert node(workflow, "Normalize Manual Input")["position"][0] < node(workflow, "Build Selected Profile IDs")["position"][0]
    assert node(workflow, "Normalize Web Input")["position"][0] < node(workflow, "Build Selected Profile IDs")["position"][0]
