#!/usr/bin/env python3
"""Build a portable, source-backed documentation website (no ROS required)."""
import argparse
import ast
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[2]
SURFACE = ROOT / "docs/site"
GROUPS = [
    ("Start here", ["docs/INDEX.md", "docs/VISUAL_GUIDE.md", "README.md"]),
    ("System & interfaces", ["docs/ARCHITECTURE_CURRENT.md", "docs/STREAMING_CONTRACT.md", "docs/EDGE_DEVICE.md"]),
    ("Operate & verify", ["docs/EDGE_DEPLOYMENT.md", "docs/NETWORKING_TROUBLESHOOTING.md", "docs/VALIDATION.md", "docs/FOXGLOVE_INTEGRATION.md"]),
    ("Projects & development", ["docs/PROJECTS.md", "docs/autonomous_racing_plan.md", "docs/AUTONOMOUS_TESTING_PLAN.md", "plans/RTABMAP_SLAM_ACCEPTANCE.md", "plans/RTABMAP_LONG_MAP_SCALABILITY.md", "docs/CODEX_WORKFLOWS.md", "docs/DOCUMENTATION.md", "plans/DOCUMENTATION_SITE.md", "architecture.md"]),
]


def slug(text):
    return re.sub(r"[^\w\-]+", "-", text.lower()).strip("-") or "section"


def page_path(source):
    return "index.html" if str(source) == "docs/INDEX.md" else str(Path(source).with_suffix(".html"))


def relative_url(source, target):
    import posixpath
    return posixpath.relpath(target, str(Path(page_path(source)).parent))


def resolve_local(source, href):
    parts = urlsplit(href)
    if parts.scheme or parts.netloc or href.startswith("/"):
        return None
    import posixpath
    return posixpath.normpath(str(Path(source).parent / unquote(parts.path))) if parts.path else str(source)


def render_markdown(text, source, pages, asset_map=None):
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = md.parse(text)
    headings, used = [], {}
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            label = tokens[i + 1].content
            base = slug(re.sub(r"[`*]", "", label))
            count = used.get(base, 0)
            used[base] = count + 1
            anchor = base + (f"-{count}" if count else "")
            token.attrSet("id", anchor)
            headings.append((anchor, label, int(token.tag[1])))
        if token.children:
            for child in token.children:
                attr = "href" if child.type == "link_open" else "src" if child.type == "image" else None
                if not attr:
                    continue
                href = child.attrGet(attr)
                target = resolve_local(source, href)
                if target is None:
                    continue
                parts = urlsplit(href)
                if target in pages:
                    child.attrSet(attr, relative_url(source, page_path(target)) + ("#" + parts.fragment if parts.fragment else ""))
                elif asset_map and target in asset_map:
                    child.attrSet(attr, relative_url(source, asset_map[target]) + ("#" + parts.fragment if parts.fragment else ""))
                elif not parts.path:
                    continue
                else:
                    child.attrSet(attr, "#unavailable-reference")
                    child.attrSet("title", f"Reference unavailable in checkout: {href}")
                    child.attrSet("class", "unavailable")
    default_fence = md.renderer.rules["fence"]

    def fence(items, index, options, env):
        token = items[index]
        if token.info.strip() != "mermaid":
            return default_fence(items, index, options, env)
        code = html.escape(token.content)
        return (f'<figure class="diagram"><div class="mermaid" role="img" aria-label="Diagram from this page">{code}</div>'
                f'<details class="diagram-source" open><summary>Diagram source / text alternative</summary><pre><code>{code}</code></pre></details></figure>')

    md.renderer.rules["fence"] = fence
    return md.renderer.render(tokens, md.options, {}), headings


def title(text):
    match = re.search(r"^# (.+)$", text, re.M)
    return re.sub(r"\[.*?\]\s*", "", match[1]) if match else "Untitled reference"


def gather(root):
    paths = [root / "README.md", root / "architecture.md"]
    for folder in ("docs", "plans", "deprecated"):
        paths.extend(sorted((root / folder).glob("*.md")))
    return {p.relative_to(root).as_posix(): p.read_text() for p in paths}


