#!/usr/bin/env python3
"""
Checks for repos not yet configured in site-config.json.
Opens a GitHub issue if any are found.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error


def fetch_all_repos(username, token):
    """Fetch all owned repos (public + private with token)."""
    repos = []
    page = 1
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }
    while True:
        url = f"https://api.github.com/user/repos?per_page=100&page={page}&affiliation=owner"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        if not data:
            break
        for repo in data:
            if repo["owner"]["login"] == username:
                repos.append(repo["name"])
        page += 1
    return set(repos)


def get_known_repos(config):
    """Get all repo names mentioned anywhere in config."""
    known = set()
    for entry in config.get("manual_entries", []):
        known.add(entry.get("id", ""))
    for entry in config.get("showcase", []):
        known.add(entry.get("id", ""))
    known.update(config.get("hidden", []))
    known.update(config.get("overrides", {}).keys())
    known.update(config.get("order", []))
    # Also count anything in the auto-discovered Pages list as "known"
    # (they show up automatically, user just needs to decide on showcase/hidden)
    known.discard("")
    return known


def get_open_issues(token, repo_full_name):
    """Check for existing new-repo issues."""
    url = f"https://api.github.com/repos/{repo_full_name}/issues?state=open&labels=new-repo&per_page=100"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError:
        return []


def create_issue(token, repo_full_name, new_repos):
    """Create an issue listing unconfigured repos."""
    body_lines = [
        "The following repos aren't configured in `site-config.json` yet:\n",
    ]
    for name in sorted(new_repos):
        body_lines.append(f"- [ ] **{name}** — add to `showcase`, `order`, `hidden`, or `manual_entries`")
    body_lines.append("\n---")
    body_lines.append("For each repo, decide:")
    body_lines.append("1. **showcase** — list in 'other projects' (name + description, no link)")
    body_lines.append("2. **hidden** — don't show it at all")
    body_lines.append("3. **manual_entries** — show with a custom link")
    body_lines.append("4. Do nothing — if it has Pages, it auto-appears in the main list")
    body_lines.append("\nEdit `site-config.json` and close this issue when done.")

    data = json.dumps({
        "title": f"Configure {len(new_repos)} new repo(s) for personal directory",
        "body": "\n".join(body_lines),
        "labels": ["new-repo"],
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo_full_name}/issues",
        data=data,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        issue = json.loads(resp.read())
    return issue["html_url"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--config", default="site-config.json")
    args = parser.parse_args()

    username = "jkraybill"
    repo_full_name = f"{username}/{username}.github.io"

    with open(args.config) as f:
        config = json.load(f)

    all_repos = fetch_all_repos(username, args.token)
    known = get_known_repos(config)

    # Repos with Pages are auto-discovered, so fetch those too
    pages_repos = set()
    page = 1
    while True:
        url = f"https://api.github.com/user/repos?per_page=100&page={page}&affiliation=owner"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {args.token}",
        })
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        if not data:
            break
        for repo in data:
            if repo["owner"]["login"] == username and repo.get("has_pages"):
                pages_repos.add(repo["name"])
        page += 1

    new_repos = all_repos - known - pages_repos
    # Also exclude the site repo itself
    new_repos.discard(f"{username}.github.io")

    if not new_repos:
        print("All repos are configured.")
        return

    print(f"Found {len(new_repos)} unconfigured repo(s): {', '.join(sorted(new_repos))}")

    # Check if there's already an open issue
    open_issues = get_open_issues(args.token, repo_full_name)
    if open_issues:
        print(f"Open issue already exists: {open_issues[0]['html_url']}")
        # Update existing issue body
        issue_num = open_issues[0]["number"]
        # Just print, don't create a duplicate
        return

    url = create_issue(args.token, repo_full_name, new_repos)
    print(f"Created issue: {url}")


if __name__ == "__main__":
    main()
