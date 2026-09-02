import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = REPOSITORY_ROOT / "workflows" / "n8n"
V4_PATH = WORKFLOW_DIR / "AI Job Automation — Daily Search CRM Digest v4.json"
V5_PATH = WORKFLOW_DIR / "AI Job Automation — Daily Search CRM Digest v5.json"


def load_workflow(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def node_by_name(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def connected_nodes(workflow: dict, source: str, output_index: int = 0) -> list[str]:
    return [item["node"] for item in workflow["connections"][source]["main"][output_index]]


def test_v4_is_preserved_and_v5_is_a_new_versioned_export() -> None:
    v4 = load_workflow(V4_PATH)
    v5 = load_workflow(V5_PATH)

    assert v4["name"] == "AI Job Automation — Daily Search CRM Digest v4"
    assert v5["name"] == "AI Job Automation — Daily Search CRM Digest v5"
    assert V4_PATH != V5_PATH


def test_v5_compute_preflight_is_inserted_before_conditional_hh_preflight() -> None:
    workflow = load_workflow(V5_PATH)
    compute = node_by_name(workflow, "Preflight Compute")

    assert compute["parameters"]["method"] == "POST"
    assert compute["parameters"]["url"].endswith("/health/ollama/compute")
    assert compute["parameters"]["options"]["timeout"] >= 120000
    assert compute["continueOnFail"] is True
    assert connected_nodes(workflow, "Preflight Ollama") == ["Preflight Compute"]
    assert connected_nodes(workflow, "Preflight Compute") == ["Resume Profiles Selected?"]


def test_v5_validate_preflight_requires_gpu_compute_before_worker_pipeline() -> None:
    workflow = load_workflow(V5_PATH)
    validate_code = node_by_name(workflow, "Validate Preflight")["parameters"]["jsCode"]

    for required_check in [
        "compute.status !== 'ok'",
        "compute.model_loaded !== true",
        "compute.compute_backend !== 'gpu'",
        "compute.gpu_acceptable !== true",
    ]:
        assert required_check in validate_code

    assert connected_nodes(workflow, "Preflight OK?", 0) == ["Generate Run ID"]
    assert connected_nodes(workflow, "Preflight OK?", 1) == ["Stop Preflight Failed"]
    assert connected_nodes(workflow, "Generate Run ID") == ["HTTP Worker Pipeline"]


def test_v5_canvas_layout_has_unique_positions_and_separated_error_branches() -> None:
    workflow = load_workflow(V5_PATH)
    positions = [tuple(node["position"]) for node in workflow["nodes"]]
    by_name = {node["name"]: tuple(node["position"]) for node in workflow["nodes"]}

    assert len(positions) == len(set(positions))
    assert by_name["Preflight Ollama"][0] < by_name["Preflight Compute"][0] < by_name["Resume Profiles Selected?"][0]
    assert by_name["Preflight Compute"][1] == by_name["Preflight Ollama"][1]
    assert by_name["Stop Preflight Failed"][1] > by_name["Preflight OK?"][1]
    assert by_name["Prepare Failure Email"][1] > by_name["Pipeline OK?"][1]
