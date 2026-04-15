# Contributing

Thanks for your interest in improving the WordPress Contributor Sponsors directory. This doc covers the most common contribution paths.

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Table of contents

1. [Add or update your own entry](#add-or-update-your-own-entry)
2. [Report inaccurate data](#report-inaccurate-data)
3. [Propose a feature or design change](#propose-a-feature-or-design-change)
4. [Submit a code contribution](#submit-a-code-contribution)
5. [Running the pipeline locally](#running-the-pipeline-locally)
6. [What's in scope, what's not](#whats-in-scope-whats-not)

## Add or update your own entry

This is the most common reason someone will open a PR. You don't need to be a developer. Editing one YAML file is enough.

1. Fork the repo.
2. Open [`data/contributors.yaml`](data/contributors.yaml).
3. Find your wp.org handle, or add a new top-level entry keyed by your handle (lowercase):

   ```yaml
   yourwporghandle:
     name: Your Display Name
     github: yourgithubhandle
     github_sponsors: true          # only if you have github.com/sponsors/you
     open_collective: your-slug     # opencollective.com/your-slug
     ko_fi: your-slug               # ko-fi.com/your-slug
     buy_me_a_coffee: your-slug     # buymeacoffee.com/your-slug
     liberapay: your-slug           # liberapay.com/your-slug
     patreon: your-slug             # patreon.com/your-slug
     website: https://example.com
     employer: Company Name
   ```

4. **Only include fields you want displayed.** Every field is optional. Missing fields fall back to whatever the scraper found on your wp.org profile.
5. Submit a PR. **Only add or edit your own entry** unless you've been asked.

GitHub Sponsors listings are auto-verified via GraphQL each build, so `github_sponsors: true` is only needed as a hint, and will get double-checked in CI.

If you'd rather not edit YAML, [open an issue using the "Add or update my entry" template](https://github.com/yani-/wp-contributor-sponsors/issues/new/choose) and a maintainer will do it for you.

## Report inaccurate data

The pipeline gets most things right automatically, but not everything. If something looks wrong (wrong display name, wrong employer, wrong GitHub handle, missing props count, miscounted PRs, anything), please open a **Data correction** issue. Include:

* The wp.org handle affected.
* What's currently shown.
* What it should be.
* A source for the correct value if it's not obvious (for example, a link to the wp.org profile).

For anything related to someone *else's* data, only include publicly available information. Don't add private info on someone's behalf.

## Propose a feature or design change

Open a **Feature request** issue first so we can discuss scope before you invest time in a PR. Good fits:

* New sponsor platforms.
* Better handle and identity matching heuristics.
* Accessibility improvements.
* Additional filters on the site.
* Widening the pipeline to cover more WordPress repos (docs, themes, etc.).

Out of scope (see the full list [below](#whats-in-scope-whats-not)):

* Building a backend or database.
* Scraping anything that requires authentication.
* Features that need WordPress Foundation cooperation.

## Submit a code contribution

1. Fork and clone the repo.
2. Create a feature branch: `git checkout -b feature/short-description`.
3. Make your changes. Keep the scope tight: one change per PR.
4. Run the affected script locally and verify the output.
5. If you touched the template, rebuild the site and spot-check in a browser.
6. Commit with a descriptive message explaining the *why*.
7. Push and open a PR. Fill out the PR template.

### Style

* Python: stdlib plus `requests`, `pyyaml`, and `jinja2`. No additional dependencies without discussion.
* Formatting: sensible defaults. No auto-formatter enforced yet.
* Comments: only where the *why* is non-obvious. The code itself is short enough to read.

### Tests

There's no test suite. This is deliberately a small, transparent pipeline where the scripts are the spec. If you add logic that's easy to break (for example, props parsing edge cases), consider adding a small inline example in a docstring.

## Running the pipeline locally

Prerequisites: Python 3.10+, [`gh`](https://cli.github.com/) logged in.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install requests pyyaml jinja2

python scripts/fetch_core.py        # Core commits
python scripts/fetch_gutenberg.py   # Gutenberg PRs
python scripts/scrape_profiles.py   # wp.org profile enrichment
python scripts/verify_sponsors.py   # GitHub Sponsors check
python scripts/build_site.py        # Render site/index.html

open site/index.html
```

If you're only iterating on the site design, you can skip straight to `build_site.py`. The data caches from your last run are reused.

See the [README](README.md#how-the-data-is-collected) for a full explanation of what each stage does.

## What's in scope, what's not

**In scope**

* The static-site directory at [yani-.github.io/wp-contributor-sponsors](https://yani-.github.io/wp-contributor-sponsors/).
* Improvements to the data pipeline (accuracy, coverage, performance).
* Design and UX polish.
* Additional public data sources.
* Additional sponsor platforms.
* Documentation and accessibility.

**Not in scope (for now)**

* A backend, database, or authenticated UI.
* Anything requiring wp.org Meta team cooperation or private data.
* Scraping behind authentication.
* Ranking algorithm rewrites. The current `core + gutenberg_prs` sum is intentionally simple and transparent. Propose changes via issue first.

If you're unsure whether something fits, open an issue and ask.
