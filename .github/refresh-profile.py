import html
import json
import os
import re
import string
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

OWNER = "Vanshchandel17"
PROFILE = f"{OWNER}/{OWNER}"
README = Path(__file__).resolve().parents[1] / "README.md"


def api(path, **query):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme"}
    if token := os.getenv("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com{path}?{urlencode(query)}", headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def cell(text):
    return "".join(
        f"&#{ord(char)};" if char in string.punctuation and char not in "-./,:!?" else char
        for char in " ".join(text.split())
    )


def repo_link(name):
    return f"[{cell(name)}](https://github.com/{quote(name)})"


def repositories():
    rows = ["| Repository | Description | Last push (UTC) |",
            "| :--- | :--- | :--- |"]
    page = 1
    while True:
        repos = api(f"/users/{OWNER}/repos", type="owner", sort="pushed",
                    direction="desc", per_page=100, page=page)
        for repo in repos:
            if repo["private"] or repo["full_name"].lower() == PROFILE.lower():
                continue
            labels = [label for key, label in (("fork", "fork"), ("archived", "archived")) if repo[key]]
            link = repo_link(repo["full_name"])
            if labels:
                link += f" ({', '.join(labels)})"
            pushed = (repo["pushed_at"] or "")[:10] or "—"
            rows.append(f"| {link} | {cell(repo['description'] or '—')} | {pushed} |")
        if len(repos) < 100:
            return "\n".join(rows)
        page += 1


def activity():
    labels = {
        "PushEvent": "Pushed to", "PullRequestEvent": "Updated a pull request in",
        "PullRequestReviewEvent": "Reviewed a pull request in",
        "IssuesEvent": "Updated an issue in", "IssueCommentEvent": "Commented in",
        "CreateEvent": "Created a branch, tag, or repository in",
        "ReleaseEvent": "Published a release in", "ForkEvent": "Forked",
    }
    rows = []
    events = api(f"/users/{OWNER}/events/public", per_page=100)
    for event in sorted(events, key=lambda event: event["created_at"], reverse=True):
        name = event["repo"]["name"]
        label = labels.get(event["type"])
        if event["public"] and label and name.lower() != PROFILE.lower():
            rows.append(f"- {event['created_at'][:10]} · {label} {repo_link(name)}")
    return "\n".join(rows[:10]) or "No recent public activity in the GitHub event feed."


def pull_requests(state):
    query = f"is:pr is:public is:{state} author:{OWNER} -user:{OWNER}"
    result = api("/search/issues", q=query, sort="updated", order="desc", per_page=10)
    if result.get("incomplete_results"):
        raise RuntimeError("GitHub returned incomplete pull request results")
    rows = []
    for pr in result["items"]:
        name = pr["repository_url"].split("/repos/", 1)[1]
        title = cell(pr["title"])
        status = " (draft)" if pr.get("draft") else ""
        url = html.escape(pr["html_url"], quote=True)
        rows.append(f"- {repo_link(name)} · [#{pr['number']} · {title}]({url}){status}")
    link = f"[View all {state} upstream PRs](https://github.com/search?{urlencode({'q': query, 'type': 'pullrequests'})})"
    return ("\n".join(rows) or f"No {state} public upstream pull requests.") + f"\n\n{link}"


def refresh():
    readme = README.read_text(encoding="utf-8")
    sections = {
        "repos": repositories(), "activity": activity(),
        "merged": pull_requests("merged"), "open": pull_requests("open"),
    }
    for name, content in sections.items():
        start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
        readme, count = re.subn(
            f"{start}.*?{end}",
            lambda _: f"{start}\n\n{content}\n\n{end}",
            readme, flags=re.DOTALL,
        )
        if count != 1:
            raise ValueError(f"Expected exactly one README section for {name}")
    README.write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    refresh()
