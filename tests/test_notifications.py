import asyncio
import json

import notifications
from github_api import BadCredentials, ConnectionFailed, RateLimitExceeded


def run(coroutine):
    return asyncio.run(coroutine)


def titles(results):
    return [result.title for result in results]


def test_query_lists_notifications_with_default_formats(github):
    results = run(notifications.query(""))
    assert titles(results) == ["octo-org/web-app #42", "octo-org/cli #7", "octo-org/cli "]
    assert results[0].subtitle == "[Review_Requested] Add dark mode toggle"
    assert results[0].icon == notifications.UNREAD_ICON
    assert results[1].icon == notifications.READ_ICON
    assert github.instances[0].token == "test-token"


def test_query_filters_on_title_case_insensitively(github):
    assert titles(run(notifications.query("WEB"))) == ["octo-org/web-app #42"]


def test_custom_formats_from_settings(github, settings):
    settings["title"] = "{release_title}{repo_full_name}"
    settings["subtitle"] = "{subject_url}"
    result = run(notifications.query(""))[2]
    assert result.title == "v2.0.0 in octo-org/cli"
    assert result.subtitle == "https://api.github.com/repos/octo-org/cli/releases/9"


def test_result_opens_the_subject_and_carries_thread_id(github):
    result = run(notifications.query(""))[0].to_json()
    assert result["JsonRPCAction"]["Method"] == "open_url"
    assert result["JsonRPCAction"]["Parameters"] == ["https://api.github.com/repos/octo-org/web-app/pulls/42", "101"]
    assert result["ContextData"] == ["101"]
    assert result["Preview"]["Description"] == "[Review_Requested] Add dark mode toggle"
    json.dumps(result)


def test_max_results_setting_limits_the_request(github, settings):
    settings["max_results"] = "2"
    assert len(run(notifications.query(""))) == 2
    assert github.calls == [("notifications", 2)]


def test_invalid_max_results_falls_back_to_default(github, settings):
    settings["max_results"] = "lots"
    run(notifications.query(""))
    assert github.calls == [("notifications", notifications.DEFAULT_MAX_RESULTS)]


def test_notifications_are_cached_between_keystrokes(github):
    run(notifications.query("o"))
    run(notifications.query("oc"))
    assert github.calls == [("notifications", 20)]


def test_cache_expires(github, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(notifications, "cache", notifications.NotificationCache(clock=lambda: now[0]))
    run(notifications.query(""))
    now[0] = notifications.CACHE_SECONDS + 1
    run(notifications.query(""))
    assert len(github.calls) == 2


def test_no_notifications_shows_a_phrase(github):
    github.notifications = []
    (result,) = run(notifications.query(""))
    assert result.title == "No notifications"
    assert result.subtitle in notifications.phrases


def test_bad_credentials_points_to_settings(github):
    github.error = BadCredentials("Bad credentials")
    (result,) = run(notifications.query(""))
    assert result.title == "Could not login to Github"
    assert result.json_rpc_action["Method"] == "Flow.Launcher.OpenSettingDialog"


def test_rate_limit_message(github):
    github.error = RateLimitExceeded("API rate limit exceeded")
    assert titles(run(notifications.query(""))) == ["Rate limit exceeded"]


def test_connection_failure_message(github):
    github.error = ConnectionFailed("timed out")
    (result,) = run(notifications.query(""))
    assert result.title == "Could not connect to Github"
    assert result.subtitle == "timed out"


def test_context_menu_for_a_notification():
    results = notifications.context_menu(["101"])
    assert titles(results) == ["Mark as read", "Mark all as read", "Refresh Cache"]
    assert results[0].json_rpc_action["Parameters"] == ["101"]


def test_context_menu_without_a_notification():
    assert titles(notifications.context_menu(None)) == ["Refresh Cache"]


def test_open_url_marks_read_and_opens_html_page(github, invoked):
    run(notifications.query(""))
    run(notifications.open_url("https://api.github.com/repos/octo-org/web-app/pulls/42", "101"))
    assert ("mark_read", "101") in github.calls
    assert invoked == [{"Method": "Flow.Launcher.OpenUrl", "Parameters": ["https://github.com/octo-org/web-app/pull/42", False]}]
    assert run(notifications.query(""))[0].icon == notifications.READ_ICON


def test_open_url_reports_errors(github, invoked):
    github.error = ConnectionFailed("timed out")
    run(notifications.open_url("https://api.github.com/repos/octo-org/web-app/pulls/42", "101"))
    assert invoked[0]["Method"] == "Flow.Launcher.ShowMsg"
    assert invoked[0]["Parameters"][1] == "timed out"


def test_mark_read_updates_the_cached_icon(github):
    run(notifications.query(""))
    run(notifications.mark_read("103"))
    assert github.calls[-1] == ("mark_read", "103")
    assert run(notifications.query(""))[2].icon == notifications.READ_ICON
    assert github.calls.count(("notifications", 20)) == 1


def test_mark_all_read_refetches(github):
    run(notifications.query(""))
    run(notifications.clear_all())
    run(notifications.query(""))
    assert github.calls == [("notifications", 20), ("mark_all_read",), ("notifications", 20)]


def test_refresh_cache_refetches(github):
    run(notifications.query(""))
    notifications.refresh_cache()
    run(notifications.query(""))
    assert github.calls.count(("notifications", 20)) == 2
