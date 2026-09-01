# Minimalist Portfolio Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the public portfolio into a restrained, image-led presentation with a fixed responsive navigation shell, ratio-preserving Selected Works, statement-first project viewers, and preserved content/routes.

**Architecture:** Keep the existing static HTML/CSS/JavaScript stack and generated content files. `common.js` owns the shared shell, `script.js` owns the photographic overview/viewer, a new `videos.js` owns video loading, and the existing commercial scripts own their respective overview and detail states. Browser-level tests exercise the rendered contract before each implementation slice.

**Tech Stack:** Static HTML5, CSS3, browser JavaScript, Python Playwright smoke tests, existing Node/Python tooling

**Spec:** `docs/superpowers/specs/2026-09-01-yundongshu-portfolio-refactor-design.md`

## Global Constraints

- Do not edit generated `data.js` or `commercial.js`; SQLite remains the only CMS source of truth.
- Preserve `index.html`, `videos.html`, `commercial.html`, `commercial-detail.html?project=<id>`, and `about.html` public entry points.
- Preserve 12 photographic groups, 70 photographic images, 15 videos, 3 commercial projects, 10 commercial media items, all About content, and source order.
- Do not migrate frameworks, add runtime dependencies, copy reference-site content, or invent project prose, alt-text facts, identity data, awards, or clients.
- Remove the user-authorized top/sub navigation, random/timeline mode, year/month filters, filter sidebar, title/count/watermark overlays, and duplicate footer presentation.
- Preserve existing metadata, favicon, robots, R2 URLs, lazy loading, first-image priority, video click-to-load, external-link safety, commercial missing-cover fallback, and reduced-motion behavior.
- Preserve uncropped image ratios. Overview images use natural height; project images use `object-fit: contain`.
- Do not stage or modify the user's unrelated `DESIGN-claude.md`, `DESIGN-nike.md`, `upload-tool/r2-upload.js`, or untracked `AGENTS.md` changes.

---

## File Responsibility Map

| File | Responsibility after refactor |
|---|---|
| `common.js` | Shared sidebar/top disclosure shell, active navigation, focus/menu behavior, shared lazy-image helpers |
| `style.css` | Shared shell, Selected Works, photo viewer, videos, About, accessibility, responsive and reduced-motion styles |
| `index.html` | Minimal Selected Works and photo-viewer semantic containers |
| `script.js` | Deterministic photo-project mapping, overview columns, hash state, statement/image slides, pointer/keyboard/focus behavior |
| `videos.html` | Minimal video main region using the shared shell |
| `videos.js` | Existing video placeholder and click-to-load behavior extracted from `script.js` |
| `about.html` | Existing content in a restrained biography/portrait structure |
| `commercial.html` | Minimal commercial overview container |
| `commercial-list.js` | Existing project data rendered as uncluttered overview cards |
| `commercial-detail.html` | Semantic statement/media viewer container while preserving `?project=` |
| `commercial-detail.js` | Commercial statement-first media sequence and focus-safe navigation |
| `commercial.css` | Only commercial overview/detail differences from shared styles |
| `tests/site_smoke_test.py` | Route/content integrity and observable desktop/mobile interaction contract |

---

### Task 1: Shared Portfolio Shell and Mobile Disclosure

**Files:**
- Modify: `tests/site_smoke_test.py`
- Modify: `common.js`
- Modify: `style.css`

**Interfaces:**
- Consumes: existing empty `<nav class="navbar"></nav>` placeholder on every public page and the current path/hash.
- Produces: `renderPortfolioShell()`, `setMenuExpanded(expanded)`, `updateActiveNavigation()`, `.portfolio-shell`, `.portfolio-sidebar`, `.portfolio-nav`, and `[data-menu-toggle]` used by every later task.

- [ ] **Step 1: Record a green baseline before editing**

Run:

```powershell
python -m unittest discover -s upload-tool/tests -p "test_*.py"
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
```

Expected: unit suite exits 0 with only the known Windows symlink skip; site smoke prints `site smoke checks passed`.

- [ ] **Step 2: Write failing shared-shell tests**

Add this helper and call it from `main()`:

```python
def assert_minimal_shell_and_mobile_menu(browser):
    desktop = open_page(browser, "index", width=1280, height=720)
    assert desktop.locator(".portfolio-sidebar").count() == 1
    assert desktop.locator(".portfolio-nav a").count() == 8
    assert desktop.locator(".navbar, .sub-nav, footer").count() == 0
    assert desktop.locator("[data-menu-toggle]:visible").count() == 0
    desktop.close()

    mobile = open_page(browser, "index", width=390, height=844)
    toggle = mobile.locator("[data-menu-toggle]")
    assert toggle.is_visible()
    assert toggle.get_attribute("aria-expanded") == "false"
    assert mobile.locator(".portfolio-nav").get_attribute("data-expanded") == "false"
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert mobile.locator(".portfolio-nav").get_attribute("data-expanded") == "true"
    mobile.locator(".portfolio-nav a[href='about.html']").click()
    assert mobile.locator("[data-menu-toggle]").get_attribute("aria-expanded") == "false"
    mobile.close()
```

