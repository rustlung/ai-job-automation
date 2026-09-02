import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = REPOSITORY_ROOT / "workflows" / "n8n"
V3_PATH = WORKFLOW_DIR / "AI Job Automation — Daily Search CRM Digest v3.json"
V4_PATH = WORKFLOW_DIR / "AI Job Automation — Daily Search CRM Digest v4.json"


def load_workflow(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def node_by_name(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def connected_nodes(workflow: dict, source: str, output_index: int = 0) -> list[str]:
    return [item["node"] for item in workflow["connections"][source]["main"][output_index]]


def test_v3_production_baseline_is_preserved_and_v4_is_a_new_export() -> None:
    v3 = load_workflow(V3_PATH)
    v4 = load_workflow(V4_PATH)

    assert v3["name"] == "AI Job Automation — Daily Search CRM Digest v3"
    assert v4["name"] == "AI Job Automation — Daily Search CRM Digest v4"
    assert V3_PATH != V4_PATH


def test_v4_profile_selector_builds_worker_profile_ids_and_stops_empty_selection() -> None:
    workflow = load_workflow(V4_PATH)
    selector = node_by_name(workflow, "Search Profiles — EDIT BEFORE RUN")
    selector_config = selector["parameters"]["jsonOutput"]
    builder_code = node_by_name(workflow, "Build Selected Profile IDs")["parameters"]["jsCode"]
    generate_code = node_by_name(workflow, "Generate Run ID")["parameters"]["jsCode"]

    for profile_id in [
        "ai_resume_recommendations",
        "python_resume_recommendations",
        "ai_automation_keywords",
        "vibecoding_keywords",
        "python_backend_keywords",
        "python_automation_keywords",
    ]:
        assert profile_id in selector_config
        assert profile_id in builder_code

    assert "No search profiles selected" in builder_code
    assert "profile_ids: profileIds" in builder_code
    assert "profile_ids: config.profile_ids" in generate_code


def test_v4_skips_authenticated_preflight_for_keyword_only_selection() -> None:
    workflow = load_workflow(V4_PATH)
    resume_gate = node_by_name(workflow, "Resume Profiles Selected?")
    validate_code = node_by_name(workflow, "Validate Preflight")["parameters"]["jsCode"]

    assert "has_resume_profile" in resume_gate["parameters"]["conditions"]["conditions"][0]["leftValue"]
    assert connected_nodes(workflow, "Preflight Ollama") == ["Resume Profiles Selected?"]
    assert connected_nodes(workflow, "Resume Profiles Selected?", 0) == ["Preflight HH Auth"]
    assert connected_nodes(workflow, "Resume Profiles Selected?", 1) == ["Skip HH Auth Preflight (keyword-only)"]
    assert connected_nodes(workflow, "Skip HH Auth Preflight (keyword-only)") == ["Validate Preflight"]
    assert "selection.has_resume_profile && hasError(hhAuth)" in validate_code
    assert "selection.has_resume_profile && hasError(hhSession)" in validate_code


def test_v4_new_run_flows_through_profile_selection_before_preflight() -> None:
    workflow = load_workflow(V4_PATH)

    assert connected_nodes(workflow, "Use Existing Run?", 1) == ["Search Profiles — EDIT BEFORE RUN"]
    assert connected_nodes(workflow, "Search Profiles — EDIT BEFORE RUN") == ["Build Selected Profile IDs"]
    assert connected_nodes(workflow, "Build Selected Profile IDs") == ["Preflight Orchestrator"]
