"""Join all data sources with the manual sponsor mapping and render the site.

Score = core_props + gutenberg_prs. No weighting, kept transparent.

Sources merged, in priority order per field:
  1. data/contributors.yaml   (hand-curated, authoritative)
  2. data/profiles_cache.json (auto-scraped from profiles.wordpress.org)
  3. data/sponsors_cache.json (auto-verified via GitHub GraphQL)
  4. data/core_commits.json   (wp.org props counts)
  5. data/gutenberg_prs.json  (GitHub PR counts)
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
TEMPLATES = ROOT / "templates"

WPORG_REDIRECT_RE = re.compile(r"^https?://profiles\.wordpress\.org/website-redirect/")


def load():
    core = json.loads((DATA / "core_commits.json").read_text())
    gb = json.loads((DATA / "gutenberg_prs.json").read_text())
    manual = yaml.safe_load((DATA / "contributors.yaml").read_text()) or {}
    profiles = _load_optional("profiles_cache.json")
    sponsors = _load_optional("sponsors_cache.json")
    return core, gb, manual, profiles, sponsors


def _load_optional(name: str) -> dict:
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else {}


def clean_website(url: str | None) -> str | None:
    if not url:
        return None
    if WPORG_REDIRECT_RE.match(url):
        # wp.org wraps external links in a redirector; the underlying
        # URL isn't exposed in the markup, but the redirector still works.
        return url
    return url


def resolve_info(handle: str, manual: dict, profiles: dict) -> dict:
    """Merge manual + profile-scraped data. Manual wins."""
    auto = profiles.get(handle) or {}
    m = manual.get(handle) or {}
    return {
        "name": m.get("name") or auto.get("name") or handle,
        "github": m.get("github") or auto.get("github"),
        "website": m.get("website") or clean_website(auto.get("website")),
        "employer": m.get("employer") or auto.get("company"),
        "location": auto.get("location"),
        "job": auto.get("job"),
        "github_sponsors_manual": m.get("github_sponsors"),
        "open_collective": m.get("open_collective"),
        "ko_fi": m.get("ko_fi"),
        "buy_me_a_coffee": m.get("buy_me_a_coffee"),
        "liberapay": m.get("liberapay"),
        "patreon": m.get("patreon"),
    }


def sponsor_links(info: dict, sponsors: dict) -> list[dict]:
    links = []
    github = (info.get("github") or "").lower()
    gh_sponsors_live = sponsors.get(github)
    if gh_sponsors_live is True or (gh_sponsors_live is None and info.get("github_sponsors_manual")):
        if github:
            links.append({
                "label": "GitHub Sponsors",
                "url": f"https://github.com/sponsors/{info['github']}",
                "platform": "github",
            })
    if info.get("open_collective"):
        links.append({
            "label": "Open Collective", "platform": "opencollective",
            "url": f"https://opencollective.com/{info['open_collective']}",
        })
    if info.get("ko_fi"):
        links.append({
            "label": "Ko-fi", "platform": "kofi",
            "url": f"https://ko-fi.com/{info['ko_fi']}",
        })
    if info.get("buy_me_a_coffee"):
        links.append({
            "label": "Buy Me a Coffee", "platform": "bmc",
            "url": f"https://buymeacoffee.com/{info['buy_me_a_coffee']}",
        })
    if info.get("liberapay"):
        links.append({
            "label": "Liberapay", "platform": "liberapay",
            "url": f"https://liberapay.com/{info['liberapay']}",
        })
    if info.get("patreon"):
        links.append({
            "label": "Patreon", "platform": "patreon",
            "url": f"https://patreon.com/{info['patreon']}",
        })
    return links


def build_rows(core, gb, manual, profiles, sponsors):
    gb_by_github = {k.lower(): v for k, v in gb["pr_counts"].items()}
    gb_recent_by_github = {k.lower(): v for k, v in gb["recent_prs_by_user"].items()}

    # Union of handles: core props keys, manual entries, profile cache entries.
    handles = (
        set(core["props_counts"].keys())
        | set(manual.keys())
        | set(profiles.keys())
    )
    # Reverse-lookup: which github logins are already claimed by a wp.org handle
    claimed_github: set[str] = set()
    for h in handles:
        info = resolve_info(h, manual, profiles)
        if info["github"]:
            claimed_github.add(info["github"].lower())
    # Add unclaimed Gutenberg-only contributors by github login
    for gh_login in gb_by_github:
        if gh_login not in claimed_github:
            handles.add(gh_login)

    rows = []
    for h in handles:
        info = resolve_info(h, manual, profiles)
        github = (info["github"] or h).lower()
        core_n = core["props_counts"].get(h, 0)
        gb_n = gb_by_github.get(github, 0)
        if core_n == 0 and gb_n == 0:
            continue
        is_wporg_handle = h in core["props_counts"] or h in manual or h in profiles
        rows.append({
            "handle": h,
            "is_wporg_handle": is_wporg_handle,
            "name": info["name"],
            "github": info["github"] or (h if not is_wporg_handle and gb_n else None),
            "employer": info["employer"],
            "location": info["location"],
            "job": info["job"],
            "website": info["website"],
            "core_props": core_n,
            "gutenberg_prs": gb_n,
            "score": core_n + gb_n,
            "sponsor_links": sponsor_links(info, sponsors),
            "recent_core": core["recent_commits_by_handle"].get(h, [])[:3],
            "recent_gb": gb_recent_by_github.get(github, [])[:3],
            "wporg_profile": f"https://profiles.wordpress.org/{h}/" if is_wporg_handle else None,
        })

    rows.sort(key=lambda r: (-r["score"], -r["core_props"], r["handle"]))
    return rows


def main():
    core, gb, manual, profiles, sponsors = load()
    rows = build_rows(core, gb, manual, profiles, sponsors)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("index.html.j2")
    mapped_handles = set(manual.keys()) | {
        h for h, info in profiles.items() if info.get("github")
    }
    html = tmpl.render(
        rows=rows,
        core_total=core["total_commits"],
        gb_total=gb["total_prs"],
        days=core["days"],
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        sponsored_count=sum(1 for r in rows if r["sponsor_links"]),
        mapped_count=sum(1 for r in rows if r["handle"] in mapped_handles),
        mapped_handles=mapped_handles,
    )
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(html)
    print(f"Wrote {SITE / 'index.html'} ({len(rows)} contributors, "
          f"{sum(1 for r in rows if r['sponsor_links'])} with sponsor links)")


if __name__ == "__main__":
    main()
