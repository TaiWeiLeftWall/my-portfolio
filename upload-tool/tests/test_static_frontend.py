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
    def _evaluate_data_js(self, expression):
        program = """
const fs = require('fs');
const vm = require('vm');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync('data.js', 'utf8'), context, { filename: 'data.js' });
const result = vm.runInContext(%s, context);
process.stdout.write(JSON.stringify(result));
""" % json.dumps(expression)
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
        return json.loads(result.stdout)

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

    def test_curated_photo_group_titles_dates_and_counts(self):
        program = r"""
const fs = require('fs');
const vm = require('vm');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync('data.js', 'utf8'), context, { filename: 'data.js' });
const groups = vm.runInContext(
  'photoGroups.map(({ title, date, images }) => ({ title, date, count: images.length }))',
  context,
);
process.stdout.write(JSON.stringify(groups));
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
        self.assertEqual(
            json.loads(result.stdout),
            [
                {"title": "留别III", "date": "2024-06-03", "count": 9},
                {"title": "25GR摇滚节", "date": "2025-05-30", "count": 16},
                {"title": "心海I", "date": "2025-12-19", "count": 2},
                {"title": "中环", "date": "2025-10-09", "count": 2},
                {"title": "西湖吴山", "date": "2024-11-23", "count": 2},
                {"title": "杭州动物园", "date": "2024-11-06", "count": 1},
                {"title": "金沙湖", "date": "2024-11-04", "count": 2},
                {"title": "焦点万圣影棚", "date": "2024-11-02", "count": 2},
                {"title": "关前正街", "date": "2025-10-10", "count": 4},
                {"title": "虎跑", "date": "2025-12-06", "count": 4},
                {"title": "植物园", "date": "2025-11-21", "count": 14},
                {"title": "心海II", "date": "2025-12-21", "count": 6},
                {"title": "徐浩蓝毕业照", "date": "2023-06-06", "count": 6},
                {"title": "沈媛毕业照", "date": "2023-06-09", "count": 9},
                {"title": "洪媛玥毕业照", "date": "2024-06-09", "count": 7},
                {"title": "24届吉协毕业照", "date": "2024-06-16", "count": 4},
                {"title": "25届焦点毕业照", "date": "2025-06-24", "count": 10},
            ],
        )

    def test_graduation_collection_inventory(self):
        groups = self._evaluate_data_js(
            "photoGroups.filter(group => group.collection === 'graduation')"
            ".map(({title,date,images}) => ({title,date,count:images.length}))"
            ".sort((a,b) => a.date.localeCompare(b.date))"
        )

        self.assertEqual(
            groups,
            [
                {"title": "徐浩蓝毕业照", "date": "2023-06-06", "count": 6},
                {"title": "沈媛毕业照", "date": "2023-06-09", "count": 9},
                {"title": "留别III", "date": "2024-06-03", "count": 9},
                {"title": "洪媛玥毕业照", "date": "2024-06-09", "count": 7},
                {"title": "24届吉协毕业照", "date": "2024-06-16", "count": 4},
                {"title": "25届焦点毕业照", "date": "2025-06-24", "count": 10},
            ],
        )

    def test_curated_photo_deletions_and_november_split(self):
        program = r"""
const fs = require('fs');
const vm = require('vm');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync('data.js', 'utf8'), context, { filename: 'data.js' });
const groups = vm.runInContext(
  `Object.fromEntries(photoGroups.map(group => [
    group.title,
    group.images.map(image => image.src.split('/').pop()),
  ]))`,
  context,
);
process.stdout.write(JSON.stringify(groups));
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
        groups = json.loads(result.stdout)
        self.assertEqual(
            groups.get("中环"),
            [
                "1778573147741-kimvutkgpsd.jpg",
                "1778573229694-qe1xnjg6yt.jpg",
            ],
        )
        self.assertEqual(
            groups.get("西湖吴山"),
            [
                "1778573167139-57pp66kzc2n.jpg",
                "1778573188236-lah7s7zpv7.jpg",
            ],
        )
        self.assertEqual(groups.get("杭州动物园"), ["1778573175933-217u44ddv8ih.jpg"])
        self.assertEqual(
            groups.get("金沙湖"),
            [
                "1778573204546-jawj2dy9bmc.jpg",
                "1778573216145-usaaudujl7.jpg",
            ],
        )
        self.assertEqual(
            groups.get("焦点万圣影棚"),
            [
                "1778573206828-5mce4orwp73.jpg",
                "1778573252186-c7v70dzzeis.jpg",
            ],
        )
        removed = {
            "1778573171198-jnl3k616nwe.jpg",
            "1778573173683-64kjgkrczh8.jpg",
            "1778573194919-na8k7slrm6.jpg",
            "1778573191823-xwzq9v963l.jpg",
            "1778573242599-pd2h0hljd8.jpg",
            "1778573259172-d3t5iis85iv.jpg",
        }
        present = {filename for filenames in groups.values() for filename in filenames}
        self.assertTrue(removed.isdisjoint(present))

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
