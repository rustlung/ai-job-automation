import json

import pytest

from app.services.hh_auth_state import HHAuthStateInvalidError, HHAuthStateMissingError, HHAuthStateStore


def write_state(path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_auth_state_store_accepts_basic_playwright_storage_state(tmp_path) -> None:
    path = tmp_path / "hh-storage-state.json"
    write_state(path, {"cookies": [], "origins": []})

    HHAuthStateStore(path).validate_available()


def test_auth_state_store_reports_missing_file(tmp_path) -> None:
    with pytest.raises(HHAuthStateMissingError) as exc_info:
        HHAuthStateStore(tmp_path / "missing.json").validate_available()

    assert exc_info.value.error_code == "hh_auth_state_missing"


@pytest.mark.parametrize("payload", [{}, {"cookies": []}, {"origins": []}, []])
def test_auth_state_store_rejects_invalid_shape(tmp_path, payload) -> None:
    path = tmp_path / "hh-storage-state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HHAuthStateInvalidError) as exc_info:
        HHAuthStateStore(path).validate_available()

    assert exc_info.value.error_code == "hh_auth_state_invalid"


def test_auth_state_store_rejects_invalid_json(tmp_path) -> None:
    path = tmp_path / "hh-storage-state.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(HHAuthStateInvalidError):
        HHAuthStateStore(path).validate_available()
