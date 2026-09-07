import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / "workflows" / "n8n"
V11 = WORKFLOWS / "AI Job Automation — Daily Search CRM Digest v11.json"
V12 = WORKFLOWS / "AI Job Automation — Daily Search CRM Digest v12.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def node(workflow: dict, name: str) -> dict:
    return next(item for item in workflow["nodes"] if item["name"] == name)


def crm_rows(workflow: dict, analyses: list[dict], sheet_rows: list[dict]) -> list[dict]:
    code = node(workflow, "Prepare CRM Rows")["parameters"]["jsCode"]
    harness = f"""
const code = {json.dumps(code)};
const values = {{
  'Get Current Run': {{ run_id: 'run-1', analyses: {json.dumps(analyses)} }},
  'Build Run Context': {{ config: {{ crm_sync_priorities: ['P1', 'P2', 'ALT'] }} }}
}};
const getItems = (name) => [{{ json: values[name] || {{}} }}];
const execute = new Function('$', '$items', '$input', code);
console.log(JSON.stringify(execute(
  (name) => ({{ all: () => getItems(name) }}),
  (name) => getItems(name),
  {{ all: () => {json.dumps([{'json': row} for row in sheet_rows])} }},
)));
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True, encoding="utf-8", check=True)
    return [item["json"] for item in json.loads(result.stdout)]


def analysis(
    *,
    external_id: str,
    presentation_key: str | None = None,
    business_fingerprint: str | None = None,
    canonical_member_keys: list[str] | None = None,
) -> dict:
    return {
        "priority": "P1",
        "run_id": "run-1",
        "created_at": "2026-09-08T00:00:00Z",
        "final_score": 80,
        "presentation_key": presentation_key,
        "business_fingerprint": business_fingerprint,
        "canonical_member_keys": canonical_member_keys or [],
        "vacancy_snapshot": {
            "source": "hh",
            "external_id": external_id,
            "title": "Python Developer",
            "company": "Test",
            "url": f"https://samara.hh.ru/vacancy/{external_id}",
        },
        "provenance": {"profile_ids": ["ai_automation_keywords"]},
    }


def test_v11_is_preserved_and_v12_is_a_separate_versioned_export() -> None:
    v11 = load(V11)
    v12 = load(V12)

    assert v11["name"] == "AI Job Automation — Daily Search CRM Digest v11"
    assert v12["name"] == "AI Job Automation — Daily Search CRM Digest v12"
    assert V11.read_bytes() != V12.read_bytes()


def test_v12_migrates_existing_groupable_legacy_key_without_appending() -> None:
    workflow = load(V12)
    rows = crm_rows(
        workflow,
        [
            analysis(
                external_id="134829827",
                presentation_key="business:abc",
                business_fingerprint="abc",
                canonical_member_keys=["hh:134829827"],
            )
        ],
        [{"№": 7, "CRM Key": "hh:134829827", "Ссылка": "https://hh.ru/vacancy/134829827"}],
    )

    assert rows[0]["CRM Key"] == "business:abc"
    assert rows[0]["№"] == 7
    assert rows[0]["crm_action"] == "updated"
    assert rows[0]["match_strategy"] == "legacy_crm_key_fallback"


def test_v12_business_key_wins_over_legacy_duplicate_and_new_group_is_not_counted() -> None:
    workflow = load(V12)
    grouped = analysis(
        external_id="300",
        presentation_key="business:abc",
        business_fingerprint="abc",
        canonical_member_keys=["hh:200", "hh:300"],
    )
    business_wins = crm_rows(
        workflow,
        [grouped],
        [{"№": 1, "CRM Key": "business:abc"}, {"№": 2, "CRM Key": "hh:200"}],
    )[0]
    new_group = crm_rows(workflow, [grouped], [])[0]

    assert business_wins["№"] == 1
    assert business_wins["match_strategy"] == "crm_key"
    assert new_group["crm_action"] == "new"
    assert new_group["match_strategy"] == "new"


def test_v12_preserves_non_groupable_canonical_matching_and_migrates_regional_member() -> None:
    workflow = load(V12)
    non_groupable = crm_rows(workflow, [analysis(external_id="1")], [{"№": 3, "CRM Key": "hh:1"}])[0]
    regional = crm_rows(
        workflow,
        [
            analysis(
                external_id="300",
                presentation_key="business:regional",
                business_fingerprint="regional",
                canonical_member_keys=["hh:100", "hh:200", "hh:300"],
            )
        ],
        [{"№": 9, "CRM Key": "hh:200", "Ссылка": "https://kazan.hh.ru/vacancy/200"}],
    )[0]

    assert non_groupable["CRM Key"] == "hh:1"
    assert non_groupable["match_strategy"] == "crm_key"
    assert regional["CRM Key"] == "business:regional"
    assert regional["№"] == 9
    assert regional["match_strategy"] == "legacy_crm_key_fallback"


def test_v12_legacy_match_counter_is_zero_or_counts_each_fallback_once() -> None:
    workflow = load(V12)
    no_matches = crm_rows(
        workflow,
        [analysis(external_id="1", presentation_key="business:no-match", business_fingerprint="no-match", canonical_member_keys=["hh:1"])],
        [],
    )
    multiple_matches = crm_rows(
        workflow,
        [
            analysis(external_id="10", presentation_key="business:one", business_fingerprint="one", canonical_member_keys=["hh:10"]),
            analysis(external_id="20", presentation_key="business:two", business_fingerprint="two", canonical_member_keys=["hh:20"]),
        ],
        [{"№": 1, "CRM Key": "hh:10"}, {"№": 2, "CRM Key": "hh:20"}],
    )

    assert sum(row["match_strategy"] == "legacy_crm_key_fallback" for row in no_matches) == 0
    assert sum(row["match_strategy"] == "legacy_crm_key_fallback" for row in multiple_matches) == 2


def test_v12_records_only_legacy_crm_key_fallbacks_in_existing_stats_path() -> None:
    workflow = load(V12)
    code = node(workflow, "Prepare CRM Rows")["parameters"]["jsCode"]
    stats = node(workflow, "Record Legacy CRM Key Migration Stats")

    assert "Temporary compatibility path" in code
    assert "legacy_crm_key_fallback" in code
    assert stats["parameters"]["jsonBody"].count("legacy_crm_key_fallback") == 1
    assert "legacy_crm_key_matches" in stats["parameters"]["jsonBody"]
    assert "status" not in stats["parameters"]["jsonBody"]
    assert stats["parameters"]["url"].endswith("/internal/pipeline-runs/{{ $('Build Run Context').first().json.run_id }}")


def test_v12_routes_temporary_fallback_to_row_number_update_and_keeps_canvas_readable() -> None:
    workflow = load(V12)
    positions = [tuple(item["position"]) for item in workflow["nodes"]]
    fallback = node(workflow, "CRM Upsert Legacy CRM Key Fallback")

    assert fallback["parameters"]["columns"]["matchingColumns"] == ["№"]
    assert workflow["connections"]["Legacy CRM Key Fallback?"]["main"][0][0]["node"] == "CRM Upsert Legacy CRM Key Fallback"
    assert workflow["connections"]["Legacy CRM Key Fallback?"]["main"][1][0]["node"] == "Legacy URL Match?"
    assert workflow["connections"]["CRM Upsert Legacy CRM Key Fallback"]["main"][0][0]["node"] == (
        "Record Legacy CRM Key Migration Stats"
    )
    assert len(positions) == len(set(positions))
