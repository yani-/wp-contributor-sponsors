# Security Policy

## Supported Versions

This project is a static site generator run on a schedule. Only the `main` branch is supported. There are no release artifacts to patch.

## Reporting a Vulnerability

If you discover a security issue, for example an XSS risk in the rendered template, a dependency vulnerability, or a way to inject malicious data into the site via a crafted wp.org profile, please **do not open a public issue**.

Email **yani@iliev.me** with:

* A description of the issue.
* Steps to reproduce or a proof-of-concept.
* Any suggested mitigation.

You can expect an acknowledgement within a few days. Verified issues will be fixed on `main` and redeployed via the usual CI pipeline.

## Out-of-Scope

* Issues in upstream dependencies (`requests`, `pyyaml`, `jinja2`). Please report those to the upstream projects.
* Anything related to WordPress.org, GitHub.com, or other third-party services. This project only consumes their public data.
* Social engineering against contributors listed in the directory. The project only displays publicly available information from those users' own profiles.
