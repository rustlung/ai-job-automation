import importlib.util
import json
from pathlib import Path

import pytest


def load_hh_auth_setup_module():
    script_path = Path(__file__).resolve().parents[2] / "tools" / "hh_auth_setup.py"
    spec = importlib.util.spec_from_file_location("hh_auth_setup", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self, payload: dict | str) -> None:
        self.payload = payload

    def storage_state(self, path: str) -> None:
        if isinstance(self.payload, str):
            Path(path).write_text(self.payload, encoding="utf-8")
        else:
            Path(path).write_text(json.dumps(self.payload), encoding="utf-8")


def test_validate_hh_url_accepts_hh_https_url() -> None:
    module = load_hh_auth_setup_module()

    assert module.validate_hh_url("https://hh.ru/") == "https://hh.ru/"
    assert module.validate_hh_url("https://samara.hh.ru/search/vacancy") == "https://samara.hh.ru/search/vacancy"


@pytest.mark.parametrize("url", ["http://hh.ru/", "https://example.com/", "not-a-url"])
def test_validate_hh_url_rejects_unsafe_url(url: str) -> None:
    module = load_hh_auth_setup_module()

    with pytest.raises(module.HHAuthSetupError):
        module.validate_hh_url(url)


def test_atomic_write_storage_state_replaces_file_only_after_valid_json(tmp_path) -> None:
    module = load_hh_auth_setup_module()
    output_path = tmp_path / "hh-storage-state.json"
    output_path.write_text("old", encoding="utf-8")

    module.atomic_write_storage_state(FakeContext({"cookies": [], "origins": []}), output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == {"cookies": [], "origins": []}
    assert not (tmp_path / ".hh-storage-state.json.tmp").exists()


def test_atomic_write_storage_state_keeps_existing_file_when_new_state_is_invalid(tmp_path) -> None:
    module = load_hh_auth_setup_module()
    output_path = tmp_path / "hh-storage-state.json"
    output_path.write_text("old", encoding="utf-8")

    with pytest.raises(module.HHAuthSetupError):
        module.atomic_write_storage_state(FakeContext({"cookies": []}), output_path)

    assert output_path.read_text(encoding="utf-8") == "old"
    assert not (tmp_path / ".hh-storage-state.json.tmp").exists()


def test_default_output_path_points_to_worker_secrets() -> None:
    module = load_hh_auth_setup_module()

    output_path = module.default_output_path()

    assert output_path.parts[-2:] == ("secrets", "hh-storage-state.json")
    assert output_path.parts[-3] == "worker"