- [ ] **Step 3: Run the new shell test and verify failure**

Run the Playwright command from Step 1.

Expected: FAIL because `.portfolio-sidebar` and `[data-menu-toggle]` do not exist and the old navbar/footer still render.

- [ ] **Step 4: Replace the old generated navbar/footer with the shared shell**

Keep `getLazyImageObserver()`, `loadLazyImage()`, and `observeLazyImage()` unchanged. Replace the DOM-ready navigation/footer code in `common.js` with these interfaces:

```javascript
const PORTFOLIO_LINKS = [
    ['index.html', 'Selected Works'],
    ['index.html#category=portrait', '人像'],
    ['index.html#category=performance', '演出'],
    ['index.html#category=landscape', '风光'],
    ['videos.html', '视频'],
    ['commercial.html', '商业项目'],
    ['about.html', 'About']
];

function setMenuExpanded(expanded) {
    const nav = document.querySelector('.portfolio-nav');
    const toggle = document.querySelector('[data-menu-toggle]');
    if (!nav || !toggle) return;
    nav.dataset.expanded = String(expanded);
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.textContent = expanded ? '关闭' : '菜单';
}

function updateActiveNavigation() {
    const current = `${location.pathname.split('/').pop() || 'index.html'}${location.hash}`;
    document.querySelectorAll('.portfolio-nav a').forEach(link => {
        const href = link.getAttribute('href');
        const active = href === current || (!location.hash && href === (current || 'index.html'));
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });
}

function renderPortfolioShell() {
    const placeholder = document.querySelector('nav.navbar');
    if (!placeholder) return;
    const shell = document.createElement('aside');
    shell.className = 'portfolio-sidebar';
    shell.innerHTML = `
        <div class="portfolio-identity">
            <a href="index.html" class="portfolio-name">沉礁</a>
            <span>杭州自由摄影师</span>
            <button type="button" data-menu-toggle aria-expanded="false" aria-controls="portfolio-navigation">菜单</button>
        </div>
        <nav class="portfolio-nav" id="portfolio-navigation" data-expanded="false" aria-label="作品集导航">
            ${PORTFOLIO_LINKS.map(([href, label]) => `<a href="${href}">${label}</a>`).join('')}
            <div class="portfolio-contact"><a href="about.html">合作：sleepylagoon2894</a></div>
        </nav>`;
    placeholder.replaceWith(shell);
    document.querySelector('footer')?.remove();
    shell.querySelector('[data-menu-toggle]').addEventListener('click', event => {
        setMenuExpanded(event.currentTarget.getAttribute('aria-expanded') !== 'true');
    });
    shell.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setMenuExpanded(false)));
    window.addEventListener('hashchange', updateActiveNavigation);
    updateActiveNavigation();
}
```

Call `renderPortfolioShell()` on DOM ready. Use DOM methods for identity and static navigation only; do not interpolate CMS content.

- [ ] **Step 5: Add the shell CSS tokens and breakpoint contract**

Consolidate existing equivalent variables instead of creating competing token sets:

```css
:root {
  --portfolio-paper: #fff;
  --portfolio-ink: #111;
  --portfolio-secondary: #666;
  --portfolio-muted: #999;
  --portfolio-rule: #f0f0f0;
  --portfolio-sidebar: 260px;
  --portfolio-main-pad: 40px;
  --portfolio-gap: clamp(12px, 1.6vw, 20px);
}

body { min-height: 100vh; min-height: 100dvh; background: var(--portfolio-paper); color: var(--portfolio-ink); }
.portfolio-sidebar { position: fixed; inset: 0 auto 0 0; width: var(--portfolio-sidebar); padding: 50px 40px; overflow-y: auto; background: #fff; }
body > main, body > .filter-bar, body > .commercial-page { margin-left: var(--portfolio-sidebar); min-width: 0; }
[data-menu-toggle] { display: none; }

@media (max-width: 1100px) and (min-width: 801px) {
  :root { --portfolio-sidebar: 220px; --portfolio-main-pad: 28px; }
  .portfolio-sidebar { padding: 40px 28px; }
}

@media (max-width: 800px) {
  :root { --portfolio-main-pad: 15px; --portfolio-gap: 10px; }
  body { display: flex; flex-direction: column; }
  .portfolio-sidebar { position: static; width: 100%; padding: 15px 20px; border-bottom: 1px solid var(--portfolio-rule); }
  body > main, body > .filter-bar, body > .commercial-page { margin-left: 0; min-height: 0; }
  [data-menu-toggle] { display: inline-flex; }
  .portfolio-nav[data-expanded='false'] { display: none; }
  .portfolio-nav[data-expanded='true'] { display: flex; max-height: 46dvh; overflow-y: auto; }
}
```

