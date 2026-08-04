import argparse
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

DEFAULT_START_URL = "https://hh.ru/"
DEFAULT_OUTPUT_FILENAME = "hh-storage-state.json"
AUTH_MARKER_SELECTORS = (
    '[data-qa="mainmenu_applicantProfile"]',
    '[data-qa="mainmenu_myResumes"]',
    '[data-qa="mainmenu_my_hh"]',
    '[data-qa="mainmenu_userName"]',
    'a[href*="/applicant/resumes"]',
    'a[href*="/applicant/resume"]',
)

logger = logging.getLogger(__name__)


class HHAuthSetupError(Exception):
    pass


def worker_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_output_path() -> Path:
    return worker_root() / "secrets" / DEFAULT_OUTPUT_FILENAME


def resolve_output_path(value: str | None) -> Path:
    if value is None:
        return default_output_path()
    return Path(value).expanduser().resolve()


def validate_hh_url(url: str) -> str:
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    if parts.scheme != "https" or (hostname != "hh.ru" and not hostname.endswith(".hh.ru")):
        raise HHAuthSetupError("Start URL must be an HTTPS hh.ru URL")
    return url


def safe_url_parts(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.hostname or "", parts.path or "/"


def validate_storage_state_shape(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HHAuthSetupError("Storage state is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HHAuthSetupError("Storage state must be a JSON object")
    if not isinstance(payload.get("cookies"), list):
        raise HHAuthSetupError("Storage state must contain a cookies list")
    if not isinstance(payload.get("origins"), list):
        raise HHAuthSetupError("Storage state must contain an origins list")


def atomic_write_storage_state(context: object, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        context.storage_state(path=str(temporary_path))
        validate_storage_state_shape(temporary_path)
        os.replace(temporary_path, output_path)
        try:
            output_path.chmod(0o600)
        except OSError:
            logger.debug("hh_auth_setup_chmod_skipped path=%s", output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def authenticated_marker_detected(page: object) -> bool:
    for selector in AUTH_MARKER_SELECTORS:
        try:
            if page.locator(selector).count() > 0:
                return True
        except PlaywrightError:
            continue
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create HH Playwright storage state after manual browser login.")
    parser.add_argument("--output", default=None, help="Output storage state path.")
    parser.add_argument("--start-url", default=DEFAULT_START_URL, help="HTTPS hh.ru URL to open for login.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    playwright_runtime = None
    browser = None
    context = None
    page = None
    try:
        args = parse_args(argv)
        output_path = resolve_output_path(args.output)
        start_url = validate_hh_url(args.start_url)
        hostname, path = safe_url_parts(start_url)
        logger.info("hh_auth_setup_started hostname=%s path=%s output=%s", hostname, path, output_path)
        playwright_runtime = sync_playwright().start()
        browser = playwright_runtime.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(start_url, wait_until="domcontentloaded")
        input("Complete HH login in the opened browser, then press Enter here...")
        if not authenticated_marker_detected(page):
            raise HHAuthSetupError("HH authentication marker was not detected")
        atomic_write_storage_state(context, output_path)
        logger.info("hh_auth_setup_succeeded hostname=%s path=%s output=%s", hostname, path, output_path)
        return 0
    except (HHAuthSetupError, PlaywrightTimeoutError, PlaywrightError) as exc:
        logger.error("hh_auth_setup_failed error=%s", exc)
        return 1
    finally:
        for resource in (page, context, browser):
            if resource is None:
                continue
            close = getattr(resource, "close", None)
            if close is not None:
                try:
                    close()
                except PlaywrightError:
                    logger.debug("hh_auth_setup_close_skipped", exc_info=True)
        if playwright_runtime is not None:
            playwright_runtime.stop()


if __name__ == "__main__":
    sys.exit(main())
