#!/usr/bin/env python3
"""
Builds index.html from GitHub Pages repos + manual config.

Usage:
  python build.py                  # uses GITHUB_TOKEN env var
  python build.py --token TOKEN    # explicit token
  python build.py --dry-run        # skip API, use only config
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


def fetch_pages_repos(username, token=None):
    """Fetch all repos with GitHub Pages enabled."""
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&page={page}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            print(f"Warning: GitHub API returned {e.code}, using config-only mode", file=sys.stderr)
            return []
        if not data:
            break
        for repo in data:
            if repo.get("has_pages") and not repo.get("fork"):
                repos.append({
                    "id": repo["name"],
                    "name": repo["name"],
                    "url": f"https://{username}.github.io/{repo['name']}/",
                    "description": repo.get("description") or "",
                    "source": "github",
                    "stars": repo.get("stargazers_count", 0),
                    "updated": repo.get("pushed_at", ""),
                })
        page += 1
    return repos


def build_entries(config, api_repos):
    """Merge API repos + manual entries, apply overrides and ordering."""
    username = "jkraybill"
    hidden = set(config.get("hidden", []))
    overrides = config.get("overrides", {})
    order = config.get("order", [])
    manual = config.get("manual_entries", [])
    showcase_ids = {s["id"] for s in config.get("showcase", []) if "id" in s}

    # Build lookup of API repos by id
    entries = {}
    for repo in api_repos:
        if repo["id"] in hidden or repo["id"] in showcase_ids:
            continue
        entry = repo.copy()
        if repo["id"] in overrides:
            entry.update(overrides[repo["id"]])
            entry["url"] = repo["url"]  # don't override url from overrides
        entries[repo["id"]] = entry

    # Add manual entries
    for m in manual:
        if m.get("id") in hidden:
            continue
        entry = m.copy()
        entry["source"] = "manual"
        entries[m["id"]] = entry

    # Apply ordering: ordered items first, then remainder alphabetically
    ordered = []
    seen = set()
    for item_id in order:
        if item_id in entries:
            ordered.append(entries[item_id])
            seen.add(item_id)
    remainder = sorted(
        [e for eid, e in entries.items() if eid not in seen],
        key=lambda e: e["name"].lower()
    )
    return ordered + remainder


def render_html(config, entries):
    """Render the index page."""
    title = config.get("title", "jkraybill")
    subtitle = config.get("subtitle", "projects & pages")
    showcase = config.get("showcase", [])
    now = datetime.now(timezone.utc).strftime("%b %d, %Y")

    cards_html = ""
    for entry in entries:
        badge = ""
        if entry.get("source") == "github":
            badge = '<span class="badge gh">pages</span>'
        else:
            badge = '<span class="badge manual">link</span>'

        desc = entry.get("description", "")
        desc_html = f'<p class="desc">{desc}</p>' if desc else ''

        cards_html += f"""
      <a href="{entry['url']}" class="card" target="_blank" rel="noopener">
        <div class="card-header">
          <h2>{entry['name']}</h2>
          {badge}
        </div>
        {desc_html}
      </a>"""

    # Render showcase section (private repos, no links, with group headings)
    showcase_html = ""
    if showcase:
        showcase_html += """
    <div class="section-divider">
      <h3 class="section-title">other projects</h3>
    </div>"""
        in_group = False
        for item in showcase:
            if "group" in item:
                if in_group:
                    showcase_html += """
    </div>"""
                showcase_html += f"""
    <div class="showcase-group">{item['group']}</div>
    <div class="showcase">"""
                in_group = True
            elif "id" in item:
                desc = item.get("description", "")
                desc_html = f'<span class="showcase-desc"> &mdash; {desc}</span>' if desc else ''
                showcase_html += f"""
      <div class="showcase-item">
        <span class="showcase-name">{item['name']}</span>{desc_html}
      </div>"""
        if in_group:
            showcase_html += """
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0f1117;
      --surface: #1a1d27;
      --surface-hover: #242736;
      --border: #2a2d3a;
      --text: #e2e4ea;
      --text-dim: #8b8fa3;
      --accent: #6c8aff;
      --accent-dim: #4a5a99;
      --gh-badge: #2ea04370;
      --gh-badge-text: #58d68d;
      --manual-badge: #6c8aff30;
      --manual-badge-text: #8ba4ff;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 0 1rem;
    }}

    .container {{
      max-width: 640px;
      margin: 0 auto;
      padding: 4rem 0 3rem;
    }}

    header {{
      margin-bottom: 2.5rem;
    }}

    header h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      margin-bottom: 0.25rem;
    }}

    header .subtitle {{
      color: var(--text-dim);
      font-size: 0.95rem;
    }}

    .cards {{
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }}

    .card {{
      display: block;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.25rem;
      text-decoration: none;
      color: var(--text);
      transition: background 0.15s, border-color 0.15s, transform 0.1s;
    }}

    .card:hover {{
      background: var(--surface-hover);
      border-color: var(--accent-dim);
      transform: translateY(-1px);
    }}

    .card-header {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}

    .card h2 {{
      font-size: 1rem;
      font-weight: 600;
      letter-spacing: -0.01em;
    }}

    .badge {{
      font-size: 0.7rem;
      font-weight: 600;
      padding: 0.15rem 0.5rem;
      border-radius: 99px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      flex-shrink: 0;
    }}

    .badge.gh {{
      background: var(--gh-badge);
      color: var(--gh-badge-text);
    }}

    .badge.manual {{
      background: var(--manual-badge);
      color: var(--manual-badge-text);
    }}

    .desc {{
      color: var(--text-dim);
      font-size: 0.875rem;
      margin-top: 0.35rem;
      line-height: 1.4;
    }}

    .section-divider {{
      margin-top: 2.5rem;
      margin-bottom: 1rem;
    }}

    .section-title {{
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-dim);
    }}

    .showcase-group {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--accent);
      margin-top: 1.25rem;
      margin-bottom: 0.4rem;
      padding-left: 0.1rem;
    }}

    .showcase {{
      display: flex;
      flex-direction: column;
      gap: 0.1rem;
    }}

    .showcase-item {{
      padding: 0.55rem 0;
      border-bottom: 1px solid var(--border);
      font-size: 0.9rem;
      line-height: 1.4;
    }}

    .showcase-item:last-child {{
      border-bottom: none;
    }}

    .showcase-name {{
      font-weight: 600;
      color: var(--text);
    }}

    .showcase-desc {{
      color: var(--text-dim);
    }}

    footer {{
      margin-top: 3rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border);
      color: var(--text-dim);
      font-size: 0.8rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    footer a {{
      color: var(--accent);
      text-decoration: none;
    }}

    footer a:hover {{
      text-decoration: underline;
    }}

    @media (max-width: 480px) {{
      .container {{ padding: 2.5rem 0 2rem; }}
      header h1 {{ font-size: 1.5rem; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>{title}</h1>
      <div class="subtitle">{subtitle}</div>
    </header>
    <div class="cards">{cards_html}
    </div>{showcase_html}
    <footer>
      <span>updated {now}</span>
      <a href="https://github.com/jkraybill">github.com/jkraybill</a>
    </footer>
  </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", default="site-config.json")
    parser.add_argument("--output", default="index.html")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    if args.dry_run:
        api_repos = []
    else:
        api_repos = fetch_pages_repos("jkraybill", args.token or None)

    entries = build_entries(config, api_repos)
    html = render_html(config, entries)

    with open(args.output, "w") as f:
        f.write(html)

    print(f"Built {args.output} with {len(entries)} entries")


if __name__ == "__main__":
    main()