Remove the old black navbar, sub-nav, footer, pill, shadow, backdrop-filter, and duplicated mobile-nav rules after the new shell works.

- [ ] **Step 6: Run shell and baseline tests**

Run both commands from Step 1.

Expected: all existing unit tests pass; the new shell/mobile assertions pass. Existing page-specific smoke assertions may still fail only where later tasks intentionally replace old markup; record each expected failure before continuing.

- [ ] **Step 7: Commit the shared shell**

```powershell
git add -- common.js style.css tests/site_smoke_test.py
git commit -m "feat: add minimalist portfolio shell"
```

---

### Task 2: Ratio-Preserving Selected Works and Photo Project Viewer

**Files:**
- Modify: `tests/site_smoke_test.py`
- Modify: `index.html`
- Modify: `script.js`
- Modify: `style.css`

**Interfaces:**
- Consumes: `photoGroups`, `observeLazyImage(img)`, `updateActiveNavigation()`, and the shared shell.
- Produces: `getPortfolioProjects()`, `renderOverview(category)`, `openProject(projectId, slideIndex, trigger)`, `showProjectSlide(index, updateHash)`, `closeProject()`, `#selected-grid`, and `#project-viewer`.

- [ ] **Step 1: Write failing content-integrity and overview tests**

Replace old filter/random/lightbox assertions with:

```python
def assert_selected_works_contract(browser):
    page = open_page(browser, "index", width=1280, height=720)
    assert page.locator(".filter-bar, .filter-sidebar, .mode-btn, .date-filter").count() == 0
    assert page.locator("#selected-grid .selected-work").count() == 12
    assert page.locator("#selected-grid .selected-work img").count() == 12
    assert page.locator(".watermark-overlay, .overlay, .stack-count").count() == 0
    assert page.evaluate("photoGroups.reduce((n, group) => n + group.images.length, 0)") == 70
    first_sources = page.evaluate("photoGroups.map(group => group.images[0].src)")
    rendered_sources = page.locator("#selected-grid .selected-work img").evaluate_all(
        "images => images.map(image => image.src)"
    )
    assert rendered_sources == first_sources
    page.close()
```

- [ ] **Step 2: Write failing project-viewer tests**

```python
def assert_photo_project_viewer(browser):
    page = open_page(browser, "index", width=1280, height=720)
    trigger = page.locator("button.selected-work").first
    trigger.focus()
    trigger.press("Enter")
    viewer = page.locator("#project-viewer:not([hidden])")
    assert viewer.count() == 1
    assert viewer.locator(".project-statement").is_visible()
    total = page.evaluate("1 + photoGroups[0].images.length")
    assert viewer.locator("[data-slide-counter]").inner_text() == f"1 / {total}"
    viewer.press("ArrowRight")
    assert viewer.locator(".project-image").is_visible()
    assert viewer.locator("[data-slide-counter]").inner_text() == f"2 / {total}"
    viewer.locator("[data-project-prev]").click()
    assert viewer.locator("[data-slide-counter]").inner_text() == f"1 / {total}"
    viewer.locator("[data-project-prev]").click()
    assert viewer.locator("[data-slide-counter]").inner_text() == f"{total} / {total}"
    viewer.locator("[data-project-close]").click()
    assert viewer.get_attribute("hidden") is not None
    assert trigger.evaluate("element => element === document.activeElement")
    page.close()
```

- [ ] **Step 3: Run the new overview/viewer tests and verify failure**

Run the Playwright command from Task 1.

Expected: FAIL because the filter UI still exists and `#selected-grid`, `.selected-work`, and `#project-viewer` are absent.

- [ ] **Step 4: Replace the homepage markup with two explicit views**

Keep all head metadata and script data connections. Replace the filter/lightbox/footer content in `index.html` with:

```html
<main class="portfolio-main">
  <section class="selected-view" id="selected-view" aria-labelledby="selected-heading">
    <h1 class="visually-hidden" id="selected-heading">沉礁摄影作品集</h1>
    <div class="selected-grid" id="selected-grid"></div>
  </section>
  <section class="project-viewer" id="project-viewer" tabindex="-1" aria-label="摄影项目浏览器" hidden>
    <button type="button" class="project-close" data-project-close>返回作品</button>
    <div class="project-slide" data-project-slide></div>
    <button type="button" class="project-zone project-zone-prev" data-project-prev aria-label="上一张"></button>
    <button type="button" class="project-zone project-zone-next" data-project-next aria-label="下一张"></button>
    <p class="project-counter" data-slide-counter aria-live="polite"></p>
  </section>
</main>
```

