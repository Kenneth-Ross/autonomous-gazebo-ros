"""Acceptance tests for the repository documentation website."""
import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DocumentationSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("docs_builder", ROOT / "scripts/docs/build_site.py")
        cls.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)

    def test_nominal_complete_site_and_deterministic_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            result = self.builder.build(ROOT, output)
            expected = {p.relative_to(ROOT).as_posix() for folder in ("docs", "plans", "deprecated")
                        for p in (ROOT / folder).glob("*.md")} | {"README.md", "architecture.md"}
            self.assertEqual(expected, set(result))
            self.assertEqual([], self.builder.validate(output))
            snapshot = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            self.builder.build(ROOT, output)
            self.assertEqual(snapshot, {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()})
            self.assertFalse((output / "yolo_inference_416.png").exists())
            self.assertIn("Historical reference", (output / "deprecated/plan.html").read_text())
            self.assertIn('class="mermaid"', (output / "docs/ARCHITECTURE_CURRENT.html").read_text())
            guide = (output / "docs/VISUAL_GUIDE.html").read_text()
            self.assertIn('src="../assets/catalunya.svg"', guide)
            self.assertIn('src="assets/system-map.svg"', (output / "index.html").read_text())
            self.assertTrue((output / "assets/mermaid.min.js").is_file())
            self.assertTrue((output / "assets/MERMAID-LICENSE.txt").is_file())

    def test_adversarial_escape_and_duplicate_heading_ids(self):
        body, headings = self.builder.render_markdown('# Repeat\n\n# Repeat\n\n<script>alert(1)</script>\n\n```mermaid\nA["<script>bad</script>"]\n```', Path("docs/example.md"), {})
        self.assertNotIn("<script>alert", body)
        self.assertNotIn("<script>bad", body)
        self.assertEqual(["repeat", "repeat-1"], [h[0] for h in headings])

    def test_adversarial_missing_asset_and_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "index.html").write_text('<a href="missing.html">Missing</a><img src="../secret.png">')
            errors = self.builder.validate(output)
            self.assertTrue(any("missing.html" in e for e in errors))
            self.assertTrue(any("outside" in e for e in errors))

    def test_adversarial_failed_rebuild_keeps_last_working_site(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            self.builder.build(ROOT, output)
            before = {p.relative_to(output): hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob("*") if p.is_file()}
            fixture = Path(directory) / "fixture"
            fixture.mkdir()
            for folder in ("docs", "plans", "deprecated", "server_sim"):
                (fixture / folder).symlink_to(ROOT / folder, target_is_directory=True)
            (fixture / "architecture.md").write_text((ROOT / "architecture.md").read_text())
            (fixture / "README.md").write_text('# Broken update\n\n[Missing heading](architecture.md#does-not-exist)')
            with self.assertRaises(ValueError):
                self.builder.build(fixture, output)
            self.assertEqual(before, {p.relative_to(output): hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
