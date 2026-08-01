from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import Settings
from app.schemas.hh_collection import SearchProfile, SearchProfileSourceType, SearchProfileTrack

HH_SEARCH_PATH = "/search/vacancy"
HH_REMOTE_SCHEDULE_VALUE = "remote"
HH_SEARCH_PARAMS_REPLACED_BY_COLLECTOR = {
    "enable_snippets",
    "items_on_page",
    "page",
    "experience",
    "schedule",
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
                max_pages=2,
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
                max_pages=2,
                items_on_page=100,
                remote_only=True,
                experience=["noExperience", "between1And3"],
                order=20,
            ),
            SearchProfile(
                id="ai_expanded_search",
                name="AI expanded search",
                track=SearchProfileTrack.MAIN,
                source_type=SearchProfileSourceType.EXPANDED_SEARCH,
                base_url=self._public_search_url(),
                query="AI automation AI integration LLM n8n автоматизация",
                max_pages=2,
                items_on_page=100,
                remote_only=True,
                experience=["noExperience", "between1And3"],
                order=30,
            ),
            SearchProfile(
                id="python_expanded_search",
                name="Python expanded search",
                track=SearchProfileTrack.MAIN,
                source_type=SearchProfileSourceType.EXPANDED_SEARCH,
                base_url=self._public_search_url(),
                query="Python backend FastAPI API интеграции",
                max_pages=2,
                items_on_page=100,
                remote_only=True,
                experience=["noExperience", "between1And3"],
                order=40,
            ),
            SearchProfile(
                id="alt_opportunities",
                name="Alternative opportunities",
                track=SearchProfileTrack.ALTERNATIVE,
                source_type=SearchProfileSourceType.EXPANDED_SEARCH,
                base_url=self._public_search_url(),
                query="QA тестировщик data analyst системный аналитик бизнес аналитик AI trainer AI evaluation",
                max_pages=1,
                items_on_page=100,
                remote_only=True,
                experience=["noExperience", "between1And3"],
                order=50,
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

    def build_search_url(self, profile: SearchProfile, page: int, max_pages_override: int | None = None) -> str:
        if not profile.base_url:
            raise HHInvalidSearchProfileUrlError(profile.id)
        self._validate_base_url(profile)

        replaced_keys = set(HH_SEARCH_PARAMS_REPLACED_BY_COLLECTOR)
        if profile.query:
            replaced_keys.add("text")
        params = [(key, value) for key, value in parse_qsl(urlsplit(profile.base_url).query, keep_blank_values=True) if key not in replaced_keys]
        if profile.query:
            params.append(("text", profile.query))
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
            params.append(("schedule", HH_REMOTE_SCHEDULE_VALUE))

        parts = urlsplit(profile.base_url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))

    def max_pages_for(self, profile: SearchProfile, max_pages_override: int | None) -> int:
        if max_pages_override is None:
            return profile.max_pages
        return min(profile.max_pages, max_pages_override)

    def safe_url_parts(self, url: str) -> tuple[str, str]:
        parts = urlsplit(url)
        return parts.hostname or "", parts.path

    def _public_search_url(self) -> str:
        return f"{self.settings.hh_base_url.rstrip('/')}{HH_SEARCH_PATH}"

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
