"""Fetch WordPress Core commits from the GitHub mirror and count props per contributor.

The Core SVN repo is mirrored to github.com/WordPress/wordpress-develop. Commit
messages preserve the full SVN message, which includes "Props user1, user2, ..."
lines attributing contributors. We parse those.
"""

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "WordPress/wordpress-develop"
DAYS = 180
OUT = Path(__file__).parent.parent / "data" / "core_commits.json"

PROPS_RE = re.compile(r"^\s*Props[:\s]+(.+?)(?:\.\s*$|$)", re.IGNORECASE | re.MULTILINE)
HANDLE_SPLIT_RE = re.compile(r"[,\s]+(?:and\s+)?")


def gh_api(path: str) -> dict | list:
    result = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json", path],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def parse_props(message: str) -> list[str]:
    handles = []
    for match in PROPS_RE.finditer(message):
        chunk = match.group(1).strip().rstrip(".")
        # stop at the first line break (props lines are one line)
        chunk = chunk.split("\n")[0]
        for raw in HANDLE_SPLIT_RE.split(chunk):
            h = raw.strip().strip(".,;").lstrip("@")
            # filter obvious non-handles
            if h and re.match(r"^[a-zA-Z0-9_.\-]+$", h) and len(h) <= 40:
                handles.append(h.lower())
    return handles


def fetch_commits():
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS)).isoformat()
    commits = []
    page = 1
    while True:
        batch = gh_api(f"/repos/{REPO}/commits?since={since}&per_page=100&page={page}")
        if not batch:
            break
        commits.extend(batch)
        print(f"  page {page}: +{len(batch)} (total {len(commits)})", file=sys.stderr)
        if len(batch) < 100:
            break
        page += 1
    return commits


def main():
    print(f"Fetching {REPO} commits from last {DAYS} days...", file=sys.stderr)
    commits = fetch_commits()

    props_counts: dict[str, int] = defaultdict(int)
    committer_counts: dict[str, int] = defaultdict(int)
    recent_commits_by_handle: dict[str, list] = defaultdict(list)

    for c in commits:
        msg = c["commit"]["message"]
        sha = c["sha"]
        date = c["commit"]["author"]["date"]
        committer = (c["commit"]["author"]["name"] or "").lower()
        if committer:
            committer_counts[committer] += 1

        for handle in parse_props(msg):
            props_counts[handle] += 1
            if len(recent_commits_by_handle[handle]) < 5:
                recent_commits_by_handle[handle].append({
                    "sha": sha[:10],
                    "date": date,
                    "summary": msg.split("\n")[0][:120],
                })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": REPO,
        "days": DAYS,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_commits": len(commits),
        "props_counts": dict(props_counts),
        "committer_counts": dict(committer_counts),
        "recent_commits_by_handle": dict(recent_commits_by_handle),
    }, indent=2))
    print(f"Wrote {OUT}: {len(commits)} commits, {len(props_counts)} distinct contributors",
          file=sys.stderr)


if __name__ == "__main__":
    main()
