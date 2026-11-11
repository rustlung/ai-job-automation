from __future__ import annotations

from app.clients.hh import HHSearchClient
from app.clients.hh_browser import HHAuthenticatedBrowserClient
from app.core.config import Settings
from app.schemas.hh_collection import SearchProfile, SearchProfileSourceType, SearchQueryVariant
from app.schemas.hh_transport_diagnostic import classify_transport_comparison
from app.services.hh_auth_state import HHAuthStateStore
from app.services.hh_search_profiles import HHSearchProfileRegistry, HHUnknownSearchProfileError


class HHTransportDiagnosticSelectionError(Exception):
    pass


class HHTransportDiagnosticService:
    def __init__(
        self,
        profile_registry: HHSearchProfileRegistry,
        browser_client: HHAuthenticatedBrowserClient,
        search_client: HHSearchClient,
    ) -> None:
        self.profile_registry = profile_registry
        self.browser_client = browser_client
        self.search_client = search_client

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHTransportDiagnosticService":
        return cls(
            profile_registry=HHSearchProfileRegistry(settings),
            browser_client=HHAuthenticatedBrowserClient(
                auth_state_store=HHAuthStateStore(settings.hh_auth_storage_state_path),
                browser_timeout_seconds=settings.hh_auth_browser_timeout_seconds,
                page_load_timeout_seconds=settings.hh_auth_page_load_timeout_seconds,
            ),
            search_client=HHSearchClient(
                user_agent=settings.hh_user_agent,
                timeout_seconds=settings.hh_request_timeout_seconds,
                max_response_bytes=settings.hh_max_response_bytes,
            ),
        )

    async def compare(self, profile_id: str | None = None, query_variant_id: str | None = None) -> dict[str, object]:
        profile, variant = self._select_query_variant(profile_id, query_variant_id)
        url = self.profile_registry.build_search_url(profile, page=0, query_variant=variant)
        playwright = await self.browser_client.diagnose_search_page(url)
        httpx = await self.search_client.diagnose_search_page(url)
        return {
            "classification": classify_transport_comparison(playwright, httpx),
            "transports": [playwright.to_dict(), httpx.to_dict()],
        }

    def _select_query_variant(
        self,
        profile_id: str | None,
        query_variant_id: str | None,
    ) -> tuple[SearchProfile, SearchQueryVariant]:
        if profile_id is not None:
            try:
                profile = self.profile_registry.get_profiles([profile_id])[0]
            except HHUnknownSearchProfileError as exc:
                raise HHTransportDiagnosticSelectionError("Unknown configured HH profile") from exc
            if profile.source_type != SearchProfileSourceType.EXPANDED_SEARCH:
                raise HHTransportDiagnosticSelectionError("Diagnostic requires an expanded-search profile")
        else:
            profile = next(
                (
                    item
                    for item in self.profile_registry.list_profiles()
                    if item.enabled
                    and item.source_type == SearchProfileSourceType.EXPANDED_SEARCH
                    and self.profile_registry.enabled_query_variants(item)
                ),
                None,
            )
            if profile is None:
                raise HHTransportDiagnosticSelectionError("No configured expanded-search query variant is available")

        variants = self.profile_registry.enabled_query_variants(profile)
        if query_variant_id is not None:
            variant = next((item for item in variants if item.id == query_variant_id), None)
            if variant is None:
                raise HHTransportDiagnosticSelectionError("Unknown configured query variant")
        elif variants:
            variant = variants[0]
        else:
            raise HHTransportDiagnosticSelectionError("Selected profile has no enabled query variant")
        return profile, variant
