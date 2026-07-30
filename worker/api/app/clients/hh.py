import logging
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)


class HHClientError(Exception):
    pass


class HHConnectionError(HHClientError):
    pass


class HHTimeoutError(HHClientError):
    pass


class HHHTTPError(HHClientError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HHUnexpectedContentError(HHClientError):
    pass


class HHResponseTooLargeError(HHClientError):
    pass


class HHInvalidFinalUrlError(HHClientError):
    pass


@dataclass(frozen=True)
class HHPageResponse:
    html: str
    final_url: str
    status_code: int
    size_bytes: int


class HHSearchClient:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: float,
        max_response_bytes: int,
        max_redirects: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects
        self.transport = transport

    async def fetch_search_page(self, search_url: str) -> str:
        started_at = time.perf_counter()
        safe_url = self._safe_url_for_log(search_url)
        logger.info("hh_search_fetch_started url=%s", safe_url)

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                max_redirects=self.max_redirects,
                transport=self.transport,
                headers={"User-Agent": self.user_agent},
            ) as client:
                async with client.stream("GET", search_url) as response:
                    response.raise_for_status()
                    self._validate_content_type(response)
                    html = await self._read_limited_html(response)
        except httpx.TimeoutException as exc:
            logger.warning("hh_search_fetch_failed url=%s reason=timeout", safe_url)
            raise HHTimeoutError("HH request timed out") from exc
        except httpx.TooManyRedirects as exc:
            logger.warning("hh_search_fetch_failed url=%s reason=too_many_redirects", safe_url)
            raise HHHTTPError("HH returned too many redirects") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning("hh_search_fetch_failed url=%s status_code=%s", safe_url, status_code)
            raise HHHTTPError("HH returned an HTTP error", status_code=status_code) from exc
        except httpx.ConnectError as exc:
            logger.warning("hh_search_fetch_failed url=%s reason=connection_error", safe_url)
            raise HHConnectionError("HH connection failed") from exc
        except httpx.RequestError as exc:
            logger.warning("hh_search_fetch_failed url=%s reason=request_error", safe_url)
            raise HHConnectionError("HH request failed") from exc
        except HHUnexpectedContentError:
            logger.warning("hh_search_fetch_failed url=%s reason=unexpected_content_type", safe_url)
            raise
        except HHResponseTooLargeError:
            logger.warning("hh_search_fetch_failed url=%s reason=response_too_large", safe_url)
            raise

        duration_ms = self._duration_ms(started_at)
        logger.info(
            "hh_search_fetch_succeeded url=%s size_bytes=%s duration_ms=%s",
            safe_url,
            len(html.encode("utf-8")),
            duration_ms,
        )
        return html

    async def fetch_vacancy_page(self, url: str) -> HHPageResponse:
        started_at = time.perf_counter()
        safe_url = self._safe_url_for_log(url)
        requested_external_id = self._extract_vacancy_id(url)
        logger.info("hh_vacancy_fetch_started url=%s external_id=%s", safe_url, requested_external_id)

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                max_redirects=self.max_redirects,
                transport=self.transport,
                headers={"User-Agent": self.user_agent},
            ) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    self._validate_final_vacancy_url(str(response.url), requested_external_id)
                    self._validate_content_type(response)
                    html = await self._read_limited_html(response)
        except httpx.TimeoutException as exc:
            logger.warning("hh_vacancy_fetch_failed url=%s reason=timeout", safe_url)
            raise HHTimeoutError("HH request timed out") from exc
        except httpx.TooManyRedirects as exc:
            logger.warning("hh_vacancy_fetch_failed url=%s reason=too_many_redirects", safe_url)
            raise HHHTTPError("HH returned too many redirects") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning("hh_vacancy_fetch_failed url=%s status_code=%s", safe_url, status_code)
            raise HHHTTPError("HH returned an HTTP error", status_code=status_code) from exc
        except httpx.ConnectError as exc:
            logger.warning("hh_vacancy_fetch_failed url=%s reason=connection_error", safe_url)
            raise HHConnectionError("HH connection failed") from exc
        except httpx.RequestError as exc:
            logger.warning("hh_vacancy_fetch_failed url=%s reason=request_error", safe_url)
            raise HHConnectionError("HH request failed") from exc
        except HHInvalidFinalUrlError:
            logger.warning("hh_vacancy_fetch_failed url=%s reason=invalid_final_url", safe_url)
            raise
        except HHUnexpectedContentError:
            logger.warning("hh_vacancy_fetch_failed url=%s reason=unexpected_content_type", safe_url)
            raise
        except HHResponseTooLargeError:
            logger.warning("hh_vacancy_fetch_failed url=%s reason=response_too_large", safe_url)
            raise

        final_url = self._clean_url(str(response.url))
        size_bytes = len(html.encode("utf-8"))
        duration_ms = self._duration_ms(started_at)
        logger.info(
            "hh_vacancy_fetch_succeeded url=%s final_domain=%s status_code=%s size_bytes=%s duration_ms=%s",
            safe_url,
            urlsplit(final_url).netloc,
            response.status_code,
            size_bytes,
            duration_ms,
        )
        return HHPageResponse(html=html, final_url=final_url, status_code=response.status_code, size_bytes=size_bytes)

    def _validate_content_type(self, response: httpx.Response) -> None:
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            raise HHUnexpectedContentError("HH returned unexpected content type")

    async def _read_limited_html(self, response: httpx.Response) -> str:
        chunks: list[bytes] = []
        total_bytes = 0
        async for chunk in response.aiter_bytes():
            total_bytes += len(chunk)
            if total_bytes > self.max_response_bytes:
                raise HHResponseTooLargeError("HH response is too large")
            chunks.append(chunk)

        content = b"".join(chunks)
        encoding = response.encoding or "utf-8"
        return content.decode(encoding, errors="replace")

    @staticmethod
    def _safe_url_for_log(url: str) -> str:
        return HHSearchClient._clean_url(url)

    @staticmethod
    def _clean_url(url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)

    @staticmethod
    def _extract_vacancy_id(url: str) -> str:
        parts = urlsplit(url)
        path_parts = [part for part in parts.path.split("/") if part]
        if len(path_parts) != 2 or path_parts[0] != "vacancy" or not path_parts[1].isdigit():
            raise HHInvalidFinalUrlError("HH vacancy URL must contain /vacancy/{id}")
        return path_parts[1]

    def _validate_final_vacancy_url(self, url: str, expected_external_id: str) -> None:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        if parts.scheme != "https" or (hostname != "hh.ru" and not hostname.endswith(".hh.ru")):
            raise HHInvalidFinalUrlError("HH final URL must point to hh.ru")
        final_external_id = self._extract_vacancy_id(url)
        if final_external_id != expected_external_id:
            raise HHInvalidFinalUrlError("HH final vacancy id does not match requested vacancy id")
