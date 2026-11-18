TITLE_TEMPLATE = "{repo_owner}/{repo_name} {num_symbol}{number}"
SUBTITLE_TEMPLATE = "[{reason_title}] {subject_title}"
NUMBERED_SUBJECTS = ("PullRequest", "Issue")


def format_string(template: str, notification: dict) -> str:
    subject = notification["subject"]
    repository = notification["repository"]
    number = ""
    num_symbol = ""
    release_title = ""
    if subject["type"] in NUMBERED_SUBJECTS:
        number = subject["url"].split("/")[-1]
        num_symbol = "#"
    else:
        release_title = f"{subject['title']} in "
    return template.format(
        subject_url=subject["url"],
        number=number,
        num_symbol=num_symbol,
        repo_full_name=repository["full_name"],
        repo_owner=repository["owner"]["login"],
        repo_name=repository["name"],
        reason_title=notification["reason"].title(),
        subject_title=subject["title"],
        release_title=release_title,
    )
