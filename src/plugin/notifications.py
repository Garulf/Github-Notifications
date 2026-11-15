from __future__ import annotations

import asyncio
import time
from functools import partial
from pathlib import Path
from random import choice
from typing import Callable, List, Optional

from pyflowlauncher import FlowLauncherV2, Plugin, Result, api
from pyflowlauncher.models.result import PreviewInfo

from formatting import SUBTITLE_TEMPLATE, TITLE_TEMPLATE, format_string
from github_api import BadCredentials, ConnectionFailed, Github, GithubError, RateLimitExceeded
from phrases import phrases

PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_ICON = str(PLUGIN_DIR.parent / "icon.png")
UNREAD_ICON = str(PLUGIN_DIR / "icons" / "unread2.png")
READ_ICON = str(PLUGIN_DIR / "icons" / "read.png")
DEFAULT_MAX_RESULTS = 20
CACHE_SECONDS = 5

plugin = Plugin(launcher=FlowLauncherV2())
make_client: Callable[[str], Github] = Github


class NotificationCache:
    def __init__(self, max_age: float = CACHE_SECONDS, clock: Callable[[], float] = time.monotonic) -> None:
        self._max_age = max_age
        self._clock = clock
        self._key: Optional[tuple] = None
        self._stored_at = 0.0
        self._notifications: List[dict] = []

    def get(self, key: tuple) -> Optional[List[dict]]:
        if key == self._key and self._clock() - self._stored_at < self._max_age:
            return self._notifications
        return None

    def put(self, key: tuple, notifications: List[dict]) -> None:
        self._key = key
        self._stored_at = self._clock()
        self._notifications = notifications

    def mark_read(self, thread_id: str) -> None:
        for notification in self._notifications:
            if notification["id"] == thread_id:
                notification["unread"] = False

    def clear(self) -> None:
        self._key = None
        self._notifications = []


cache = NotificationCache()


def token() -> str:
    return (plugin.settings.get("token") or "").strip()


def max_results() -> int:
    try:
        return int(plugin.settings.get("max_results") or DEFAULT_MAX_RESULTS)
    except (TypeError, ValueError):
        return DEFAULT_MAX_RESULTS


def github() -> Github:
    return make_client(token())


async def run_blocking(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


def preview(description: Optional[str]) -> PreviewInfo:
    return PreviewInfo(PreviewImagePath=None, Description=description or "", IsMedia=False, PreviewDeligate=None)


def message(title: str, subtitle: str) -> Result:
    return Result(title=title, subtitle=subtitle, icon=PLUGIN_ICON, preview=preview(subtitle))


def settings_message(title: str, subtitle: str) -> Result:
    return message(title, subtitle).add_action(api.open_setting_dialog())


def fetch_notifications() -> List[dict]:
    key = (token(), max_results())
    notifications = cache.get(key)
    if notifications is None:
        notifications = github().notifications(max_results())
        cache.put(key, notifications)
    return notifications


def notification_result(notification: dict) -> Result:
    title = format_string(plugin.settings.get("title") or TITLE_TEMPLATE, notification)
    subtitle = format_string(plugin.settings.get("subtitle") or SUBTITLE_TEMPLATE, notification)
    return Result(
        title=title,
        subtitle=subtitle,
        icon=UNREAD_ICON if notification["unread"] else READ_ICON,
        context_data=[notification["id"]],
        preview=preview(subtitle),
    ).add_action(open_url, [notification["subject"]["url"], notification["id"]])


def search(query: str) -> List[Result]:
    results = [notification_result(notification) for notification in fetch_notifications()]
    needle = query.lower()
    return [result for result in results if needle in result.title.lower()]


@plugin.on_method
async def query(query: str):
    try:
        results = await run_blocking(search, query)
    except BadCredentials:
        return [settings_message("Could not login to Github", "Bad or missing Personal Access Token.")]
    except RateLimitExceeded:
        return [message("Rate limit exceeded", "You have reached the rate limit for this hour.")]
    except ConnectionFailed as error:
        return [message("Could not connect to Github", str(error))]
    except GithubError as error:
        return [message("Github returned an error", str(error))]
    return results or [message("No notifications", choice(phrases))]


@plugin.on_method
def context_menu(data):
    results = []
    if data:
        thread_id = data[0]
        results.append(message("Mark as read", "Mark notification as read.").add_action(mark_read, [thread_id]))
        results.append(message("Mark all as read", "Mark all notifications as read.").add_action(clear_all))
    results.append(message("Refresh Cache", "Refresh the cache.").add_action(refresh_cache))
    return results


async def report_error(error: GithubError) -> None:
    await plugin.launcher.api.invoke(api.show_msg("Github Notifications", str(error), PLUGIN_ICON))


def mark_thread_read(thread_id: str) -> None:
    github().mark_read(thread_id)
    cache.mark_read(thread_id)


@plugin.on_method
async def mark_read(thread_id: str):
    try:
        await run_blocking(mark_thread_read, thread_id)
    except GithubError as error:
        await report_error(error)


def mark_all_threads_read() -> None:
    github().mark_all_read()
    cache.clear()


@plugin.on_method
async def clear_all():
    try:
        await run_blocking(mark_all_threads_read)
    except GithubError as error:
        await report_error(error)


@plugin.on_method
def refresh_cache():
    cache.clear()


def resolve_html_url(subject_url: str, thread_id: str) -> str:
    client = github()
    client.mark_read(thread_id)
    cache.mark_read(thread_id)
    return client.html_url(subject_url)


@plugin.on_method
async def open_url(subject_url: str, thread_id: str):
    try:
        url = await run_blocking(resolve_html_url, subject_url, thread_id)
    except GithubError as error:
        await report_error(error)
        return
    await plugin.launcher.api.invoke(api.open_url(url))
