# Documentation website maintenance

## Canonical content

The website is generated from root `README.md` and `architecture.md`, every
top-level `docs/*.md` and `plans/*.md`, and the `deprecated/*.md` archive. Edit these
Markdown sources once; the website and repository views share the same content.
`docs/INDEX.md` is the website home. `scripts/docs/build_site.py` owns navigation,
heading IDs, source copies, search indexing, link rewriting, and validation.

The static output lives in `docs/site/dist/` and is ignored by Git. Source styles,
JavaScript, SVG assets, and the hosting configuration live in `docs/site/`.
No ROS build, telemetry, model, or device output is included automatically.

## Build and serve — simulation server

The builder requires Python 3.12+ and `markdown-it-py>=3.0.0,<5`, declared in
`scripts/docs/requirements.txt`. Use an environment where that dependency is
already available. Dependency installation is a separate operator action.

From the repository root:

```bash
python3 -m unittest discover -s scripts/docs -p 'test_*.py'
node scripts/docs/check_diagrams.cjs
python3 scripts/docs/build_site.py
python3 scripts/docs/serve_site.py --bind 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8766`. The server rebuilds when documentation or site assets
change; a browser refresh picks up the new content. It persists until stopped.
Port 8766 is documentation HTTP only, separate from the Foxglove bridge on 8765.
No server or Orange Pi ROS launch, topic, parameter, frame, or dependency changes.

## Keep it running across logins and reboots

The [systemd user service](site/docs-site.service) is enabled and running on this
simulation host. It starts at login and restarts on failure. User lingering is
disabled, so it does not start at boot before login. Review its paths,
interpreter, and port before using the template on another checkout. The service
listens on loopback and this host's Tailscale IPv4 address `100.98.177.128`.
After explicit user approval, the full site and included source copies are
available at [the tailnet website](http://100.98.177.128:8766/) to devices permitted
to reach this host by the tailnet policy. The added listener is bound to that
specific address rather than the LAN or a wildcard address. The URL uses HTTP
over the Tailscale connection; HTTPS Serve is not configured. On another host,
replace `--tailnet-bind` with its own address reported by `tailscale ip -4`.
Firewall configuration is unchanged. Control the installed host service with:

```bash
systemctl --user status docs-site.service
systemctl --user restart docs-site.service
systemctl --user stop docs-site.service
```

Builds validate in a staging directory before replacing served files. An invalid
document update leaves the last working site available and reports the failure in
the service log. Restart the service after changing the Python generator itself.

## Publish the same static site

The current deployment is the host user service exposed directly over Tailscale;
it rebuilds from this checkout without requiring Git publication. Tailscale Serve
was unavailable because tailnet HTTPS Serve is disabled and Serve configuration
requires privileges unavailable non-interactively. The approved direct binding
does not change tailnet settings. To withdraw tailnet access, remove
`--tailnet-bind 100.98.177.128` from the service, run
`systemctl --user daemon-reload`, then restart the service. Local access remains.

Upload the contents of `docs/site/dist/` to any static HTTP host. Nested `.html`
paths are real files, so no SPA rewrites or server-side runtime are required.
Relative links work under a subdirectory such as `/docs/`. The Sites manifest
declares `dist` as the public output directory.

### GitHub Pages

The [Pages workflow](https://github.com/Kenneth-Ross/autonomous-gazebo-ros/blob/main/.github/workflows/docs-pages.yml)
runs the documentation unit tests and Mermaid check, builds the static bundle,
then deploys it through GitHub Actions. Push to `main` to publish; a manual run
only deploys when selected branch is `main`. Build source is the committed
GitHub snapshot. Local or untracked changes do not appear until committed and
pushed.

This repository already uses GitHub Actions as its Pages source. To configure
another repository, open **Settings → Pages → Build and deployment** and set
**Source** to **GitHub Actions**. The public project site is
`https://kenneth-ross.github.io/autonomous-gazebo-ros/`.

The generator publishes `README.md`, `architecture.md`, every top-level Markdown
file in `docs/`, `plans/`, and `deprecated/`, plus linked source copies and a
search index containing document text. Review that full corpus as public content.
Generated output excludes telemetry, model files, and unrelated untracked images.

Optional Sites publication remains unselected. A hosted snapshot updates only
after a successful Pages workflow run on committed source.

## Diagrams and cited examples

Use fenced `mermaid` for flows and sequences. Use SVG for diagrams that should
remain visual without JavaScript. Every SVG needs `title` and `desc`; every
Markdown image needs descriptive alt text and a caption with a source link.
Say whether the image is an illustration, historical screenshot, or retained
execution evidence. Link evidence logs by name and scope rather than fabricating
an accessible log that is absent from the checkout.

Mermaid is pinned and vendored locally with its MIT license; diagram text remains
available if JavaScript fails. Search and copy controls enhance the static pages;
reading, navigation, and source downloads work without them. Mermaid syntax
references are cited in the [visual guide](VISUAL_GUIDE.md#visual-sources-and-reuse).

## Verification

The build validates local page, asset, and heading references. Missing repository
references are marked unavailable rather than presented as working source links.
Acceptance tests cover complete page inventory, deterministic rebuilds, archive
warnings, escaping, missing assets, and path traversal. Record meaningful content
and status changes in [PROJECTS.md](PROJECTS.md).

The optional Node grammar check parses every Mermaid block plus a deliberately
malformed control case. It substitutes the DOM sanitizer only inside its parser
VM; it does not render diagrams or test browser security. The site's actual
browser renderer uses Mermaid strict mode and the unchanged vendored asset.
Retained host results are recorded in [site verification](site/VERIFICATION.md).

## Serve retry — 2026-10-12

The documentation service still runs at `http://100.98.177.128:8766/`. The requested
Serve proxy was not enabled: HTTPS Serve reported disabled, HTTP configuration
was denied, and non-interactive sudo required a password. Subsequent status
showed another project on Serve port 80; preserve it. The
[review record](CODE_REVIEW_2026-10-12.md#documentation-hosting) gives the operator
command to add documentation on port 8080 without replacing that site.