- [ ] **Step 5: Implement deterministic project mapping and overview columns**

Replace the old filtering, random cover, masonry height measurement, watermark, and lightbox code in `script.js`. Preserve no video functions here; Task 3 moves them to `videos.js`.

```javascript
const CATEGORY_LABELS = { portrait: '人像', performance: '演出', landscape: '风光' };

function projectIdFor(group, index) {
    const raw = `${group.category || 'work'}-${group.date || 'undated'}-${index}`;
    return raw.toLowerCase().replace(/[^a-z0-9-]+/g, '-');
}

function getPortfolioProjects() {
    return photoGroups
        .map((group, index) => ({
            id: projectIdFor(group, index),
            category: group.category,
            categoryLabel: CATEGORY_LABELS[group.category] || group.category || '',
            title: group.title || '',
            description: group.description || '',
            date: group.date || '',
            images: Array.isArray(group.images) ? group.images : []
        }))
        .filter(project => project.images.length > 0);
}

function overviewColumnCount() {
    const width = document.getElementById('selected-grid').clientWidth;
    if (width >= 1000) return 4;
    if (width >= 700) return 3;
    return 2;
}

function renderOverview(category = 'all') {
    const grid = document.getElementById('selected-grid');
    const projects = getPortfolioProjects().filter(project => category === 'all' || project.category === category);
    const columnCount = Math.min(overviewColumnCount(), Math.max(1, projects.length));
    const chunkSize = Math.ceil(projects.length / columnCount);
    const columns = Array.from(
        { length: columnCount },
        (_, columnIndex) => projects.slice(columnIndex * chunkSize, (columnIndex + 1) * chunkSize)
    );
    grid.replaceChildren(...columns.map(projectsInColumn => createSelectedColumn(projectsInColumn)));
}
```

`createSelectedColumn(projects)` must create one `.selected-column`, one real `button.selected-work` per project, one natural-height image using `project.images[0].src`, and a conservative accessible name assembled from existing category/date/title only. Store `data-project-id` and call `openProject(project.id, 0, button)`.

- [ ] **Step 6: Implement statement-first slide state, hash restoration, and focus**

Use module-level `activeProject`, `activeSlideIndex`, and `projectReturnFocus` values. Implement these exact behaviors:

```javascript
function slideCount(project) { return 1 + project.images.length; }
function wrapSlide(index, total) { return (index % total + total) % total; }

function openProject(projectId, slideIndex = 0, trigger = document.activeElement) {
    const project = getPortfolioProjects().find(item => item.id === projectId);
    if (!project) return;
    activeProject = project;
    projectReturnFocus = trigger;
    document.getElementById('selected-view').hidden = true;
    const viewer = document.getElementById('project-viewer');
    viewer.hidden = false;
    showProjectSlide(slideIndex, true);
    viewer.focus({ preventScroll: true });
}

function showProjectSlide(index, updateHash = true) {
    const total = slideCount(activeProject);
    activeSlideIndex = wrapSlide(index, total);
    const host = document.querySelector('[data-project-slide]');
    host.replaceChildren(activeSlideIndex === 0
        ? createStatementSlide(activeProject)
        : createImageSlide(activeProject, activeSlideIndex - 1));
    document.querySelector('[data-slide-counter]').textContent = `${activeSlideIndex + 1} / ${total}`;
    if (updateHash) history.replaceState(null, '', `#work=${encodeURIComponent(activeProject.id)}&slide=${activeSlideIndex}`);
}

function closeProject() {
    document.getElementById('project-viewer').hidden = true;
    document.getElementById('selected-view').hidden = false;
    history.replaceState(null, '', '#selected');
    projectReturnFocus?.focus({ preventScroll: true });
    activeProject = null;
}
```

`createStatementSlide(project)` must omit empty title/description elements and show only category label, date, and factual image count. `createImageSlide(project, imageIndex)` must render one `img.project-image` with natural dimensions, `object-fit: contain`, lazy/eager intent, and alt text built only from title/category/date.

Handle hash forms `#category=<category>`, `#work=<id>&slide=<n>`, and `#selected`. Invalid values fall back to Selected Works without throwing.

- [ ] **Step 7: Add viewer controls, scoped keyboard behavior, and reduced motion**

Bind controls once on DOM ready:

```javascript
viewer.addEventListener('keydown', event => {
    if (!activeProject || event.target.matches('input, textarea, select')) return;
    if (event.key === 'ArrowLeft') showProjectSlide(activeSlideIndex - 1);
    else if (event.key === 'ArrowRight') showProjectSlide(activeSlideIndex + 1);
    else return;
    event.preventDefault();
});
```

Previous/next click handlers change exactly one slide. Keep the zones behind the statement/media content and counter. Add a 300ms opacity transition for normal motion and remove it under reduced motion.

