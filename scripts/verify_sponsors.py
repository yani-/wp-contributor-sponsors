"""Query GitHub GraphQL to check who has an active Sponsors listing.

We batch lookups (50 users per query) via GraphQL aliases for efficiency.
Input: every GitHub username we know about (from profiles_cache.json, the
gutenberg PR list, and contributors.yaml). Output: data/sponsors_cache.json
with {github_login_lower: bool}.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
CACHE = DATA / "sponsors_cache.json"
BATCH = 50


def gh_graphql(query: str) -> dict:
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # GraphQL can return partial data with errors (e.g. missing users).
        # Try to parse anyway.
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"gh graphql failed: {result.stderr}")
    return json.loads(result.stdout)


def gather_logins() -> set[str]:
    logins: set[str] = set()

    profiles = json.loads((DATA / "profiles_cache.json").read_text())
    for info in profiles.values():
        gh = info.get("github")
        if gh:
            logins.add(gh.lower())

    gb = json.loads((DATA / "gutenberg_prs.json").read_text())
    for u in gb["pr_counts"]:
        logins.add(u.lower())

    contribs = yaml.safe_load((DATA / "contributors.yaml").read_text()) or {}
    for info in contribs.values():
        gh = (info or {}).get("github")
        if gh:
            logins.add(gh.lower())

    return logins


def sanitize(login: str) -> str | None:
    """GraphQL aliases must match [A-Za-z_][A-Za-z0-9_]*."""
    if not login or not login[0].isalpha():
        return None
    clean = "".join(c if c.isalnum() else "_" for c in login)
    return "u_" + clean


def check_batch(logins: list[str]) -> dict[str, bool | None]:
    alias_to_login = {}
    parts = []
    for lg in logins:
        alias = sanitize(lg)
        if not alias:
            continue
        alias_to_login[alias] = lg
        parts.append(f'{alias}: user(login: "{lg}") {{ hasSponsorsListing }}')
    if not parts:
        return {}
    query = "{ " + " ".join(parts) + " }"
    try:
        resp = gh_graphql(query)
    except RuntimeError as e:
        print(f"  batch failed: {e}", file=sys.stderr)
        return {lg: None for lg in logins}

    out: dict[str, bool | None] = {}
    data = (resp or {}).get("data") or {}
    for alias, login in alias_to_login.items():
        node = data.get(alias)
        if node is None:
            out[login] = None  # user not found / renamed / deleted
        else:
            out[login] = bool(node.get("hasSponsorsListing"))
    return out


def main():
    logins = sorted(gather_logins())
    print(f"Checking sponsor listing status for {len(logins)} GitHub users "
          f"in batches of {BATCH}...", file=sys.stderr)

    cache: dict[str, bool | None] = {}
    for i in range(0, len(logins), BATCH):
        chunk = logins[i : i + BATCH]
        result = check_batch(chunk)
        cache.update(result)
        yes = sum(1 for v in result.values() if v)
        print(f"  batch {i // BATCH + 1}: {yes}/{len(chunk)} sponsorable "
              f"(running total {sum(1 for v in cache.values() if v)})",
              file=sys.stderr)

    CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True))
    sponsorable = sorted(lg for lg, v in cache.items() if v)
    print(f"Wrote {CACHE}: {len(sponsorable)} sponsorable on GitHub Sponsors",
          file=sys.stderr)
    if sponsorable:
        print("Top sponsorable: " + ", ".join(sponsorable[:20]), file=sys.stderr)


if __name__ == "__main__":
    main()
