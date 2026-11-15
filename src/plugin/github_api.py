from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Mapping, NamedTuple, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.github.com"
TIMEOUT = 10
PAGE_SIZE = 50
USER_AGENT = "Github-Notifications-Flow-Launcher"


class Response(NamedTuple):
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, str, Dict[str, str], Optional[bytes]], Response]


class GithubError(Exception):
    pass


class BadCredentials(GithubError):
    pass


class RateLimitExceeded(GithubError):
    pass


class ConnectionFailed(GithubError):
    pass


def urllib_transport(method: str, url: str, headers: Dict[str, str], body: Optional[bytes]) -> Response:
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return Response(response.status, dict(response.headers), response.read())
    except HTTPError as error:
        return Response(error.code, dict(error.headers or {}), error.read())
    except (URLError, OSError) as error:
        raise ConnectionFailed(str(getattr(error, "reason", error))) from error


def _error_message(body: bytes) -> str:
    try:
        return json.loads(body)["message"]
    except (ValueError, KeyError, TypeError):
        return body.decode("utf-8", "replace")


def _is_rate_limited(response: Response) -> bool:
    remaining = {key.lower(): value for key, value in response.headers.items()}.get("x-ratelimit-remaining")
    return response.status == 429 or (response.status == 403 and remaining == "0")


class Github:
    def __init__(self, token: str, transport: Transport = urllib_transport) -> None:
        self._token = token
        self._transport = transport

    def request(self, method: str, url: str, data: Any = None) -> Any:
        if url.startswith("/"):
            url = API_URL + url
        if not url.startswith(API_URL + "/"):
            raise GithubError(f"Refusing to send the token to {url}")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        response = self._transport(method, url, headers, body)
        if response.status == 401:
            raise BadCredentials(_error_message(response.body))
        if _is_rate_limited(response):
            raise RateLimitExceeded(_error_message(response.body))
        if response.status >= 400:
            raise GithubError(f"{response.status}: {_error_message(response.body)}")
        return json.loads(response.body) if response.body else None

    def notifications(self, limit: int) -> List[dict]:
        notifications: List[dict] = []
        page = 1
        while len(notifications) < limit:
            batch = self.request("GET", f"/notifications?all=true&per_page={PAGE_SIZE}&page={page}") or []
            notifications.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            page += 1
        return notifications[:limit]

    def mark_read(self, thread_id: str) -> None:
        self.request("PATCH", f"/notifications/threads/{thread_id}")

    def mark_all_read(self) -> None:
        self.request("PUT", "/notifications", {"read": True})

    def html_url(self, api_url: str) -> str:
        return self.request("GET", api_url)["html_url"]
