"""Fetch merged PRs from WordPress/gutenberg and count per-author over last 180 days.

GitHub's Search API caps each query at 1000 results, and Gutenberg merges ~2500
PRs per 6-month window. We split the window into 30-day chunks so each chunk
stays under the cap, then merge the results.
"""

import json
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = "WordPress/gutenberg"
DAYS = 180
CHUNK_DAYS = 30
OUT = Path(__file__).parent.parent / "data" / "gutenberg_prs.json"

BOT_USERS = {"dependabot", "github-actions", "renovate", "codecov"}


def gh_api(path: str) -> dict:
    result = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json", path],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def fetch_chunk(start: date, end: date, seen: set[int]) -> list[dict]:
    query = f"repo:{REPO}+is:pr+is:merged+merged:{start}..{end}"
    items = []
    page = 1
    while True:
        url = f"/search/issues?q={query}&per_page=100&page={page}&sort=created&order=desc"
        data = gh_api(url)
        batch = data.get("items", [])
        if not batch:
            break
        fresh = [p for p in batch if p["number"] not in seen]
        items.extend(fresh)
        seen.update(p["number"] for p in batch)
        total = data.get("total_count", 0)
        print(f"    page {page}: +{len(batch)} ({len(fresh)} new, chunk total {total})",
              file=sys.stderr)
        if len(batch) < 100 or page * 100 >= total or page >= 10:
            break
        page += 1
    return items


def main():
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=DAYS)
    print(f"Fetching merged PRs in {REPO} from {start_date} to {end_date} "
          f"(in {CHUNK_DAYS}-day chunks)...", file=sys.stderr)

    pr_counts: dict[str, int] = defaultdict(int)
    recent_by_user: dict[str, list] = defaultdict(list)
    seen: set[int] = set()
    total = 0

    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS - 1), end_date)
        print(f"  chunk {cursor} .. {chunk_end}", file=sys.stderr)
        items = fetch_chunk(cursor, chunk_end, seen)
        for pr in items:
            user = (pr.get("user") or {}).get("login", "").lower()
            if not user or user.endswith("[bot]") or user in BOT_USERS:
                continue
            pr_counts[user] += 1
            merged_at = pr.get("pull_request", {}).get("merged_at") or pr.get("closed_at")
            recent_by_user[user].append({
                "number": pr["number"],
                "title": pr["title"][:120],
                "merged_at": merged_at,
                "url": pr["html_url"],
            })
        total += len(items)
        cursor = chunk_end + timedelta(days=1)

    # Keep only 5 most recent per user
    for user, prs in recent_by_user.items():
        prs.sort(key=lambda p: p["merged_at"] or "", reverse=True)
        recent_by_user[user] = prs[:5]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": REPO,
        "days": DAYS,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_prs": total,
        "pr_counts": dict(pr_counts),
        "recent_prs_by_user": dict(recent_by_user),
    }, indent=2))
    print(f"Wrote {OUT}: {total} PRs, {len(pr_counts)} distinct authors", file=sys.stderr)


if __name__ == "__main__":
    main()