def track_svg(root):
    path = root / "server_sim/src/my_gazebo_package/my_gazebo_package_py/track_layouts.py"
    tree = ast.parse(path.read_text())
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TRACK_LAYOUTS" for t in n.targets))
    points = ast.literal_eval(assignment.value)["catalunya"]["points"]
    xs, ys = zip(*points)
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    coords = " ".join(f"{(x-xmin)*2+35:.2f},{(ymax-y)*2+35:.2f}" for x, y in points + [points[0]])
    width, height = (xmax-xmin)*2+70, (ymax-ymin)*2+70
    x0, y0 = -xmin*2+35, ymax*2+35
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}" role="img" aria-labelledby="title desc">
<title id="title">Catalunya simulation centerline</title><desc id="desc">Closed polyline generated from the checked-in Catalunya coordinates. The circle marks the spawn at zero, zero. This is simulation geometry, not a driven trajectory.</desc>
<rect width="100%" height="100%" rx="12" fill="#101d32"/><polyline points="{coords}" fill="none" stroke="#57d5db" stroke-width="4" stroke-linejoin="round"/><circle cx="{x0:.2f}" cy="{y0:.2f}" r="7" fill="#ffbf69"/>
</svg>'''


def build(root=ROOT, output=None):
    """Validate a staged build before replacing the last working site's files."""
    root = Path(root).resolve()
    output = Path(output or root / "docs/site/dist").resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError("Output must not be the checkout or its parent")
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "generated-files.json"
    old_names = json.loads(manifest.read_text()) if manifest.exists() else []
    for name in old_names:
        if not (output / name).resolve().is_relative_to(output):
            raise ValueError("Generated-file manifest points outside output")
    with tempfile.TemporaryDirectory(prefix="gazebo-docs-", dir=output.parent) as directory:
        stage = Path(directory)
        pages = _build(root, stage)
        new_names = json.loads((stage / "generated-files.json").read_text())
        for name in new_names + ["generated-files.json"]:
            target = output / name
            if not target.resolve().is_relative_to(output):
                raise ValueError("Output file points outside output")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / name, target)
        for name in set(old_names) - set(new_names):
            target = output / name
            if target.is_file():
                target.unlink()
        return pages


def _build(root, output):
    root = Path(root).resolve()
    output = Path(output or root / "docs/site/dist").resolve()
    # Refuse broad output directories; only replace files this builder owns.
    if output == root or root.is_relative_to(output):
        raise ValueError("Output must not be the checkout or its parent")
    output.mkdir(parents=True, exist_ok=True)
    pages = gather(root)
    assets = {"docs/site/assets/catalunya.svg": "assets/catalunya.svg"}
    assets.update({"docs/site/assets/" + p.relative_to(root / "docs/site/assets").as_posix():
                   "assets/" + p.relative_to(root / "docs/site/assets").as_posix()
                   for p in (root / "docs/site/assets").rglob("*") if p.is_file()})
    generated = []

    def write(name, data):
        file = output / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data if isinstance(data, bytes) else data.encode())
        generated.append(name)

    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    for source, content in pages.items():
        write("source/" + source, content)
        for token in md.parse(content):
            for child in token.children or []:
                href = child.attrGet("href") if child.type == "link_open" else child.attrGet("src") if child.type == "image" else None
                if not href:
                    continue
                target = resolve_local(Path(source), href)
                if not target or target in pages or target in assets or target.startswith("docs/site/dist/"):
                    continue
                file = (root / target).resolve()
                if (file.is_relative_to(root) and file.is_file() and file.stat().st_size < 2_000_000
                        and not any(p in file.parts for p in ("build", "install", "log", "telemetry", "validation_evidence", ".git"))
                        and file.suffix in (".py", ".cpp", ".hpp", ".xml", ".yaml", ".yml", ".sh", ".svg", ".jpg", ".png", ".md", ".service")):
                    assets[target] = "source/" + target
                    write(assets[target], file.read_bytes())
    for file in sorted((root / "docs/site/assets").rglob("*")):
        if file.is_file():
            write("assets/" + file.relative_to(root / "docs/site/assets").as_posix(), file.read_bytes())
    write("assets/catalunya.svg", track_svg(root))
    groups = GROUPS + [("Other references", [p for p in pages if not p.startswith("deprecated/") and p not in {p for _, group in GROUPS for p in group}]),
                       ("Historical archive", [p for p in pages if p.startswith("deprecated/")])]
    search = []
    for source, content in pages.items():
        body, headings = render_markdown(content, Path(source), pages, assets)
        historical = source.startswith("deprecated/")
        label = title(content)
        digest = hashlib.sha256(content.encode()).hexdigest()[:12]
        nav = ""
        for group, paths in groups:
            if not paths:
                continue
            links = "".join(f'<a href="{html.escape(relative_url(source, page_path(p)))}" {"aria-current=\"page\"" if p == source else ""}>{html.escape(title(pages[p]))}</a>' for p in paths if p in pages)
            nav += f'<details {"" if group == "Historical archive" and not historical else "open"}><summary>{group}</summary>{links}</details>'
        toc = "".join(f'<a class="level-{level}" href="#{anchor}">{html.escape(label)}</a>' for anchor, label, level in headings if level in (2, 3))
        prefix = relative_url(source, "assets")
        banner = '<aside class="notice archive">Historical reference — superseded; commands and claims may be obsolete. Use the current guides for deployment.</aside>' if historical else ""
        document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(label)} · Autonomous Gazebo Docs</title><meta name="description" content="Simulation-to-edge documentation: architecture, operation, contracts, and acceptance evidence.">
<link rel="stylesheet" href="{prefix}/site.css"><script defer src="{prefix}/site.js"></script></head>
<body><a class="skip" href="#content">Skip to content</a><header><a class="brand" href="{relative_url(source, 'index.html')}"><span class="brand-mark">AG</span> Autonomous Gazebo <span class="brand-docs">/ docs</span></a><span class="header-note">ROS 2 Jazzy · Gazebo Harmonic</span></header>
<div class="layout"><aside class="sidebar"><details class="mobile-nav" open><summary>Documentation menu</summary>
<label class="search-label" for="search">Search documentation</label><input id="search" type="search" placeholder="Topics, ports, commands…" autocomplete="off" data-index="{relative_url(source, 'search-index.json')}" data-root="{relative_url(source, 'index.html').removesuffix('index.html')}"><div id="search-results" role="status" aria-live="polite"></div><nav aria-label="Documentation">{nav}</nav></details></aside>
<main id="content"><div class="page-meta"><span>{'ARCHIVE' if historical else 'DOCUMENTATION'}</span><a href="{relative_url(source, 'source/' + source)}">Markdown source</a></div>{banner}<article>{body}</article>
<footer><span>Source: <code>{html.escape(source)}</code> · content {digest}</span><p id="unavailable-reference">Underlined references marked unavailable point to files absent from this checkout; archived claims are not acceptance evidence.</p></footer></main>
<aside class="toc"><span>ON THIS PAGE</span><nav aria-label="Page contents">{toc}</nav><a class="back-top" href="#content">Back to top ↑</a></aside></div></body></html>'''
        write(page_path(source), document)
        search.append({"title": label, "path": page_path(source), "text": content, "historical": historical})
    write("search-index.json", json.dumps(search, ensure_ascii=False, sort_keys=True))
    write(".nojekyll", "")
    write("generated-files.json", json.dumps(sorted(set(generated)), indent=2))
    errors = validate(output)
    if errors:
        raise ValueError("Invalid site:\n" + "\n".join(errors))
    return pages


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        for key in ("href", "src"):
            if key in values:
                self.refs.append(values[key])


def validate(output):
    output = Path(output).resolve()
    parsed = {}
    for file in output.rglob("*.html"):
        parser = Links()
        parser.feed(file.read_text())
        parsed[file] = parser
    errors = []
    for file, parser in parsed.items():
        for href in parser.refs:
            url = urlsplit(href)
            if url.scheme or url.netloc:
                continue
            target = (file.parent / unquote(url.path)).resolve() if url.path else file
            if not target.is_relative_to(output):
                errors.append(f"{file.name}: outside output: {href}")
            elif not target.is_file():
                errors.append(f"{file.name}: missing: {href}")
            elif url.fragment and target in parsed and unquote(url.fragment) not in parsed[target].ids:
                errors.append(f"{file.name}: missing fragment: {href}")
    return errors


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, default=SURFACE / "dist")
    args = cli.parse_args()
    pages = build(output=args.output)
    print(f"Built {len(pages)} pages; local links and fragments passed: {args.output}")
