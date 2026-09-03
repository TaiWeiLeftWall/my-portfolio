import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SCRIPTS = [
    ROOT / "common.js",
    ROOT / "load-data.js",
    ROOT / "script.js",
    ROOT / "data.js",
    ROOT / "commercial.js",
    ROOT / "commercial-list.js",
    ROOT / "commercial-detail.js",
    ROOT / "upload-tool" / "cms.js",
]


class StaticFrontendTests(unittest.TestCase):
    def test_all_tracked_frontend_javascript_has_valid_syntax(self):
        for script in FRONTEND_SCRIPTS:
            with self.subTest(script=script.relative_to(ROOT)):
                result = subprocess.run(
                    ["node", "--check", str(script)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_exported_data_files_load_in_a_node_vm(self):
        program = r"""
const fs = require('fs');
const vm = require('vm');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync('data.js', 'utf8'), context, { filename: 'data.js' });
vm.runInContext(fs.readFileSync('commercial.js', 'utf8'), context, { filename: 'commercial.js' });
const summary = vm.runInContext(`({
  photographerNameIsString: typeof photographerName === 'string',
  photoGroupsIsArray: Array.isArray(photoGroups),
  photosIsArray: Array.isArray(photos),
  commercialProjectsIsArray: Array.isArray(commercialProjects),
})`, context);
process.stdout.write(JSON.stringify(summary));
"""
        result = subprocess.run(
            ["node", "-e", program],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["photographerNameIsString"])
        self.assertTrue(summary["photoGroupsIsArray"])
        self.assertTrue(summary["photosIsArray"])
        self.assertTrue(summary["commercialProjectsIsArray"])

    def test_commercial_detail_uses_statement_first_sequence(self):
        script = (ROOT / "commercial-detail.js").read_text(encoding="utf-8")
        markup = (ROOT / "commercial-detail.html").read_text(encoding="utf-8")

        for interface in (
            "commercialSlideCount",
            "renderCommercialSequence",
            "setCommercialSlide",
            "createCommercialStatement",
            "createCommercialMedia",
        ):
            self.assertIn(f"function {interface}", script)

        self.assertIn('class="commercial-viewer"', markup)
        self.assertIn("data-commercial-counter", markup)
        self.assertIn("data-commercial-prev", markup)
        self.assertIn("data-commercial-next", markup)
        self.assertNotIn('id="lightbox"', markup)
        self.assertNotIn("openLightbox", script)


if __name__ == "__main__":
    unittest.main()
