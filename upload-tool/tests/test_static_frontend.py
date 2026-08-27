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

    def test_commercial_detail_initializes_and_operates_its_lightbox(self):
        program = r"""
const fs = require('fs');
const vm = require('vm');

function element(id) {
  const classes = new Set();
  return {
    id,
    children: [],
    dataset: {},
    attributes: {},
    listeners: {},
    style: {},
    textContent: '',
    innerHTML: '',
    classList: {
      add(name) { classes.add(name); },
      remove(name) { classes.delete(name); },
      contains(name) { return classes.has(name); },
    },
    addEventListener(type, callback) {
      (this.listeners[type] ||= []).push(callback);
    },
    focus() { document.activeElement = this; },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    appendChild(child) { this.children.push(child); },
    querySelector(selector) {
      if (selector !== 'img') return null;
      this.image ||= element(id + '-img');
      return this.image;
    },
  };
}

const elements = Object.fromEntries([
  'detail-client', 'detail-title', 'detail-description', 'detail-media',
  'lightbox', 'lightbox-img', 'lightbox-caption', 'lightbox-preview-strip',
].map(id => [id, element(id)]));
const closeButton = element('lightbox-close');
const subNavTitle = element('sub-nav-title');
const documentListeners = {};
const document = {
  activeElement: null,
  body: { style: {} },
  addEventListener(type, callback) {
    (documentListeners[type] ||= []).push(callback);
  },
  createElement(tag) { return element(tag); },
  getElementById(id) { return elements[id] || null; },
  querySelector(selector) {
    if (selector === '.lightbox-close') return closeButton;
    if (selector === '.sub-nav-title') return subNavTitle;
    return null;
  },
};

const context = {
  document,
  setTimeout() {},
  URLSearchParams,
  location: { search: '?project=verification', href: '' },
  getProjectById() {
    return {
      client: 'Client', title: 'Title', description: 'Description',
      items: [
        { type: 'image', src: 'https://cdn.example/a.jpg', title: 'A' },
        { type: 'image', src: 'https://cdn.example/b.jpg', title: 'B' },
      ],
    };
  },
  observeLazyImage() {},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('commercial-detail.js', 'utf8'), context, {
  filename: 'commercial-detail.js',
});
vm.runInContext('_domReady = true; _dataReady = true; _init();', context);

const media = elements['detail-media'];
media.children[0].listeners.click[0]();
const opened = elements.lightbox.classList.contains('active');
const firstSource = elements['lightbox-img'].src;
documentListeners.keydown[0]({ key: 'ArrowRight' });
const secondSource = elements['lightbox-img'].src;
closeButton.listeners.click[0]({ stopPropagation() {} });

process.stdout.write(JSON.stringify({
  mediaCount: media.children.length,
  opened,
  firstSource,
  secondSource,
  closed: !elements.lightbox.classList.contains('active'),
}));
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
        self.assertEqual(summary["mediaCount"], 2)
        self.assertTrue(summary["opened"])
        self.assertEqual(summary["firstSource"], "https://cdn.example/a.jpg")
        self.assertEqual(summary["secondSource"], "https://cdn.example/b.jpg")
        self.assertTrue(summary["closed"])


if __name__ == "__main__":
    unittest.main()
