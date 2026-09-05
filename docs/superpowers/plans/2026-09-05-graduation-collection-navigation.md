# Graduation Collection Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reference-style grouped sidebar and a portrait → graduation collection containing six cover groups, while importing 36 new images and reusing the existing nine-image “留别III” group.

**Architecture:** Extend the existing `photoGroups` records with one optional `collection` string that round-trips through SQLite, the CMS API, and `data.js`. Keep all public pages and the existing hash router; add `#collection=graduation` as one overview state, render it with the existing ratio-preserving work controls, and remember the originating overview when closing a project. Convert the flat sidebar constant into a small grouped navigation model without introducing a framework or dependency.

**Tech Stack:** Static HTML, CSS, vanilla JavaScript, Python 3 standard library, SQLite, `unittest`, Node syntax/harness tests, Playwright smoke tests, existing local CMS and R2 upload service.

**Spec:** `docs/superpowers/specs/2026-09-05-graduation-collection-navigation-design.md`

## Global Constraints

- Preserve the current static HTML/CSS/JavaScript architecture and every existing public page.
- Preserve the existing 12 groups, 64 photos, their order, and their URLs; append five new groups rather than reordering existing records.
- Reuse the existing nine-photo `留别III` group; do not upload that source folder again.
- Treat `E:\图片\1A作品汇总\00A图片项目\A01人像\01_毕业照` as read-only.
- Upload exactly five groups and 36 images through the existing CMS/R2 path; publish 17 groups and 100 photos only after every new group is complete.
- Keep intrinsic image ratios, the contained single-image viewer, keyboard controls, image fades, and `prefers-reduced-motion` behavior.
- Desktop/tablet graduation overview: three columns. Mobile at `max-width: 800px`: two columns.
- Do not introduce a frontend, carousel, masonry, icon, font, or animation dependency.

## Preflight

- [ ] Read the spec and confirm the isolated branch is clean.

```powershell
git status --short --branch
Get-Content -Raw docs/superpowers/specs/2026-09-05-graduation-collection-navigation-design.md
```

Expected: branch `feature/yundongshu-portfolio-refactor`; no uncommitted files.

- [ ] Verify the source inventory without modifying it.

```powershell
$graduationRoot = 'E:\图片\1A作品汇总\00A图片项目\A01人像\01_毕业照'
Get-ChildItem -LiteralPath $graduationRoot -Directory | ForEach-Object {
    [pscustomobject]@{
        Folder = $_.Name
        Images = (Get-ChildItem -LiteralPath $_.FullName -File |
            Where-Object Extension -Match '^\.(jpg|jpeg|png|webp)$').Count
    }
}
```

Expected counts in date order: `6, 9, 9, 7, 4, 10`.

- [ ] Run the fresh baseline before any implementation edits.

```powershell
python -m unittest discover -s upload-tool/tests -p "test_*.py"
node upload-tool/tests/check_cms_script.mjs
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: all Python tests pass, CMS script checks pass, and `site smoke checks passed`.

---

### Task 1: Persist the optional collection marker through the CMS

**Files:**
- Modify: `upload-tool/cms_db.py:14-220, 450-545, 950-1030`
- Modify: `upload-tool/cms.js:110-180, 246-345, 432-436`
- Test: `upload-tool/tests/test_cms_db.py`
- Test: `upload-tool/tests/test_cms_server.py`
- Test: `upload-tool/tests/check_cms_script.mjs`

**Interfaces:**
- Consumes: existing photo-group payloads with `category`, `title`, `description`, `date`, `cols`, and `sort_order`.
- Produces: every photo-group record exposes `collection: string`; omitted input becomes `""`. `Database.create_photo_group`, `create_photo_group_idempotent`, `update_photo_group`, `bulk_import`, `state`, and `_frontend_strings` preserve it.

- [ ] **Step 1: Write failing database tests for schema migration and round trips.**

Update the schema-version assertion to `3`, assert `collection` exists with default `''`, and add these behaviors to `DatabaseTests`:

```python
def test_photo_group_collection_round_trips_through_create_update_and_state(self):
    group = self.db.create_photo_group(
        {
            "category": "portrait",
            "title": "Graduation",
            "date": "2025-06-24",
            "collection": "graduation",
        }
    )
    self.assertEqual(group["collection"], "graduation")
    self.assertEqual(self.db.state()["photoGroups"][0]["collection"], "graduation")

    updated = self.db.update_photo_group(group["id"], {"title": "Updated"})
    self.assertEqual(updated["collection"], "graduation")