- [ ] **Step 8: Add ratio-preserving 4/3/2 layout styles**

```css
.portfolio-main { margin-left: var(--portfolio-sidebar); min-width: 0; min-height: 100vh; min-height: 100dvh; padding: var(--portfolio-main-pad); }
.selected-grid { display: flex; align-items: flex-start; gap: var(--portfolio-gap); }
.selected-column { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; gap: var(--portfolio-gap); }
.selected-work { display: block; width: 100%; border: 0; padding: 0; background: transparent; overflow: visible; cursor: pointer; }
.selected-work img { display: block; width: 100%; height: auto; }
@media (hover: hover) { .selected-work img { transition: transform 280ms ease; } .selected-work:hover img { transform: scale(1.04); } }
.project-viewer { position: relative; min-height: calc(100dvh - 2 * var(--portfolio-main-pad)); display: grid; place-items: center; }
.project-slide { position: relative; z-index: 2; max-width: 100%; max-height: 85dvh; }
.project-image { display: block; max-width: 100%; max-height: 85dvh; width: auto; height: auto; object-fit: contain; }
.project-statement { width: min(500px, 100%); max-height: 80dvh; overflow-y: auto; line-height: 1.6; }
```

Remove all obsolete `.filter-*`, `.gallery-item`, `.photo-group-stacked`, `.stacked-*`, `.watermark-overlay`, and old lightbox rules only after searching HTML/JS/tests to confirm they have no remaining consumers.

- [ ] **Step 9: Run photo-view tests and full regressions**

Run both commands from Task 1.

Expected: all photo overview/viewer assertions and all unaffected regressions pass.

- [ ] **Step 10: Commit the homepage/viewer**

```powershell
git add -- index.html script.js style.css tests/site_smoke_test.py
git commit -m "feat: present selected works as project sequences"
```

---

### Task 3: Restrained Video and About Views

**Files:**
- Create: `videos.js`
- Modify: `tests/site_smoke_test.py`
- Modify: `videos.html`
- Modify: `about.html`
- Modify: `style.css`
- Modify: `script.js`

**Interfaces:**
- Consumes: `videos`, `observeLazyImage(img)`, shared shell and existing video URLs/content.
- Produces: `renderVideos()`, `loadVideoIframe(placeholder, video)`, `#video-grid .video-work`, and `.about-composition`.

- [ ] **Step 1: Write failing video/About preservation tests**

```python
def assert_video_and_about_are_restrained(browser):
    videos = open_page(browser, "videos", width=1280, height=720)
    assert videos.locator("#video-grid .video-work").count() == 15
    assert videos.locator("#video-grid iframe").count() == 0
    videos.locator("button.video-placeholder").first.click()
    assert videos.locator("#video-grid iframe").count() == 1
    videos.close()

    about = open_page(browser, "about", width=1280, height=720)
    assert about.locator(".about-composition").count() == 1
    assert about.locator(".about-image img").count() == 1
    assert about.locator(".about-links a[target='_blank']").count() == 4
    assert about.locator(".social-module, .social-icon").count() == 0
    assert "合作：sleepylagoon2894" in about.locator("main").inner_text()
    about.close()
```

- [ ] **Step 2: Run the new tests and verify failure**

Run site smoke.

Expected: FAIL because `.video-work`, `.about-composition`, and `.about-links` are absent and social card/icon markup remains.

- [ ] **Step 3: Extract video behavior into `videos.js`**

Move only the existing `loadVideos()` and `loadVideoIframe(placeholder, video)` responsibilities out of `script.js`, rename `loadVideos()` to `renderVideos()`, and initialize only when `#video-grid` exists:

```javascript
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('video-grid')) renderVideos();
});

function renderVideos() {
    const grid = document.getElementById('video-grid');
    grid.replaceChildren(...videos.map(video => createVideoWork(video)));
}
```

`createVideoWork(video)` must preserve existing titles, platform labels, posters, accessible button names, and click-to-load behavior. It must not create an iframe before activation.

- [ ] **Step 4: Simplify video and About markup without changing content**

Point `videos.html` to `videos.js` instead of `script.js`, retain `data.js`, and reduce the main markup to the existing heading plus `#video-grid`.

In `about.html`, preserve every existing paragraph, portrait URL, cooperation handle, and four external URLs. Replace social-module cards with:

```html
<main class="portfolio-main about-page">
  <div class="about-composition">
    <div class="about-text">...</div>
    <figure class="about-image">...</figure>
  </div>
  <nav class="about-links" aria-label="社交媒体">...</nav>
</main>
```

Each external link keeps `target="_blank" rel="noopener noreferrer"`. Do not add inferred biography, email domains, or platform icons.

- [ ] **Step 5: Add restrained video/About styles and remove obsolete card styles**

