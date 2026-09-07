import json
import re
from pathlib import Path

from app.core.config import Settings
from app.services.hh_search_profiles import HHSearchProfileRegistry


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "workflows" / "n8n"
V9 = DIR / "AI Job Automation — Daily Search CRM Digest v9.json"
V10 = DIR / "AI Job Automation — Daily Search CRM Digest v10.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def targets(workflow: dict, name: str) -> list[str]:
    return [target["node"] for branch in workflow["connections"][name]["main"] for target in branch]


def parameter_text(item: dict) -> str:
    return json.dumps(item["parameters"], ensure_ascii=False)


def test_v9_baseline_is_preserved_and_v10_is_a_separate_export() -> None:
    v9 = load(V9)
    v10 = load(V10)

    assert v9["name"] == "AI Job Automation — Daily Search CRM Digest v9"
    assert v10["name"] == "AI Job Automation — Daily Search CRM Digest v10"
    assert V9.read_bytes() != V10.read_bytes()
    assert "Build Full Run Context" not in {item["name"] for item in v9["nodes"]}
    assert "input.headers" in node(v9, "Validate Webhook Secret")["parameters"]["jsCode"]
    assert "input.body || input" in node(v9, "Normalize Web Input")["parameters"]["jsCode"]


def test_v10_preserves_manual_web_and_replay_entries() -> None:
    workflow = load(V10)

    assert node(workflow, "Manual Trigger")["type"] == "n8n-nodes-base.manualTrigger"
    assert node(workflow, "Web UI Run Webhook")["type"] == "n8n-nodes-base.webhook"
    assert "Search Profiles — EDIT BEFORE RUN" in targets(workflow, "Use Existing Run?")
    assert "Build Run Context" in targets(workflow, "Use Existing Run?")
    assert "Build Full Run Context" not in targets(workflow, "Use Existing Run?")
    assert targets(workflow, "Build Run Context") == ["Get Current Run"]


def test_v10_builds_one_canonical_full_run_context_before_worker_start() -> None:
    workflow = load(V10)
    code = node(workflow, "Build Full Run Context")["parameters"]["jsCode"]

    for field in [
        "run_id",
        "trigger_source",
        "orchestration_started_at_ms",
        "config",
        "profile_selection",
        "profile_ids",
        "has_resume_profile",
        "selected_resume_profile_id",
        "worker_request",
    ]:
        assert field in code
    assert "orchestration_started_at_ms: Date.now()" in code
    assert "orchestration_started_at_ms" not in node(workflow, "Generate Run ID")["parameters"]["jsCode"]
    assert "orchestration_started_at_ms" not in node(workflow, "Build Web Worker Request")["parameters"]["jsCode"]

    assert targets(workflow, "Build Web Worker Request") == ["Build Full Run Context"]
    assert targets(workflow, "Restore Manual Run Context") == ["Build Full Run Context"]
    assert targets(workflow, "Build Full Run Context") == ["Mark Pipeline Run Running"]
    assert targets(workflow, "Mark Pipeline Run Running") == ["Restore Worker Start Context"]
    assert targets(workflow, "Restore Worker Start Context") == ["Start Worker Pipeline"]


def test_v10_polling_uses_only_canonical_full_run_context() -> None:
    workflow = load(V10)
    status = parameter_text(node(workflow, "Get Worker Run Status"))
    evaluate = node(workflow, "Evaluate Worker Run")["parameters"]["jsCode"]
    restore = node(workflow, "Restore Worker Start Context")["parameters"]["jsCode"]

    for text in [status, evaluate, restore]:
        assert "Build Full Run Context" in text
        assert "Generate Run ID" not in text
        assert "Build Web Worker Request" not in text
    for marker in ["running", "completed_with_errors", "result_available", "7200000", "consecutive_polling_errors"]:
        assert marker in evaluate
    assert "Wait 20s for Worker Run" in evaluate
    assert "Wait 20s for Worker Run" in targets(workflow, "Worker Run Terminal?")


def test_v10_shared_crm_nodes_use_replay_safe_context_and_keep_grouped_path() -> None:
    workflow = load(V10)

    for name in ["Read CRM Rows", "CRM Upsert by CRM Key", "CRM Upsert Legacy by URL"]:
        text = parameter_text(node(workflow, name))
        assert "$('Config')" not in text
        assert "Build Run Context" in text
    assert node(workflow, "Get Current Run")["parameters"]["url"].endswith("/grouped")
    assert "Профили поиска" in node(workflow, "Prepare CRM Rows")["parameters"]["jsCode"]


def test_v10_keeps_compute_preflight_async_polling_and_terminal_lifecycle() -> None:
    workflow = load(V10)

    assert node(workflow, "Preflight Compute")["parameters"]["options"]["timeout"] >= 120000
    assert node(workflow, "Start Worker Pipeline")["parameters"]["url"].endswith("/hh/pipeline-runs")
    assert node(workflow, "Start Worker Pipeline")["parameters"]["options"]["timeout"] <= 15000
    assert "Mark Pipeline Run Completed" in targets(workflow, "Worker Result Available?")
    assert "Mark Pipeline Run Failed" in targets(workflow, "Worker Result Available?")
    assert "Evaluate Worker Run" in parameter_text(node(workflow, "Mark Pipeline Run Completed"))


def test_v10_selectable_profile_ids_match_worker_registry() -> None:
    workflow = load(V10)
    code = node(workflow, "Build Selected Profile IDs")["parameters"]["jsCode"]
    match = re.search(r"const allowedProfileIds = \[(.*?)\];", code, flags=re.DOTALL)

    assert match is not None
    workflow_ids = re.findall(r"'([^']+)'", match.group(1))
    registry_ids = [
        profile.id
        for profile in HHSearchProfileRegistry(Settings()).list_profiles()
        if profile.user_selectable
    ]
    assert workflow_ids == registry_ids
    assert "selected === true && !allowedProfileIds.includes(profileId)" in code
    assert "No search profiles selected" in code


def test_v10_canvas_positions_are_unique_and_convergence_is_readable() -> None:
    workflow = load(V10)
    positions = [tuple(item["position"]) for item in workflow["nodes"]]

    assert len(positions) == len(set(positions))
    assert node(workflow, "Build Web Worker Request")["position"][0] < node(workflow, "Build Full Run Context")["position"][0]
    assert node(workflow, "Restore Manual Run Context")["position"][0] < node(workflow, "Build Full Run Context")["position"][0]
    assert node(workflow, "Build Full Run Context")["position"][0] < node(workflow, "Mark Pipeline Run Running")["position"][0]
    assert node(workflow, "Wait 20s for Worker Run")["position"][1] > node(workflow, "Start Worker Pipeline")["position"][1]
