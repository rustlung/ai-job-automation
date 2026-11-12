import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / "workflows" / "n8n" / "AI Job Automation — Daily Search Digest v17.json"


def load() -> dict:
    return json.loads(WORKFLOW.read_text(encoding="utf-8-sig"))


def test_v17_is_valid_and_preserves_c3_resume_without_collection_start() -> None:
    workflow = load()
    names = {node["name"] for node in workflow["nodes"]}
    ids = [node["id"] for node in workflow["nodes"]]

    assert workflow["name"] == "AI Job Automation — Daily Search Digest v17"
    assert len(ids) == len(set(ids))
    for source, connection in workflow["connections"].items():
        assert source in names
        for branch in connection.get("main", []):
            for target in branch:
                assert target["node"] in names
    recovery_nodes = {"Worker Recovery Needed?", "Wait 60s Before Worker Recovery", "Invoke Worker Resume", "Evaluate Worker Resume"}
    for source in recovery_nodes:
        targets = [target["node"] for branch in workflow["connections"][source]["main"] for target in branch]
        assert "Start Worker Pipeline" not in targets


def test_v17_routes_cancelled_worker_runs_without_post_processing() -> None:
    workflow = load()
    terminal_targets = [target["node"] for branch in workflow["connections"]["Worker Run Terminal?"]["main"] for target in branch]
    cancelled_targets = [target["node"] for branch in workflow["connections"]["Worker Run Cancelled?"]["main"] for target in branch]

    assert terminal_targets == ["Worker Run Cancelled?", "Wait 20s for Worker Run"]
    assert cancelled_targets[0] == "Cancelled Run Complete"
    assert "Prepare Success Email" not in cancelled_targets
    assert "Prepare Failure Email" not in cancelled_targets
