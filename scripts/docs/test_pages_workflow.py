"""Contract checks for the GitHub Pages documentation workflow."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/docs-pages.yml"


class GitHubPagesWorkflowTests(unittest.TestCase):
    def test_build_checks_and_deploys_only_generated_site(self):
        workflow = WORKFLOW.read_text()

        self.assertRegex(workflow, r"(?m)^on:\s*$")
        self.assertRegex(workflow, r"(?s)push:.*?branches:\s*\[main\]")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("python-version: '3.12'", workflow)
        self.assertIn("python -m pip install -r scripts/docs/requirements.txt", workflow)
        self.assertIn("python -m unittest discover -s scripts/docs -p 'test_*.py'", workflow)
        self.assertIn("node scripts/docs/check_diagrams.cjs", workflow)
        self.assertIn('python scripts/docs/build_site.py --output "$RUNNER_TEMP/docs-site"', workflow)
        self.assertRegex(workflow, r"(?m)^\s*uses: actions/upload-pages-artifact@v\d+\s*$")
        self.assertIn("${{ runner.temp }}/docs-site", workflow)
        self.assertIn("include-hidden-files: true", workflow)
        self.assertRegex(workflow, r"(?m)^\s*uses: actions/deploy-pages@v\d+\s*$")
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)

        upload_step = workflow.split("actions/upload-pages-artifact", 1)[1].split("- name:", 1)[0]
        self.assertNotIn("path: .", upload_step)


if __name__ == "__main__":
    unittest.main()
