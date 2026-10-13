# Documentation website host verification

Retained on 2026-10-01. Scope: documentation generator, static output, and local
HTTP server; no Orange Pi execution or browser visual acceptance is claimed.

## Nominal automated acceptance

Command: `python3 -m unittest discover -s scripts/docs -p 'test_*.py'`.

- Complete inventory: 35 Markdown pages, including every current guide, active
  plan, root entry point, and historical document.
- Deterministic rebuild: byte-for-byte identical files across repeated builds.
- Every emitted local page, asset, and fragment resolves.
- SVG system map and generated Catalunya geometry are delivered through local
  asset URLs; source code citations are included as static source copies.
- Archive pages carry historical warnings. No untracked inference image ships.
- Local Mermaid bundle and MIT license are present.

## Adversarial automated acceptance

The same suite retains script-like text as escaped content, generates distinct
IDs for duplicate headings, reports missing assets, and rejects links outside the
output directory. A failed-rebuild regression verifies that an invalid heading
reference leaves the previous site files unchanged. Four unittest cases passed
with no errors or failures in both the authoring interpreter (markdown-it-py
4.0.0) and `/usr/bin/python3` used by the service (markdown-it-py 3.0.0).

Command: `node scripts/docs/check_diagrams.cjs`.

All 12 Mermaid blocks parsed, and the deliberately malformed control diagram was
rejected. This is grammar validation only; the parser VM replaces the DOM-only
sanitizer. Browser rendering still uses the unchanged strict-mode renderer.

## Build and delivery checks

- `python3 scripts/docs/build_site.py`: 35 pages built; local reference validation
  passed. Static output is approximately 3.5 MB.
- `node --check docs/site/assets/site.js`: passed.
- `python3 -m py_compile scripts/docs/build_site.py scripts/docs/serve_site.py`: passed.
- `git diff --check`: passed.
- Local HTTP requests to `/` and `/docs/VISUAL_GUIDE.html` returned 200 on port 8766.

The browser preview-opening tool reported `CUA_REPL_ENABLED_SURFACES is required`.
No screenshot, interaction, viewport, or SVG rendering check was performed.

## Remaining deployment gate

The host `docs-site.service` is enabled and active; its loopback home page returned
HTTP 200. After explicit user approval of full-site/source-copy tailnet access,
the service also listens on `100.98.177.128:8766`. Host-originated requests to
the tailnet home, visual guide, and Mermaid bundle returned HTTP 200. Socket
inspection confirms specific loopback and Tailscale IP listeners, with no
wildcard listener. Six automated cases pass, including nominal loopback/tailnet
selection and rejection of wildcard, LAN, loopback, and hostname values for the
extra tailnet binding. Cross-device HTTP access has not been tested.

Tailscale HTTPS Serve was not enabled on the tailnet. HTTP Serve configuration
was denied due to unavailable privileges; `sudo -n` required a password, which
was not requested or collected. The waiting HTTPS setup process was stopped.
Direct user-service binding provides the approved deployment without changing
tailnet Serve settings or using public Funnel.

The user service starts at login and restarts on failure. User lingering
is disabled, so pre-login boot availability is not claimed. The initial preview
process was stopped after the service took ownership of port 8766. No Git commit,
push, or optional Sites/cloud registration was performed. Browser visual checks
remain unclaimed.

## Host refresh — 2026-10-12

Added the focused code review and project status summary: 36 pages built with
local links/fragments valid, six documentation acceptance tests passed, and 12
Mermaid diagrams parsed. `git diff --check` passed. The existing user service
is active. Tailscale Serve proxy configuration was denied and non-interactive
sudo required a password; the unrelated Serve port-80 site was preserved.
Direct tailnet documentation access remains on port 8766. Browser rendering
and cross-device access remain unverified.

## E2E consolidation documentation refresh

The testing guide and consolidation plan bring the current site to 39 pages.
Six documentation tests pass, generated links/fragments resolve, and the host
tailnet testing and project-status pages return updated content. Browser and
cross-device rendering/reachability remain unclaimed.
