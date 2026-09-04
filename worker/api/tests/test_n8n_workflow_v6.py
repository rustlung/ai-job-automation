import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "workflows" / "n8n"
V5 = DIR / "AI Job Automation — Daily Search CRM Digest v5.json"
V6 = DIR / "AI Job Automation — Daily Search CRM Digest v6.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def links(workflow: dict, name: str, output: int = 0) -> list[str]:
    return [item["node"] for item in workflow["connections"][name]["main"][output]]


def test_v5_is_preserved_and_v6_is_versioned() -> None:
    assert load(V5)["name"] == "AI Job Automation — Daily Search CRM Digest v5"
    assert load(V6)["name"] == "AI Job Automation — Daily Search CRM Digest v6"


def test_v6_async_polling_contract() -> None:
    workflow = load(V6)
    start, wait, status = (node(workflow, name) for name in ["Start Worker Pipeline", "Wait 20s for Worker Run", "Get Worker Run Status"])
    assert start["parameters"]["url"].endswith("/hh/pipeline-runs")
    assert start["parameters"]["options"]["timeout"] <= 15000
    assert wait["parameters"]["amount"] == 20 and wait["parameters"].get("unit", "seconds") == "seconds"
    assert status["parameters"]["options"]["timeout"] <= 15000
    assert links(workflow, "Start Worker Pipeline") == ["Wait 20s for Worker Run"]
    assert links(workflow, "Wait 20s for Worker Run") == ["Get Worker Run Status"]
    assert links(workflow, "Get Worker Run Status") == ["Evaluate Worker Run"]
    assert links(workflow, "Worker Run Terminal?", 1) == ["Wait 20s for Worker Run"]


def test_v6_terminal_gate_protects_crm_and_handles_retries() -> None:
    workflow = load(V6)
    code = node(workflow, "Evaluate Worker Run")["parameters"]["jsCode"]
    for expected in ["result_available", "consecutive_polling_errors", ">= 3", "7200000", "worker_run_not_found"]:
        assert expected in code
    assert links(workflow, "Worker Run Terminal?", 0) == ["Worker Result Available?"]
    assert links(workflow, "Worker Result Available?", 0) == ["Build Run Context"]
    assert links(workflow, "Worker Result Available?", 1) == ["Prepare Failure Email"]


def test_v6_canvas_positions_are_unique_and_separated() -> None:
    workflow = load(V6)
    positions = [tuple(item["position"]) for item in workflow["nodes"]]
    by_name = {item["name"]: tuple(item["position"]) for item in workflow["nodes"]}
    assert len(positions) == len(set(positions))
    assert by_name["Wait 20s for Worker Run"][1] > by_name["Start Worker Pipeline"][1]
    assert by_name["Prepare Failure Email"][1] > by_name["Worker Result Available?"][1]
