from conftest import NOTIFICATIONS
from formatting import SUBTITLE_TEMPLATE, TITLE_TEMPLATE, format_string

PULL_REQUEST, ISSUE, RELEASE = NOTIFICATIONS


def test_numbered_subjects_get_their_number():
    assert format_string(TITLE_TEMPLATE, PULL_REQUEST) == "octo-org/web-app #42"
    assert format_string(TITLE_TEMPLATE, ISSUE) == "octo-org/cli #7"


def test_other_subjects_get_a_release_title():
    assert format_string(TITLE_TEMPLATE, RELEASE) == "octo-org/cli "
    assert format_string("{release_title}{repo_name}", RELEASE) == "v2.0.0 in cli"
    assert format_string("{release_title}", ISSUE) == ""


def test_subtitle_uses_reason_and_subject_title():
    assert format_string(SUBTITLE_TEMPLATE, ISSUE) == "[Mention] Crash when the config file is empty"