def test_photo_group_collection_defaults_to_empty_string(self):
    group = self.db.create_photo_group({"category": "portrait"})
    self.assertEqual(group["collection"], "")


def test_bulk_import_and_frontend_export_preserve_collection(self):
    self.db.bulk_import(
        [{
            "category": "portrait",
            "title": "Graduation",
            "date": "2025-06-24",
            "collection": "graduation",
            "images": [],
        }]
    )
    data_js, _commercial_js = self.db._frontend_strings()
    self.assertIn('"collection": "graduation"', data_js)
```

Extend the existing real-v2 migration test by creating a v2 `photo_groups` table without `collection`, inserting one row, running `initialize(seed=False)`, and asserting the row remains while `collection == ""`.

- [ ] **Step 2: Run the database tests and verify RED.**

```powershell
python -m unittest upload-tool.tests.test_cms_db -v
```

Expected: failures mention schema version `2`, missing `collection`, or an absent SQLite column.

- [ ] **Step 3: Implement schema v3 and thread `collection` through every group write/export path.**

Use one defaulted column and one migration call:

```python
SCHEMA_VERSION = 3

# In photo_groups CREATE TABLE:
collection text not null default '',

# In initialize() while migrating:
self._ensure_column(
    conn, "photo_groups", "collection", "text not null default ''"
)
```

For create, idempotent create, update, seed, bulk import, and frontend export, place `collection` next to `category`. Normalize input with `str(data.get("collection", "") or "").strip()`; partial updates obtain the current value from `merged["collection"]`.

The generated frontend record must have this exact shape:

```python
{
    "category": group["category"],
    "collection": group["collection"],
    "title": group["title"],
    "description": group["description"],
    "date": group["date"],
    "cols": group["cols"],
    "images": [...],
}
```

- [ ] **Step 4: Add failing API and CMS-editor assertions.**

In `test_cms_server.py`, extend a photo-group POST/PUT round-trip test to send `"collection": "graduation"` and assert `/api/state` returns it after both operations. In `check_cms_script.mjs`, require the editor markup and save payload to include `ef-collection`:

```javascript
assert.match(source, /id=["']ef-collection["']/);
assert.match(source, /collection:\s*\$\(['"]ef-collection['"]\)\.value/);
```

- [ ] **Step 5: Run focused API/editor checks and verify RED.**

```powershell
python -m unittest upload-tool.tests.test_cms_server -v
node upload-tool/tests/check_cms_script.mjs
```

Expected: the server assertion lacks `collection`, and the Node harness reports no `ef-collection` field.

- [ ] **Step 6: Add the CMS editor field and save payload.**

In the group editor, add an optional field immediately after category:

```javascript
html += '<div class="panel-field"><label>合集标记</label>' +
  '<input id="ef-collection" value="' + esc(data.collection||'') +
  '" placeholder="例如 graduation"></div>';
```

Create-mode defaults and `savePanel()` must use:

```javascript
{
  date: $('ef-date').value,
  category: $('ef-category').value,
  collection: $('ef-collection').value.trim(),
  title: $('ef-title').value,
  description: $('ef-desc').value,
  cols: parseInt($('ef-cols').value),
}
```

Show a non-empty collection marker in the CMS card metadata so the grouping remains inspectable.

- [ ] **Step 7: Run all Task 1 checks and verify GREEN.**

```powershell
python -m unittest upload-tool.tests.test_cms_db upload-tool.tests.test_cms_server -v
node upload-tool/tests/check_cms_script.mjs
node --check upload-tool/cms.js
```

Expected: all checks pass.

- [ ] **Step 8: Commit the CMS data-contract change.**

```powershell
git add -- upload-tool/cms_db.py upload-tool/cms.js upload-tool/tests/test_cms_db.py upload-tool/tests/test_cms_server.py upload-tool/tests/check_cms_script.mjs
git commit -m "feat: preserve photo collection metadata"
```

---

### Task 2: Render the reference-style grouped sidebar

**Files:**
- Modify: `common.js:57-124`
- Modify: `style.css:1543-1572, 1627-1640`
- Test: `tests/site_smoke_test.py:330-390`

**Interfaces:**
- Consumes: existing route strings and `setMenuExpanded(expanded)` behavior.
- Produces: `PORTFOLIO_NAVIGATION` grouped records, `.portfolio-nav-section`, `.portfolio-nav-heading`, `.portfolio-nav-items`, `.portfolio-nav-child`, and `.ancestor-active`; all real routes retain `data-nav-link`.

- [ ] **Step 1: Write failing sidebar hierarchy and active-state smoke assertions.**

Replace the old flat-count-only assertions with exact hierarchy checks:

```python
assert desktop.locator(".portfolio-nav-section").count() == 3
assert desktop.locator(".portfolio-nav-heading").all_inner_texts() == [
    "PROJECTS 项目", "EDITORIAL", "INFO"
]
assert desktop.locator(".portfolio-nav a[data-nav-link]").count() == 8
graduation = desktop.locator(
    ".portfolio-nav-child[href='index.html#collection=graduation']"
)
assert graduation.count() == 1
assert graduation.evaluate(
    "node => node.closest('.portfolio-nav-items').querySelector(\"a[href='index.html#category=portrait']\") !== null"
)
```

Open `#collection=graduation` and assert the child has `.active`, `aria-current="page"`, and the portrait link has `.ancestor-active` but no `aria-current`.

- [ ] **Step 2: Run the smoke test and verify RED.**

```powershell
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: `.portfolio-nav-section` count is `0` or the graduation link is missing.

- [ ] **Step 3: Replace `PORTFOLIO_LINKS` with a grouped navigation model and renderer.**

Use a small static model; do not interpolate CMS text:

```javascript
const PORTFOLIO_NAVIGATION = {
    primary: [{ href: 'index.html', label: 'Selected Works' }],
    sections: [
        {
            label: 'PROJECTS 项目',
            items: [
                {
                    href: 'index.html#category=portrait',
                    label: '人像',
                    children: [
                        { href: 'index.html#collection=graduation', label: '毕业照' },
                    ],
                },
                { href: 'index.html#category=performance', label: '演出' },
                { href: 'index.html#category=landscape', label: '风光' },
            ],
        },
        {
            label: 'EDITORIAL',
            items: [
                { href: 'videos.html', label: '视频' },
                { href: 'commercial.html', label: '商业项目' },
            ],
        },
        { label: 'INFO', items: [{ href: 'about.html', label: '关于我' }] },
    ],
};
```

Add focused helpers such as `renderNavLink(item, className = '')`, `renderNavItems(items)`, and `renderNavSections(sections)` so `renderPortfolioShell()` remains readable. Every clickable record renders an `<a>` with `data-nav-link`; headings render as non-interactive text.

Update `updateActiveNavigation()` so `#collection=graduation` activates the child and adds `.ancestor-active` only to `index.html#category=portrait`.

- [ ] **Step 4: Add restrained hierarchy styles.**

Map the reference rhythm to existing tokens:

```css
.portfolio-nav-links,
.portfolio-nav-sections,
.portfolio-nav-items {
    display: flex;
    flex-direction: column;
}

.portfolio-nav-links { gap: 26px; }
.portfolio-nav-sections { gap: 28px; }
.portfolio-nav-items { gap: 8px; }

.portfolio-nav-heading {
    margin: 0 0 10px;
    color: var(--portfolio-muted);
    font-size: 11px;
    line-height: 1.5;
    letter-spacing: 1px;
}

.portfolio-nav-child {
    margin-left: 14px;
    font-size: 13px;
}

.portfolio-nav a.ancestor-active { color: var(--portfolio-ink); }
```

Keep the desktop sidebar fixed with hidden overflow and the mobile expanded navigation capped at `46dvh`.

- [ ] **Step 5: Run syntax and smoke checks and verify GREEN.**

```powershell
node --check common.js
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: grouped hierarchy, active/ancestor states, fixed sidebar, and mobile menu assertions pass.

- [ ] **Step 6: Commit the grouped sidebar.**

```powershell
git add -- common.js style.css tests/site_smoke_test.py
git commit -m "feat: group portfolio sidebar navigation"
```

---

### Task 3: Add the graduation collection overview state

**Files:**
- Modify: `script.js:1-225`
- Modify: `style.css:1642-1750`
- Test: `tests/site_smoke_test.py:390-500`

**Interfaces:**
- Consumes: `photoGroups[].collection`, `enableImageLoadFade(img)`, `openProject(projectId, slideIndex, trigger)`, and existing hash-state parsing.
- Produces: `COLLECTIONS.graduation`, `renderCollection(collectionId)`, `projectReturnHash`, and a `#collection=graduation` route that renders six work buttons after content import.

- [ ] **Step 1: Write failing collection view tests with injected collection fixtures.**

Add `assert_graduation_collection_state(browser)` and invoke it from `main()`. Before changing the hash, inject six markers into the current in-memory data so this task does not depend on R2 import:

```python
page = open_page(browser, "index", width=1280, height=720)
page.evaluate("photoGroups.slice(0, 6).forEach(group => group.collection = 'graduation')")
page.evaluate("location.hash = 'collection=graduation'")
page.wait_for_timeout(100)
assert page.locator("#selected-grid .selected-work").count() == 6
assert page.locator("#selected-grid .selected-column").count() == 3
assert page.locator("#selected-heading").inner_text() == "毕业照"

trigger = page.locator("#selected-grid .selected-work").first
trigger.click()
assert "#work=" in page.url
page.locator("[data-project-close]").click()
assert page.url.endswith("#collection=graduation")
assert trigger.evaluate("node => node === document.activeElement")
```

Repeat at `390×844`, assert two columns and no horizontal overflow. Add a back/forward assertion that moves between `#category=portrait`, `#collection=graduation`, and one project.

- [ ] **Step 2: Run the smoke test and verify RED.**

```powershell
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: the hash falls back to the all-project overview or the close action returns `#selected`.

- [ ] **Step 3: Carry collection metadata into the frontend project model.**

Add one display configuration and one property:

```javascript
const COLLECTIONS = {
    graduation: { title: '毕业照', category: 'portrait' },
};

// In getPortfolioProjects():
collection: group.collection || '',
```

Keep the existing `projectIdFor(group, index)` implementation. Because new groups are appended, all 12 existing project IDs remain stable.

- [ ] **Step 4: Implement one overview renderer shared by category and collection states.**

Extract the current column creation into `renderProjectOverview(projects, options)` where `options.columnMode` accepts `responsive` or `fixed-three`. Then implement:

```javascript
function renderCollection(collectionId) {
    const collection = COLLECTIONS[collectionId];
    if (!collection) return false;
    const projects = getPortfolioProjects()
        .filter(project => project.collection === collectionId)
        .sort((a, b) => a.date.localeCompare(b.date));
    document.getElementById('selected-heading').textContent = collection.title;
    renderProjectOverview(projects, { columnMode: 'fixed-three' });
    return true;
}
```

`fixed-three` means three explicit columns above 800px and two at/below 800px. It may create empty columns when the injected fixture has fewer items, matching the existing performance/landscape behavior; it must never duplicate a work.

- [ ] **Step 5: Parse collection hashes and remember the originating overview.**

Add `let projectReturnHash = '#selected';`. Immediately before replacing the overview hash in `openProject`, capture the current overview state:

```javascript
const currentHash = location.hash || '#selected';
if (!currentHash.startsWith('#work=')) projectReturnHash = currentHash;
```

In `closeProject()`, replace the hard-coded `#selected` with `projectReturnHash`. In `parsePortfolioHash()`, handle a valid `collection` before category rendering:

```javascript
const collectionId = params.get('collection');
if (collectionId && renderCollection(collectionId)) return;
```

Reset `#selected` heading text for the all-project state and category labels for category states. Unknown collection IDs fall back to Selected Works without throwing.

- [ ] **Step 6: Preserve focus, fades, containment, and reduced motion.**

Collection covers must continue to use `createSelectedWork()`, which already supplies a button, `aria-label`, lazy/eager loading, error fallback, and `enableImageLoadFade()`. Do not create a second cover component. Ensure the existing focus restoration points to the collection cover that opened the project.

- [ ] **Step 7: Run Task 3 checks and verify GREEN.**

```powershell
node --check script.js
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: injected desktop/mobile collection, navigation, project open/close, focus, and history assertions pass; all earlier checks remain green.

- [ ] **Step 8: Commit the collection route and view.**

```powershell
git add -- script.js style.css tests/site_smoke_test.py
git commit -m "feat: add graduation collection overview"
```

---

### Task 4: Import the five new graduation groups through the existing CMS/R2 flow

**Files:**
- Modify through CMS export: `data.js`
- Modify: `upload-tool/tests/test_static_frontend.py:65-145`
- Modify: `tests/site_smoke_test.py:280-470`
- Runtime only, ignored by Git: `upload-tool/cms_config.json`, `upload-tool/site_content.sqlite`

**Interfaces:**
- Consumes: Task 1 `collection` persistence, Task 3 `COLLECTIONS.graduation`, the existing local CMS on `127.0.0.1:8090`, and the five source directories below.
- Produces: 17 total groups, 100 total photos, exactly six `collection === 'graduation'` groups and 45 graduation photos. The original first 12 groups remain in their current order.

- [ ] **Step 1: Write failing final content assertions before uploading.**

Update `test_curated_photo_group_titles_dates_and_counts` by appending these five expected groups after the existing 12:

```python
{"title": "徐浩蓝毕业照", "date": "2023-06-06", "count": 6},
{"title": "沈媛毕业照", "date": "2023-06-09", "count": 9},
{"title": "洪媛玥毕业照", "date": "2024-06-09", "count": 7},
{"title": "24届吉协毕业照", "date": "2024-06-16", "count": 4},
{"title": "25届焦点毕业照", "date": "2025-06-24", "count": 10},
```

Add one reusable VM helper to `StaticFrontendTests`:

```python
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
```

Then add an exact collection test:

```python
def test_graduation_collection_inventory(self):
    groups = self._evaluate_data_js(
        "photoGroups.filter(group => group.collection === 'graduation')"
        ".map(({title,date,images}) => ({title,date,count:images.length}))"
        ".sort((a,b) => a.date.localeCompare(b.date))"
    )
    self.assertEqual(groups, [
        {"title": "徐浩蓝毕业照", "date": "2023-06-06", "count": 6},
        {"title": "沈媛毕业照", "date": "2023-06-09", "count": 9},
        {"title": "留别III", "date": "2024-06-03", "count": 9},
        {"title": "洪媛玥毕业照", "date": "2024-06-09", "count": 7},
        {"title": "24届吉协毕业照", "date": "2024-06-16", "count": 4},
        {"title": "25届焦点毕业照", "date": "2025-06-24", "count": 10},
    ])
```

Update smoke totals to 17/100 and add real-data assertions for six graduation covers and 45 graduation photos.

- [ ] **Step 2: Run static and smoke tests and verify RED.**

```powershell
python -m unittest upload-tool.tests.test_static_frontend -v
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: 12/64 differs from 17/100 and the real graduation collection is absent.

- [ ] **Step 3: Prepare an isolated CMS runtime from the current tracked frontend data.**

Verify exact paths, then copy only the ignored R2 configuration into the worktree. Do not print its contents:

```powershell
$mainConfig = 'E:\文档\my-website\upload-tool\cms_config.json'
$worktreeConfig = 'E:\文档\my-website\.worktrees\yundongshu-portfolio-refactor\upload-tool\cms_config.json'
$worktreeDb = 'E:\文档\my-website\.worktrees\yundongshu-portfolio-refactor\upload-tool\site_content.sqlite'
Resolve-Path -LiteralPath $mainConfig
Resolve-Path -LiteralPath (Split-Path -Parent $worktreeConfig)
if (Test-Path -LiteralPath $worktreeDb) { throw "Stop: worktree CMS database already exists; inspect it before replacement." }
Copy-Item -LiteralPath $mainConfig -Destination $worktreeConfig
python upload-tool/cms_server.py
```

Expected server output: `CMS running at http://127.0.0.1:8090`. First launch creates schema v3 and seeds exactly 12/64 from the feature branch `data.js`.

- [ ] **Step 4: Verify R2 health and preserve the existing `留别III` URLs before mutation.**

Open `http://127.0.0.1:8090/cms.html`. Confirm health is configured/healthy. Capture the nine current `留别III` URLs from `/api/state` for the post-import equality assertion; do not include upload credentials in logs or commits.

- [ ] **Step 5: Mark `留别III` as graduation without altering its media.**

Use the CMS group editor to set only `合集标记 = graduation`. Confirm title `留别III`, date `2024-06-03`, nine item IDs, sort order, and all nine URLs remain unchanged.

- [ ] **Step 6: Create and upload each new group in deterministic filename order.**

For each row, create `category=portrait`, `collection=graduation`, `cols=3`, the exact title/date, then open the group and set the file input to all listed directory images sorted by filename:

| Title | Date | Source directory | Expected |
|---|---|---|---:|
| 徐浩蓝毕业照 | 2023-06-06 | `2023_06_06_杭州_徐浩蓝毕业照` | 6 |
| 沈媛毕业照 | 2023-06-09 | `2023_06_09_杭州_沈媛毕业照` | 9 |
| 洪媛玥毕业照 | 2024-06-09 | `2024_06_09_杭州_洪媛玥毕业照` | 7 |
| 24届吉协毕业照 | 2024-06-16 | `2024_06_16_杭州_24届吉协毕业照` | 4 |
| 25届焦点毕业照 | 2025-06-24 | `2025_06_24_杭州_25届焦点毕业照` | 10 |

Use the existing multi-file uploader so each image is compressed with the current parameters and uploaded through `/api/photo-items/upload`. If a request reports response loss, use the existing retry action so its idempotency key and encoded blob are reused. After each group, compare the CMS count with the table before moving to the next group.

- [ ] **Step 7: Roll back any incomplete new group before continuing.**

If a group cannot reach its expected count after retry, stop. Use the CMS group delete action for that new group only; the server resolves its exact item URLs and deletes those R2 keys before cascading the SQLite rows. Do not delete or alter `留别III` and do not use a broad R2 prefix deletion.

- [ ] **Step 8: Export only after all five new groups are complete.**

Use the CMS export action or `POST /api/export`. Confirm `data.js` now contains 17 groups, 100 photos, six `collection: "graduation"` records, and the 12 original groups occupy indices 0 through 11.

- [ ] **Step 9: Run final content checks and verify GREEN.**

```powershell
python -m unittest upload-tool.tests.test_static_frontend -v
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: exact 17/100 and 6/45 inventories pass; all existing smoke checks remain green.

- [ ] **Step 10: Commit the imported content and its assertions.**

```powershell
git add -- data.js upload-tool/tests/test_static_frontend.py tests/site_smoke_test.py
git commit -m "content: add graduation photo collection"
```

Do not add `cms_config.json`, `site_content.sqlite`, backups, temp media, or credentials.

---

### Task 5: Full regression, visual verification, and clean handoff

**Files:**
- Modify only if a verified defect is found: `common.js`, `script.js`, `style.css`, or their focused tests
- Inspect: all commits since `f43f624`

**Interfaces:**
- Consumes: final 17/100 frontend data, grouped navigation, collection state, and the existing test/runtime configuration.
- Produces: evidence that desktop/mobile presentation, content integrity, accessibility, performance-sensitive loading, and repository cleanliness satisfy the spec.

- [ ] **Step 1: Run the complete repository test suite from a fresh command.**

```powershell
python -m unittest discover -s upload-tool/tests -p "test_*.py"
node upload-tool/tests/check_cms_script.mjs
node --check common.js
node --check script.js
node --check data.js
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: every command exits `0`; Python suite count is at least the 125-test baseline plus new tests; smoke output is `site smoke checks passed`.

- [ ] **Step 2: Verify the actual content inventory with a direct Node VM read.**

```powershell
node -e "const fs=require('fs'),vm=require('vm');const c={};vm.createContext(c);vm.runInContext(fs.readFileSync('data.js','utf8'),c);const g=vm.runInContext('photoGroups',c);const s=g.filter(x=>x.collection==='graduation');console.log(JSON.stringify({groups:g.length,photos:g.reduce((n,x)=>n+x.images.length,0),graduationGroups:s.length,graduationPhotos:s.reduce((n,x)=>n+x.images.length,0),titles:s.slice().sort((a,b)=>a.date.localeCompare(b.date)).map(x=>x.title)}))"
```

Expected: `groups=17`, `photos=100`, `graduationGroups=6`, `graduationPhotos=45`, and the six approved titles in chronological order.

- [ ] **Step 3: Inspect desktop `1280×720`.**

Open `index.html#collection=graduation` and verify: fixed scrollbar-free sidebar; correct section headings and indent; graduation child current state plus portrait ancestor state; six uncropped covers in three columns; no title overlay; no horizontal overflow; image load fade; opening and closing every group returns to the collection.

- [ ] **Step 4: Inspect mobile `390×844`.**

Verify: collapsed menu by default; expanded hierarchy remains readable and scrolls only within `46dvh` if needed; selecting graduation closes the menu; six covers render in two columns; no horizontal overflow; a portrait and a landscape project image each fit inside the viewport without page scrolling.

- [ ] **Step 5: Exercise keyboard and reduced motion manually.**

Tab to the graduation link and each cover, use Enter/Space to open, ArrowLeft/ArrowRight to change slides, and Escape to return. Emulate `prefers-reduced-motion: reduce` and verify fades are removed while focus, counters, routes, and slide changes still work.

- [ ] **Step 6: Review the final diff for scope and credentials.**

```powershell
git diff --check f43f624..HEAD
git diff --stat f43f624..HEAD
git status --short --branch
git ls-files | Select-String -Pattern 'cms_config\.json|site_content\.sqlite|\.env$'
```

Expected: no whitespace errors, only planned tracked files changed, clean branch, and no runtime credentials/database added.

- [ ] **Step 7: Open the local preview for user review.**

Open the absolute file URL ending in `index.html#collection=graduation` in the Codex preview panel. Report the exact commit list, tests, final inventory, and the fact that the original source directory was unchanged. Do not push or merge unless the user separately requests it.
