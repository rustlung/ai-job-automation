import json
from pathlib import Path


class HHAuthStateError(Exception):
    error_code = "hh_auth_state_error"


class HHAuthStateMissingError(HHAuthStateError):
    error_code = "hh_auth_state_missing"


class HHAuthStateInvalidError(HHAuthStateError):
    error_code = "hh_auth_state_invalid"


class HHAuthStateStore:
    def __init__(self, storage_state_path: str) -> None:
        self.storage_state_path = Path(storage_state_path)

    def validate_available(self) -> None:
        if not self.storage_state_path.exists() or not self.storage_state_path.is_file():
            raise HHAuthStateMissingError("HH auth state is missing")
        try:
            with self.storage_state_path.open("r", encoding="utf-8") as file:
                state = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise HHAuthStateInvalidError("HH auth state is invalid") from exc

        if not isinstance(state, dict):
            raise HHAuthStateInvalidError("HH auth state must be a JSON object")
        cookies = state.get("cookies")
        origins = state.get("origins")
        if not isinstance(cookies, list) or not isinstance(origins, list):
            raise HHAuthStateInvalidError("HH auth state has invalid shape")

    def is_configured(self) -> bool:
        self.validate_available()
        return True