```css
.video-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--portfolio-gap); }
.video-work { min-width: 0; }
.about-composition { display: flex; align-items: flex-start; width: min(900px, 100%); gap: clamp(30px, 6vw, 70px); }
.about-text { flex: 1 1 560px; max-width: 560px; }
.about-image { flex: 0 1 300px; margin: 0; }
.about-image img { display: block; width: 100%; height: auto; object-fit: contain; }
.about-links { display: flex; flex-wrap: wrap; gap: 8px 20px; margin-top: 32px; }
@media (max-width: 800px) { .video-grid { grid-template-columns: 1fr; } .about-composition { gap: 20px; } }
@media (max-width: 520px) { .about-composition { flex-direction: column-reverse; } .about-image { width: min(220px, 70vw); } }
```

- [ ] **Step 6: Run video/About tests and full regressions**

Expected: 15 video placeholders, no eager iframes, one iframe after activation, one portrait, four safe external links, all biography/contact text preserved.

- [ ] **Step 7: Commit video/About views**

```powershell
git add -- videos.js videos.html about.html script.js style.css tests/site_smoke_test.py
git commit -m "feat: simplify video and about views"
```

---

### Task 4: Minimal Commercial Project Overview

**Files:**
- Modify: `tests/site_smoke_test.py`
- Modify: `commercial.html`
- Modify: `commercial-list.js`
- Modify: `commercial.css`

**Interfaces:**
- Consumes: `commercialProjects`, `getCommercialCategories()`, `getCommercialYears()`, `observeLazyImage(img)`, and existing `commercial-detail.html?project=<id>` URLs.
- Produces: `renderCommercialProjects()`, `createProjectCard(project)`, and `#project-grid .project-card` without filter/lightbox dependencies.

- [ ] **Step 1: Write failing commercial overview tests**

```python
def assert_minimal_commercial_overview(browser):
    page = open_page(browser, "commercial", width=1280, height=720, wait_ms=250)
    assert page.locator("#project-grid .project-card").count() == 3
    assert page.locator(".commercial-hero, .commercial-filters, #category-filters, #year-filter").count() == 0
    assert page.locator(".project-card[href='commercial-detail.html?project=brand-a']").count() == 1
    assert page.locator(".project-card-info").count() == 3
    assert page.locator("#lightbox").count() == 0
    page.close()
```

Retain the existing missing-cover route-abort test, changing selectors only when the new markup intentionally renames them.

- [ ] **Step 2: Run the new test and verify failure**

Expected: FAIL because hero, filter UI, and list-page lightbox still exist.

- [ ] **Step 3: Reduce commercial markup to heading and project grid**

Keep head metadata, `common.js`, generated `commercial.js`, and `commercial-list.js`. Replace the body content after the shell placeholder with:

```html
<main class="portfolio-main commercial-page">
  <header class="section-heading">
    <p class="section-kicker">Commissioned Work</p>
    <h1>商业项目</h1>
  </header>
  <section class="commercial-grid" aria-label="商业项目">
    <div id="project-grid" class="commercial-grid-inner"></div>
  </section>
</main>
```

Remove list-page lightbox markup because project cards navigate to detail pages.

- [ ] **Step 4: Simplify `commercial-list.js` to deterministic rendering**

Remove `currentCategory`, `currentYear`, `allImages`, filter initialization, list-page lightbox, sorting mutation, and filter code. Preserve source order:

```javascript
document.addEventListener('DOMContentLoaded', () => {
    if (typeof commercialProjects !== 'undefined') renderCommercialProjects();
});
document.addEventListener('data-ready', renderCommercialProjects);

function renderCommercialProjects() {
    const grid = document.getElementById('project-grid');
    if (!grid || typeof commercialProjects === 'undefined') return;
    grid.replaceChildren(...commercialProjects.map(createProjectCard));
}
```

`createProjectCard(project)` remains a real link, keeps cover/client/title/year/category/image/video counts, lazy loading, missing-cover text and `observeLazyImage()`. Place all text below the image and omit media badges over the cover.

- [ ] **Step 5: Replace card decoration with image-led styles**

```css
.commercial-grid-inner { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: clamp(30px, 5vw, 70px) var(--portfolio-gap); }
.project-card { color: inherit; text-decoration: none; }
.project-card-cover { background: #f7f7f7; }
.project-card-cover img { display: block; width: 100%; height: auto; object-fit: contain; }
.project-card-info { padding-top: 10px; }
@media (max-width: 700px) { .commercial-grid-inner { grid-template-columns: 1fr; } }
```

Remove cover crop, aspect-ratio enforcement, gradients, shadows, rounded corners, overlay badges, and old filter/hero styles.

- [ ] **Step 6: Run commercial overview and full regression tests**

Expected: three source-ordered project links, no overview filters/lightbox, missing covers still produce clean textual fallback.

