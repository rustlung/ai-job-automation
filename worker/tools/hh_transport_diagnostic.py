"""Compare one configured HH search URL through Playwright and production HTTPX."""

import argparse
import asyncio
import json
import sys
from pathlib import Path


def _api_root() -> Path:
    return Path(__file__).resolve().parents[1] / "api"


sys.path.insert(0, str(_api_root()))

from app.core.config import Settings  # noqa: E402
from app.services.hh_transport_diagnostic import (  # noqa: E402
    HHTransportDiagnosticSelectionError,
    HHTransportDiagnosticService,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare one configured HH query through Playwright and HTTPX.")
    parser.add_argument("--profile-id", default=None, help="Configured expanded-search profile id.")
    parser.add_argument("--query-variant-id", default=None, help="Configured query variant id for the selected profile.")
    return parser.parse_args(argv)


async def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    service = HHTransportDiagnosticService.from_settings(Settings())
    try:
        result = await service.compare(profile_id=args.profile_id, query_variant_id=args.query_variant_id)
    except HHTransportDiagnosticSelectionError as exc:
        print(json.dumps({"classification": "inconclusive", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
