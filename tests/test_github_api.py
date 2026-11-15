import json

import pytest

from github_api import (
    BadCredentials,
    Github,
    GithubError,
    RateLimitExceeded,
    Response,
)


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, method, url, headers, body):
        self.requests.append((method, url, headers, body))
        return self.responses.pop(0)


def ok(payload, status=200):
    return Response(status, {}, json.dumps(payload).encode())


def test_requests_carry_token_and_api_headers():
    transport = FakeTransport(ok([]))
    Github("test-token", transport).notifications(10)
    method, url, headers, body = transport.requests[0]
    assert method == "GET"
    assert url == "https://api.github.com/notifications?all=true&per_page=50&page=1"
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["Accept"] == "application/vnd.github+json"
    assert body is None


def test_notifications_page_until_limit():
    transport = FakeTransport(ok([{"id": str(n)} for n in range(50)]), ok([{"id": "x"}] * 50))
    notifications = Github("t", transport).notifications(60)
    assert len(notifications) == 60
    assert [request[1][-6:] for request in transport.requests] == ["page=1", "page=2"]


def test_notifications_stop_on_short_page():
    transport = FakeTransport(ok([{"id": "1"}]))
    assert Github("t", transport).notifications(100) == [{"id": "1"}]
    assert len(transport.requests) == 1


def test_mark_read_and_mark_all_read():
    transport = FakeTransport(Response(205, {}, b""), Response(202, {}, b'{"message": "queued"}'))
    client = Github("t", transport)
    client.mark_read("101")
    client.mark_all_read()
    assert transport.requests[0][:2] == ("PATCH", "https://api.github.com/notifications/threads/101")
    method, url, headers, body = transport.requests[1]
    assert (method, url, json.loads(body)) == ("PUT", "https://api.github.com/notifications", {"read": True})
    assert headers["Content-Type"] == "application/json"


def test_html_url_follows_the_subject_api_url():
    transport = FakeTransport(ok({"html_url": "https://github.com/octo-org/cli/issues/7"}))
    client = Github("t", transport)
    assert client.html_url("https://api.github.com/repos/octo-org/cli/issues/7") == "https://github.com/octo-org/cli/issues/7"
    assert transport.requests[0][1] == "https://api.github.com/repos/octo-org/cli/issues/7"


def test_token_is_only_sent_to_the_api_host():
    transport = FakeTransport()
    with pytest.raises(GithubError):
        Github("t", transport).html_url("https://example.com/steal")
    assert transport.requests == []


def test_unauthorized_raises_bad_credentials():
    transport = FakeTransport(Response(401, {}, b'{"message": "Bad credentials"}'))
    with pytest.raises(BadCredentials, match="Bad credentials"):
        Github("t", transport).notifications(10)


@pytest.mark.parametrize("response", [
    Response(403, {"X-RateLimit-Remaining": "0"}, b'{"message": "API rate limit exceeded"}'),
    Response(429, {}, b'{"message": "slow down"}'),
])
def test_rate_limits(response):
    with pytest.raises(RateLimitExceeded):
        Github("t", FakeTransport(response)).notifications(10)


def test_other_errors_include_status_and_message():
    transport = FakeTransport(Response(403, {"X-RateLimit-Remaining": "4999"}, b'{"message": "Resource not accessible"}'))
    with pytest.raises(GithubError, match="403: Resource not accessible"):
        Github("t", transport).notifications(10)