- [ ] **Step 7: Commit commercial overview**

```powershell
git add -- commercial.html commercial-list.js commercial.css tests/site_smoke_test.py
git commit -m "feat: simplify commercial project overview"
```

---

### Task 5: Statement-First Commercial Detail Viewer

**Files:**
- Modify: `tests/site_smoke_test.py`
- Modify: `commercial-detail.html`
- Modify: `commercial-detail.js`
- Modify: `commercial.css`

**Interfaces:**
- Consumes: `getProjectById(id)`, `project.items`, existing query parsing and shared shell.
- Produces: `renderCommercialSequence(project)`, `setCommercialSlide(index)`, `commercialSlideCount(project)`, `.commercial-viewer`, and `[data-commercial-counter]`.

- [ ] **Step 1: Write failing commercial sequence tests**

```python
def assert_commercial_detail_sequence(browser):
    page = open_page(browser, "commercial-detail", wait_ms=250, query="?project=brand-a")
    viewer = page.locator(".commercial-viewer")
    assert viewer.count() == 1
    assert viewer.locator(".commercial-statement").is_visible()
    assert viewer.get_by_role("heading", name="2024春季广告", exact=True).count() == 1
    assert viewer.locator("[data-commercial-counter]").inner_text() == "1 / 4"
    viewer.focus()
    viewer.press("ArrowRight")
    assert viewer.locator("img.commercial-media").is_visible()
    assert viewer.locator("[data-commercial-counter]").inner_text() == "2 / 4"
    viewer.locator("[data-commercial-prev]").click()
    viewer.locator("[data-commercial-prev]").click()
    assert viewer.locator("[data-commercial-counter]").inner_text() == "4 / 4"
    assert page.get_by_role("link", name="获取报价", exact=True).count() == 1
    page.close()
```

- [ ] **Step 2: Run the new test and verify failure**

Expected: FAIL because the existing detail renders a header plus all media in a vertical grid and has no sequence counter.

- [ ] **Step 3: Replace detail markup with a semantic sequence host**

Keep `?project=` and script order. Replace header/media/lightbox markup with:

```html
<main class="portfolio-main project-detail">
  <section class="commercial-viewer" id="commercial-viewer" tabindex="-1" aria-label="商业项目浏览器">
    <a href="commercial.html" class="detail-back-link">返回商业项目</a>
    <div class="commercial-slide" data-commercial-slide></div>
    <button type="button" class="project-zone project-zone-prev" data-commercial-prev aria-label="上一项"></button>
    <button type="button" class="project-zone project-zone-next" data-commercial-next aria-label="下一项"></button>
    <p class="project-counter" data-commercial-counter aria-live="polite"></p>
  </section>
</main>
```

- [ ] **Step 4: Implement the statement/media sequence**

Remove the old detail media grid and modal lightbox. Keep existing project lookup and invalid-project redirect.

```javascript
let activeCommercialProject = null;
let commercialSlideIndex = 0;

function commercialSlideCount(project) { return 1 + project.items.length; }

function renderCommercialSequence(project) {
    activeCommercialProject = project;
    setCommercialSlide(0);
    document.getElementById('commercial-viewer').focus({ preventScroll: true });
}

function setCommercialSlide(index) {
    const total = commercialSlideCount(activeCommercialProject);
    commercialSlideIndex = (index % total + total) % total;
    const slide = document.querySelector('[data-commercial-slide]');
    slide.replaceChildren(commercialSlideIndex === 0
        ? createCommercialStatement(activeCommercialProject)
        : createCommercialMedia(activeCommercialProject.items[commercialSlideIndex - 1]));
    document.querySelector('[data-commercial-counter]').textContent = `${commercialSlideIndex + 1} / ${total}`;
}
```

`createCommercialStatement(project)` must render the existing client, title, description, year, category, and a real `about.html` “获取报价” link. `createCommercialMedia(item)` renders existing image items with `object-fit: contain` and existing video items as their current iframe/embed type. Edge pointer controls must not cover the central video controls or statement link.

- [ ] **Step 5: Add scoped navigation and reduced-motion behavior**

Bind previous/next buttons to one-step changes. Handle left/right only while `.commercial-viewer` is focused and skip input/textarea/select targets. Keep counter and statement actions above hit zones. Reuse the shared 300ms fade and reduced-motion override.

- [ ] **Step 6: Run commercial detail and full regression tests**

Expected: statement `1 / 4` for `brand-a`, three following images in stored order, wraparound, existing quotation link and invalid-project behavior retained.

- [ ] **Step 7: Commit commercial detail viewer**

```powershell
git add -- commercial-detail.html commercial-detail.js commercial.css tests/site_smoke_test.py
git commit -m "feat: browse commercial projects as sequences"
```

---

