import copy

import pytest

import notifications

NOTIFICATIONS = [
    {
        "id": "101",
        "unread": True,
        "reason": "review_requested",
        "subject": {
            "title": "Add dark mode toggle",
            "url": "https://api.github.com/repos/octo-org/web-app/pulls/42",
            "type": "PullRequest",
        },
        "repository": {
            "name": "web-app",
            "full_name": "octo-org/web-app",
            "owner": {"login": "octo-org"},
            "html_url": "https://github.com/octo-org/web-app",
        },
    },
    {
        "id": "102",
        "unread": False,
        "reason": "mention",
        "subject": {
            "title": "Crash when the config file is empty",
            "url": "https://api.github.com/repos/octo-org/cli/issues/7",
            "type": "Issue",
        },
        "repository": {
            "name": "cli",
            "full_name": "octo-org/cli",
            "owner": {"login": "octo-org"},
            "html_url": "https://github.com/octo-org/cli",
        },
    },
    {
        "id": "103",
        "unread": True,
        "reason": "subscribed",
        "subject": {
            "title": "v2.0.0",
            "url": "https://api.github.com/repos/octo-org/cli/releases/9",
            "type": "Release",
        },
        "repository": {
            "name": "cli",
            "full_name": "octo-org/cli",
            "owner": {"login": "octo-org"},
            "html_url": "https://github.com/octo-org/cli",
        },
    },
]


class FakeGithub:
    def __init__(self, token, notifications=None, error=None):
        self.token = token
        self.calls = []
        self._notifications = copy.deepcopy(NOTIFICATIONS if notifications is None else notifications)
        self._error = error

    def _call(self, *call):
        self.calls.append(call)
        if self._error:
            raise self._error

    def notifications(self, limit):
        self._call("notifications", limit)
        return self._notifications[:limit]

    def mark_read(self, thread_id):
        self._call("mark_read", thread_id)

    def mark_all_read(self):
        self._call("mark_all_read")

    def html_url(self, api_url):
        self._call("html_url", api_url)
        return api_url.replace("api.github.com/repos", "github.com").replace("/pulls/", "/pull/")


class FakeGithubFactory:
    def __init__(self):
        self.instances = []
        self.notifications = None
        self.error = None

    def __call__(self, token):
        client = FakeGithub(token, self.notifications, self.error)
        self.instances.append(client)
        return client

    @property
    def calls(self):
        return [call for client in self.instances for call in client.calls]


@pytest.fixture
def settings():
    launcher = notifications.plugin.launcher
    launcher._settings = {"token": "test-token", "max_results": "20"}
    yield launcher._settings
    launcher._settings = {}


@pytest.fixture
def github(settings, monkeypatch):
    factory = FakeGithubFactory()
    monkeypatch.setattr(notifications, "make_client", factory)
    monkeypatch.setattr(notifications, "cache", notifications.NotificationCache())
    return factory


@pytest.fixture
def invoked(monkeypatch):
    commands = []

    async def invoke(command):
        commands.append(command)

    monkeypatch.setattr(notifications.plugin.launcher.api, "_invoke_fn", invoke)
    return commands
