# [VERIFICATION] Persistent Documentation Website

## Scope

One repository-backed static website presents all current guides, active plans,
and an explicitly historical archive. Markdown remains canonical; generated HTML
is disposable. This is host-only documentation work with no ROS, wire, or edge
deployment change. Publishing must not commit or push this repository without
the user's explicit authorization.

## Acceptance

- Every `docs/*.md`, `plans/*.md`, root README/architecture guide, and historical
  `deprecated/*.md` has a stable page, source link, and search entry.
- Local document links and heading fragments resolve; linked source files are
  included in the static output. No telemetry, models, or untracked images ship.
- SVG diagrams include accessible titles/descriptions. Mermaid diagrams retain
  readable source when rendering is unavailable. Visual examples cite provenance
  and distinguish illustrative geometry from retained execution evidence.
- Search, mobile navigation, keyboard access, tables, code, and page contents are
  supported. Reading and navigation work without JavaScript.
- Repeated builds are deterministic. Nominal and adversarial automated checks
  cover coverage, escaping, missing links, traversal, and build reproducibility.
- Provide a repeatable build/serve procedure and a deployment-ready static bundle.

## Verification evidence

[Retained host results](../docs/site/VERIFICATION.md): 35 pages, four passing
nominal/adversarial unittest cases, 12 parsed Mermaid diagrams with malformed
control rejection, deterministic rebuilds, local link/fragment checks, Python/JS
syntax checks, and HTTP 200 responses. Source SVG figures carry provenance.
Orange Pi checks are not required. Browser preview opening was unavailable;
visual rendering is not claimed. Local persistence service is enabled and active,
starts at login, restarts on failure, and retains the last valid site after an
invalid source update. User-approved tailnet publication is now served directly
on `http://100.98.177.128:8766/`, with localhost retained and no Git publication.
Six automated tests include nominal and adversarial listener-address checks.
Browser rendering remains unchecked; no cross-device Orange Pi execution is
claimed. Optional Sites/cloud publication is not the selected deployment.

## Review and hosting update — 2026-10-12

The current site has 36 pages after adding the focused code review and overall
status. Six documentation tests and 12 Mermaid grammars pass. The user service
remains active; the requested Serve proxy is blocked by host privileges, with
an unrelated port-80 Serve site preserved. See the
[review record](../docs/CODE_REVIEW_2026-10-12.md) for details. Status remains
`[VERIFICATION]`; browser and cross-device checks remain open.

## Racing review remediation documentation

Current inventory: 37 pages, including the racing fix specification. The reviewed
remediation and retained original/fixed node-test comparison are linked from the
project ledger. Hosting and remaining browser/device gates are unchanged.

## E2E testing guide update

Current inventory is 39 pages after adding the testing guide and consolidation
specification. The documentation acceptance suite and link/fragment validation
pass. Hosting and remaining browser/device gates are unchanged.