### Task 6: Responsive, Accessibility, Content Integrity, and Visual Verification

**Files:**
- Modify: `tests/site_smoke_test.py`

**Interfaces:**
- Consumes: all prior task interfaces and unchanged content globals.
- Produces: final verified public site with no new runtime API.

- [ ] **Step 1: Add exact breakpoint and overflow assertions**

```python
def assert_responsive_breakpoints(browser):
    expectations = [
        (1101, "260px", False),
        (1100, "220px", False),
        (801, "220px", False),
        (800, "800px", True),
    ]
    for width, sidebar_width, mobile in expectations:
        page = open_page(browser, "index", width=width, height=844, wait_ms=100)
        actual = page.locator(".portfolio-sidebar").evaluate("node => getComputedStyle(node).width")
        if mobile:
            assert actual == sidebar_width
            assert page.locator("[data-menu-toggle]").is_visible()
        else:
            assert actual == sidebar_width
            assert not page.locator("[data-menu-toggle]").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        page.close()
```

- [ ] **Step 2: Add content-count, route, focus, and reduced-motion assertions**

Verify all five public pages load without console errors. Evaluate generated data directly in their owning pages and assert:

```python
assert index.evaluate("photoGroups.length") == 12
assert index.evaluate("photoGroups.reduce((n, group) => n + group.images.length, 0)") == 70
assert videos.evaluate("typeof videos !== 'undefined' ? videos.length : 0") == 15
assert commercial.evaluate("commercialProjects.length") == 3
assert commercial.evaluate("commercialProjects.reduce((n, p) => n + p.items.length, 0)") == 10
```

At 390×844, assert two Selected Works columns and 10px computed gap. At 1280×720, assert the gallery's measured width selects three columns unless it reaches 1000px. Emulate reduced motion and assert thumbnail transform and slide transition durations are `0s`. Verify visible focus on sidebar links, disclosure, Selected Works buttons, viewer controls, commercial cards and About links.

- [ ] **Step 3: Run the expanded smoke test**

Run site smoke.

Expected: PASS. If an assertion fails, stop the plan and use `superpowers:systematic-debugging` before changing implementation code.

- [ ] **Step 4: Run complete automated verification**

```powershell
python -m unittest discover -s upload-tool/tests -p "test_*.py"
node --check common.js
node --check script.js
node --check videos.js
node --check commercial-list.js
node --check commercial-detail.js
$env:PYTHONPATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\pydeps'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\work\browsers'
& 'C:\Users\1222\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\site_smoke_test.py
git diff --check
```

Expected: all commands exit 0; only the known Windows symlink test may be skipped.

- [ ] **Step 5: Capture required visual evidence**

Using the existing bundled Playwright runtime, capture full-page screenshots into the external task output directory, not the repository:

```text
C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\outputs\yundongshu-refactor\desktop-1280x720.png
C:\Users\1222\Documents\Codex\2026-08-26\referenced-chatgpt-conversation-this-is-an\outputs\yundongshu-refactor\mobile-390x844.png
```

Inspect both images and interactively verify: desktop sidebar geometry, mobile collapsed/expanded menu, natural image ratios, no title/watermark overlays, statement-first project opening, one-step controls, wraparound, counter, About portrait/content, and commercial/video views.

- [ ] **Step 6: Reconcile the final content inventory**

Run:

```powershell
node -e "const fs=require('fs'),vm=require('vm'); const c={}; vm.createContext(c); vm.runInContext(fs.readFileSync('data.js','utf8').replace(/^const /gm,'var '),c); vm.runInContext(fs.readFileSync('commercial.js','utf8').replace(/^const /gm,'var '),c); console.log(JSON.stringify({photoGroups:c.photoGroups.length,photoImages:c.photoGroups.reduce((n,g)=>n+g.images.length,0),videos:c.videos.length,commercialProjects:c.commercialProjects.length,commercialItems:c.commercialProjects.reduce((n,p)=>n+p.items.length,0)}))"
```

Expected exactly:

```json
{"photoGroups":12,"photoImages":70,"videos":15,"commercialProjects":3,"commercialItems":10}
```

- [ ] **Step 7: Review the final diff for scope and user-owned changes**

```powershell
git status --short
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

Expected: only the public presentation files, `videos.js`, smoke tests, and approved spec/plan appear. The unrelated main-checkout deletions/modifications remain absent from the feature branch.

- [ ] **Step 8: Commit the expanded responsive verification tests**

```powershell
git add -- tests/site_smoke_test.py
git commit -m "test: verify responsive portfolio experience"
```

- [ ] **Step 9: Open the finished version for user review**

Open `index.html` in the Codex browser panel and provide clickable links to the desktop/mobile screenshots and changed source files. Report preserved routes/content, test commands and results, and the known first-load intrinsic-dimension limitation from the spec.
