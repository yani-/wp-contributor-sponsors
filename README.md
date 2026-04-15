# WordPress Contributor Sponsors

[![Build and deploy](https://github.com/yani-/wp-contributor-sponsors/actions/workflows/build.yml/badge.svg)](https://github.com/yani-/wp-contributor-sponsors/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**A directory of individual contributors to WordPress Core and Gutenberg, ranked by contribution activity, with direct sponsorship links.**

Live site: **https://yani-.github.io/wp-contributor-sponsors/**

The goal is to recognize and enable direct support of the *people* who ship WordPress, not just the companies that employ them. It was built to explore an idea raised on the WordPress.org Slack: what if `.org` had a first-class way to surface individual contributor sponsorship?

## Contents

1. [What's in the directory](#whats-in-the-directory)
2. [How the data is collected](#how-the-data-is-collected)
3. [Local development](#local-development)
4. [Adding yourself to the directory](#adding-yourself-to-the-directory)
5. [Auto-deploy](#auto-deploy)
6. [Known limitations](#known-limitations)
7. [Project layout](#project-layout)
8. [Contributing](#contributing)
9. [License](#license)

## What's in the directory

For every person who has had props on a Core commit or merged a PR in Gutenberg in the last 180 days, the site shows:

* Name, wp.org handle, GitHub handle, website, employer, and location, pulled from their public wp.org profile.
* A contribution score (`core_props + gutenberg_prs`), with the raw counts broken out as chips.
* Recent activity: the three most recent Core commits they were propped on plus the three most recent Gutenberg PRs they merged.
* Sponsor buttons for any platforms they've listed: GitHub Sponsors, Open Collective, Ko-fi, Buy Me a Coffee, Liberapay, Patreon.

Client-side filters let you narrow by minimum contribution thresholds, show only contributors who accept sponsorships, or search by name or handle. Filter state is shareable via URL.

## How the data is collected

Everything is derived from **public** sources. No authenticated wp.org access, no private APIs, no database. The five-stage pipeline runs on GitHub Actions once a week (and on every push) and writes JSON caches that the site builder joins together.

### Stage 1: WordPress Core commits

Script: [`scripts/fetch_core.py`](scripts/fetch_core.py)

Core is developed in SVN on `develop.svn.wordpress.org`, but it's mirrored read-only to [`github.com/WordPress/wordpress-develop`](https://github.com/WordPress/wordpress-develop). The mirror preserves the full commit message, which by long-standing convention includes a `Props ...` line attributing contributors:

```
REST API: Harden Real Time Collaboration endpoint.

Props westonruter, sergeybiryukov, desrosj.
See #62234.
```

The script pulls every commit in the last 180 days via the GitHub REST API (`/repos/WordPress/wordpress-develop/commits`), applies this regex to each message:

```python
PROPS_RE = re.compile(r"^\s*Props[:\s]+(.+?)(?:\.\s*$|$)", re.IGNORECASE | re.MULTILINE)
```

splits the handles, lowercases them, and tallies per-contributor counts plus the three most recent commits for each. The result is written to `data/core_commits.json`.

Typical output: roughly 1,000 commits and 600 distinct handles.

### Stage 2: Gutenberg pull requests

Script: [`scripts/fetch_gutenberg.py`](scripts/fetch_gutenberg.py)

Gutenberg development happens on GitHub, so PRs are the equivalent signal. The script queries the GitHub Search API for merged PRs in `WordPress/gutenberg`. One subtlety: Search caps each query at 1,000 results, and Gutenberg typically merges about 2,500 PRs in a 6-month window. The script works around this by **chunking the window into 30-day sub-ranges** (`merged:YYYY-MM-DD..YYYY-MM-DD`) and de-duplicating by PR number across chunks.

Bots are filtered (`dependabot`, `github-actions`, `renovate`, `codecov`, anything ending in `[bot]`). The result is written to `data/gutenberg_prs.json`.

Typical output: roughly 2,500 PRs and 200 distinct authors.

### Stage 3: wp.org profile scraping

Script: [`scripts/scrape_profiles.py`](scripts/scrape_profiles.py)

`profiles.wordpress.org/{handle}/` is a public page per WordPress user with structured `<li id="user-*">` blocks:

```html
<li id="user-github">
  <span>GitHub:</span>
  <strong><a href="https://github.com/westonruter">westonruter</a></strong>
</li>
```

The script fetches the top 300 contributors by combined score, parses these blocks with simple regexes, and caches the result in `data/profiles_cache.json`. Fields extracted: name, `github`, `website`, `company`, `job`, and `location`. Requests are rate-limited to 0.6 seconds apart to be polite. Re-runs are cheap because cached handles are skipped.

This is what lets the site auto-link around 235 wp.org handles to their GitHub accounts without anyone editing YAML.

### Stage 4: GitHub Sponsors verification

Script: [`scripts/verify_sponsors.py`](scripts/verify_sponsors.py)

For every GitHub login discovered in stages 2 and 3, the script asks GitHub's GraphQL API whether that user has an active Sponsors listing:

```graphql
{
  u_westonruter: user(login: "westonruter") { hasSponsorsListing }
  u_mirka:       user(login: "mirka")       { hasSponsorsListing }
  u_mamaduka:    user(login: "Mamaduka")    { hasSponsorsListing }
  # batched 50 per query via GraphQL aliases
}
```

Result cached to `data/sponsors_cache.json` as `{login: true|false|null}` (null means the user was not found, renamed, or deleted). Typical output: about 34 of the top 340 contributors have active GitHub Sponsors listings.

This means the site doesn't need anyone to manually claim "I accept sponsors". If you have a listing, it shows up automatically.

### Stage 5: Join and render

Script: [`scripts/build_site.py`](scripts/build_site.py)

Merges all four caches with `data/contributors.yaml` (the manual override layer), deduplicates across handles (for example, `wildworks` on wp.org matches `t-hamano` on GitHub), and renders [`templates/index.html.j2`](templates/index.html.j2).

Merge priority for each field (first non-empty wins):

```
data/contributors.yaml  >  data/profiles_cache.json  >  inferred defaults
```

Sponsor links come from both sources: manual entries in `contributors.yaml` (for non-GitHub platforms) unioned with live-verified GitHub Sponsors hits.

## Local development

Prerequisites: Python 3.10+, [`gh` CLI](https://cli.github.com/) logged in (`gh auth status` should be green).

```bash
git clone https://github.com/yani-/wp-contributor-sponsors.git
cd wp-contributor-sponsors

python3 -m venv .venv && source .venv/bin/activate
pip install requests pyyaml jinja2

python scripts/fetch_core.py        # about 30s
python scripts/fetch_gutenberg.py   # about 90s
python scripts/scrape_profiles.py   # about 3min (cached on re-run)
python scripts/verify_sponsors.py   # about 15s
python scripts/build_site.py        # instant

open site/index.html
```

Only `scripts/build_site.py` and `templates/index.html.j2` need to re-run when iterating on design. The fetcher caches are plain JSON and reusable.

## Adding yourself to the directory

If you contribute to WordPress Core or Gutenberg, your wp.org handle and GitHub handle (from your wp.org profile) are already here. If you have a GitHub Sponsors listing, the sponsor button is already there too.

**The only reason to edit anything manually** is to add a non-GitHub sponsor platform, override a detected value (wrong display name, etc.), or surface an employer.

Edit [`data/contributors.yaml`](data/contributors.yaml):

```yaml
yourwporghandle:
  name: Your Display Name         # optional, falls back to profile data
  github: yourgithubhandle        # optional, auto-detected from profile
  github_sponsors: true           # optional, auto-verified via GraphQL
  open_collective: your-slug      # opencollective.com/your-slug
  ko_fi: your-slug                # ko-fi.com/your-slug
  buy_me_a_coffee: your-slug      # buymeacoffee.com/your-slug
  liberapay: your-slug            # liberapay.com/your-slug
  patreon: your-slug              # patreon.com/your-slug
  website: https://example.com    # optional override
  employer: Company Name          # optional, shown as secondary metadata
```

Submit a PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full flow.

## Auto-deploy

[`.github/workflows/build.yml`](.github/workflows/build.yml) runs the full pipeline and deploys `site/` to GitHub Pages:

* On every push to `main`.
* Weekly, Mondays at 06:00 UTC.
* On manual dispatch (`Actions` tab, then `Build and deploy`, then `Run workflow`).

The workflow uses the default `GITHUB_TOKEN` for API calls, which is enough headroom for all stages combined.

## Known limitations

* **Scope.** Only Core and Gutenberg are counted. Docs, design, translations, community support, plugin/theme repo contributions, Trac triage, Meta team work, and many other forms of contribution are not captured. Contribution counts are a *signal*, not a complete picture. This is called out in the site footer.
* **Profile scraping covers the top 300.** Lower-ranked contributors still appear in the directory but without auto-enriched data. Raise the cap in `scripts/scrape_profiles.py` if you want wider coverage, at the cost of more HTTP requests.
* **GitHub Sponsors is the only auto-verified platform.** Open Collective, Ko-fi, Patreon, Liberapay, and Buy Me a Coffee require manual entry in `contributors.yaml`.
* **Rate limits.** The pipeline makes around 50 authenticated GitHub requests and 300 unauthenticated wp.org requests per full run. Well within limits for a weekly cron.

## Project layout

```
├── scripts/
│   ├── fetch_core.py          Core commits and props parsing
│   ├── fetch_gutenberg.py     Gutenberg merged PRs, chunked by date
│   ├── scrape_profiles.py     profiles.wordpress.org enrichment
│   ├── verify_sponsors.py     GitHub GraphQL Sponsors check
│   └── build_site.py          Join and render
├── templates/
│   └── index.html.j2          The UI (Jinja2, vanilla CSS and JS, no framework)
├── data/
│   ├── contributors.yaml      Manual overrides (committed)
│   ├── core_commits.json      Generated (gitignored)
│   ├── gutenberg_prs.json     Generated (gitignored)
│   ├── profiles_cache.json    Generated (gitignored)
│   └── sponsors_cache.json    Generated (gitignored)
├── site/
│   └── index.html             Generated (gitignored, served from Pages)
├── .github/
│   ├── workflows/build.yml    CI pipeline and Pages deploy
│   ├── ISSUE_TEMPLATE/        Bug, feature, data-correction templates
│   └── PULL_REQUEST_TEMPLATE.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── LICENSE
└── README.md
```

## Contributing

This is a small project with a clear scope. PRs are welcome for:

* Adding or correcting entries in `data/contributors.yaml`.
* Improving data accuracy (better props parsing, bot filtering, handle matching).
* New sponsor platforms.
* Design and accessibility improvements.
* Widening the pipeline to cover other WordPress repos (themes team, docs, etc.).

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

Have an idea or found a bug? [Open an issue](https://github.com/yani-/wp-contributor-sponsors/issues/new/choose).

## License

[MIT](LICENSE) © 2026 Yani Iliev.
