"""Scrape profiles.wordpress.org/{handle}/ to extract GitHub, website, company, location.

Profile pages expose structured <li id="user-*"> blocks. We parse with regex.
The structure is simple and stable enough that BeautifulSoup would be overkill.

Only scrapes top-N contributors by combined score to stay polite. Caches results
to data/profiles_cache.json so re-runs are cheap.
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
CACHE = DATA / "profiles_cache.json"
TOP_N = 300  # scrape the top 300 by combined score
SLEEP = 0.6  # seconds between requests (polite rate)

UA = "wp-contributor-sponsors/0.1 (+https://github.com/WordPress research)"

FIELD_RE = {
    "github": re.compile(
        r'id="user-github".*?href="https://github\.com/([^"/?#]+)"',
        re.DOTALL,
    ),
    "website": re.compile(
        r'id="user-website".*?href="([^"]+)"',
        re.DOTALL,
    ),
    "company": re.compile(
        r'id="user-company".*?<strong>([^<]+)</strong>',
        re.DOTALL,
    ),
    "job": re.compile(
        r'id="user-job".*?<strong>([^<]+)</strong>',
        re.DOTALL,
    ),
    "location": re.compile(
        r'id="user-location".*?<strong>([^<]+)</strong>',
        re.DOTALL,
    ),
}
NAME_RE = re.compile(r"<title>([^(<]+?)\s*\(@[^)]+\)", re.IGNORECASE)


def parse(html: str) -> dict:
    out = {}
    m = NAME_RE.search(html)
    if m:
        out["name"] = m.group(1).strip()
    for field, rx in FIELD_RE.items():
        m = rx.search(html)
        if m:
            out[field] = m.group(1).strip()
    return out


def load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True))


def top_handles() -> list[str]:
    core = json.loads((DATA / "core_commits.json").read_text())
    gb = json.loads((DATA / "gutenberg_prs.json").read_text())
    scores: dict[str, int] = {}
    for h, n in core["props_counts"].items():
        scores[h] = scores.get(h, 0) + n
    # Gutenberg uses GitHub handle, not wp.org. We still scrape those too
    # so we can reverse-map later.
    for u, n in gb["pr_counts"].items():
        scores[u.lower()] = scores.get(u.lower(), 0) + n
    return [h for h, _ in sorted(scores.items(), key=lambda x: -x[1])][:TOP_N]


def main():
    cache = load_cache()
    handles = top_handles()
    sess = requests.Session()
    sess.headers["User-Agent"] = UA

    scraped = 0
    hits = 0
    for i, handle in enumerate(handles, 1):
        if handle in cache:
            if cache[handle].get("github"):
                hits += 1
            continue
        url = f"https://profiles.wordpress.org/{handle}/"
        try:
            r = sess.get(url, timeout=10)
        except requests.RequestException as e:
            print(f"  [{i}/{len(handles)}] {handle}: request failed ({e})", file=sys.stderr)
            cache[handle] = {"error": str(e)}
            continue
        if r.status_code == 404:
            cache[handle] = {"not_found": True}
            print(f"  [{i}/{len(handles)}] {handle}: 404", file=sys.stderr)
        elif r.status_code == 200:
            info = parse(r.text)
            cache[handle] = info
            scraped += 1
            if info.get("github"):
                hits += 1
                print(f"  [{i}/{len(handles)}] {handle} -> github:{info['github']}"
                      f"{' site:' + info['website'] if info.get('website') else ''}",
                      file=sys.stderr)
            else:
                print(f"  [{i}/{len(handles)}] {handle}: no github on profile",
                      file=sys.stderr)
        else:
            cache[handle] = {"status": r.status_code}
            print(f"  [{i}/{len(handles)}] {handle}: HTTP {r.status_code}", file=sys.stderr)

        if scraped and scraped % 25 == 0:
            save_cache(cache)
        time.sleep(SLEEP)

    save_cache(cache)
    print(f"Done. Scraped {scraped} new profiles, {hits} have GitHub links "
          f"(cache: {CACHE})", file=sys.stderr)


if __name__ == "__main__":
    main()
