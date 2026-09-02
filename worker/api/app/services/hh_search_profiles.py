from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import Settings
from app.schemas.hh_collection import SearchProfile, SearchProfileSourceType, SearchProfileTrack, SearchQueryVariant

HH_SEARCH_PATH = "/search/vacancy"
HH_REMOTE_WORK_FORMAT_VALUE = "REMOTE"
HH_PUBLIC_SEARCH_PERIOD_DAYS = 3
HH_SEARCH_PARAMS_REPLACED_BY_COLLECTOR = {
    "enable_snippets",
    "items_on_page",
    "page",
    "experience",
    "schedule",
    "work_format",
}


class HHSearchProfileError(Exception):
    pass


class HHUnknownSearchProfileError(HHSearchProfileError):
    def __init__(self, profile_id: str) -> None:
        super().__init__(profile_id)
        self.profile_id = profile_id


class HHInvalidSearchProfileUrlError(HHSearchProfileError):
    def __init__(self, profile_id: str) -> None:
        super().__init__(profile_id)
        self.profile_id = profile_id


class HHSearchProfileRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_profiles(self) -> list[SearchProfile]:
        profiles = [
            SearchProfile(
                id="ai_resume_recommendations",
                name="AI resume recommendations",
                track=SearchProfileTrack.MAIN,
                source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
                enabled=bool(self.settings.hh_ai_resume_search_url),
                base_url=self.settings.hh_ai_resume_search_url or None,
                max_pages=3,
                items_on_page=100,
                remote_only=True,
                experience=["noExperience", "between1And3"],
                order=10,
            ),
            SearchProfile(
                id="python_resume_recommendations",
                name="Python resume recommendations",
                track=SearchProfileTrack.MAIN,
                source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
                enabled=bool(self.settings.hh_python_resume_search_url),
                base_url=self.settings.hh_python_resume_search_url or None,
                max_pages=3,
                items_on_page=100,
                remote_only=True,
                experience=["noExperience", "between1And3"],
                order=20,
            ),
            self._public_profile(
                id="ai_expanded_search",
                name="AI expanded search",
                track=SearchProfileTrack.MAIN,
                query_variants=[
                    SearchQueryVariant(id="ai_automation", query="AI automation", max_pages=5, order=10),
                    SearchQueryVariant(id="ai_integration", query="AI integration", max_pages=5, order=20),
                    SearchQueryVariant(id="llm_engineer", query="LLM инженер", max_pages=5, order=30),
                    SearchQueryVariant(id="n8n", query="n8n", max_pages=5, order=40),
                ],
                max_pages=5,
                order=30,
            ),
            self._public_profile(
                id="python_expanded_search",
                name="Python expanded search",
                track=SearchProfileTrack.MAIN,
                query_variants=[
                    SearchQueryVariant(id="python_backend", query="Python backend", max_pages=5, order=10),
                    SearchQueryVariant(id="fastapi", query="FastAPI", max_pages=5, order=20),
                ],
                max_pages=5,
                order=40,
            ),
            self._public_profile(
                id="alt_opportunities",
                name="Alternative opportunities",
                track=SearchProfileTrack.ALTERNATIVE,
                query_variants=[
                    SearchQueryVariant(id="qa", query="тестировщик QA", max_pages=3, order=10),
                    SearchQueryVariant(id="data_analyst", query="аналитик данных", max_pages=3, order=20),
                    SearchQueryVariant(id="system_analyst", query="системный аналитик", max_pages=3, order=30),
                    SearchQueryVariant(id="business_analyst", query="бизнес-аналитик IT", max_pages=3, order=40),
                    SearchQueryVariant(id="ai_trainer", query="AI тренер", max_pages=3, order=50),
                ],
                max_pages=3,
                order=50,
            ),
            self._public_profile(
                id="ai_automation_keywords",
                name="AI automation keywords",
                track=SearchProfileTrack.MAIN,
                query_variants=[
                    SearchQueryVariant(id="ai_automation_en", query="AI Automation", max_pages=3, order=10),
                    SearchQueryVariant(id="ai_automation_ru", query="Автоматизация с ИИ", max_pages=3, order=20),
                ],
                max_pages=3,
                order=60,
            ),
            self._public_profile(
                id="vibecoding_keywords",
                name="Vibecoding keywords",
                track=SearchProfileTrack.MAIN,
                query_variants=[
                    SearchQueryVariant(id="vibecoder_ru", query="вайбкодер", max_pages=3, order=10),
                    SearchQueryVariant(id="vibe_coding", query="vibe coding", max_pages=3, order=20),
                    SearchQueryVariant(id="ai_product_builder", query="AI Product Builder", max_pages=3, order=30),
                    SearchQueryVariant(id="ai_first_developer_ru", query="AI-first разработчик", max_pages=3, order=40),
                ],
                max_pages=3,
                order=70,
            ),
            self._public_profile(
                id="python_backend_keywords",
                name="Python backend keywords",
                track=SearchProfileTrack.MAIN,
                query_variants=[
                    SearchQueryVariant(id="python_backend", query="Python backend", max_pages=3, order=10),
                    SearchQueryVariant(id="fastapi", query="FastAPI", max_pages=3, order=20),
                ],
                max_pages=3,
                order=80,
            ),
            self._public_profile(
                id="python_automation_keywords",
                name="Python automation keywords",
                track=SearchProfileTrack.MAIN,
                query_variants=[
                    SearchQueryVariant(id="python_automation_ru", query="Python автоматизация", max_pages=3, order=10),
                    SearchQueryVariant(id="python_automation_en", query="Python automation", max_pages=3, order=20),
                ],
                max_pages=3,
                order=90,
            ),
        ]
        return sorted(profiles, key=lambda profile: profile.order)

    def get_profiles(self, profile_ids: list[str] | None) -> list[SearchProfile]:
        profiles = self.list_profiles()
        if profile_ids is None:
            return profiles

        by_id = {profile.id: profile for profile in profiles}
        selected: list[SearchProfile] = []
        seen: set[str] = set()
        for profile_id in profile_ids:
            if profile_id not in by_id:
                raise HHUnknownSearchProfileError(profile_id)
            if profile_id in seen:
                continue
            seen.add(profile_id)
            selected.append(by_id[profile_id])
        return selected

    def build_search_url(
        self,
        profile: SearchProfile,
        page: int,
        query_variant: SearchQueryVariant | None = None,
    ) -> str:
        if not profile.base_url:
            raise HHInvalidSearchProfileUrlError(profile.id)
        self._validate_base_url(profile)

        replaced_keys = set(HH_SEARCH_PARAMS_REPLACED_BY_COLLECTOR)
        if profile.search_period is not None:
            replaced_keys.add("search_period")
        query = query_variant.query if query_variant is not None else profile.query
        if query:
            replaced_keys.add("text")
        params = [
            (key, value)
            for key, value in parse_qsl(urlsplit(profile.base_url).query, keep_blank_values=True)
            if key not in replaced_keys
        ]
        if query:
            params.append(("text", query))
        params.extend(
            [
                ("enable_snippets", "true"),
                ("items_on_page", str(profile.items_on_page)),
                ("page", str(page)),
            ]
        )
        for experience in profile.experience:
            params.append(("experience", experience))
        if profile.remote_only:
            params.append(("work_format", HH_REMOTE_WORK_FORMAT_VALUE))
        if profile.search_period is not None:
            params.append(("search_period", str(profile.search_period)))

        parts = urlsplit(profile.base_url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))

    def max_pages_for(
        self,
        profile: SearchProfile,
        max_pages_override: int | None,
        query_variant: SearchQueryVariant | None = None,
    ) -> int:
        limits = [profile.max_pages]
        if query_variant is not None and query_variant.max_pages is not None:
            limits.append(query_variant.max_pages)
        if max_pages_override is not None:
            limits.append(max_pages_override)
        return max(min(limits), 1)

    def safe_url_parts(self, url: str) -> tuple[str, str]:
        parts = urlsplit(url)
        return parts.hostname or "", parts.path

    def safe_url_for_log(self, url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def enabled_query_variants(profile: SearchProfile) -> list[SearchQueryVariant]:
        return sorted((variant for variant in profile.query_variants if variant.enabled), key=lambda variant: variant.order)

    def _public_search_url(self) -> str:
        return f"{self.settings.hh_base_url.rstrip('/')}{HH_SEARCH_PATH}"

    def _public_profile(
        self,
        *,
        id: str,
        name: str,
        track: SearchProfileTrack,
        query_variants: list[SearchQueryVariant],
        max_pages: int,
        order: int,
    ) -> SearchProfile:
        return SearchProfile(
            id=id,
            name=name,
            track=track,
            source_type=SearchProfileSourceType.EXPANDED_SEARCH,
            base_url=self._public_search_url(),
            query_variants=query_variants,
            max_pages=max_pages,
            items_on_page=20,
            remote_only=True,
            experience=["noExperience", "between1And3"],
            search_period=HH_PUBLIC_SEARCH_PERIOD_DAYS,
            order=order,
        )

    def _validate_base_url(self, profile: SearchProfile) -> None:
        assert profile.base_url is not None
        parts = urlsplit(profile.base_url)
        hostname = parts.hostname or ""
        if parts.scheme != "https":
            raise HHInvalidSearchProfileUrlError(profile.id)
        if hostname != "hh.ru" and not hostname.endswith(".hh.ru"):
            raise HHInvalidSearchProfileUrlError(profile.id)
        if parts.path.rstrip("/") != HH_SEARCH_PATH:
            raise HHInvalidSearchProfileUrlError(profile.id)
        if parts.fragment:
            raise HHInvalidSearchProfileUrlError(profile.id)
