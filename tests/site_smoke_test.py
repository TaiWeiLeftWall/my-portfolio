"""Browser-level regression checks for the public static portfolio.

Run after installing ``tests/requirements.txt`` and Playwright Chromium.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright


SITE_ROOT = Path(__file__).resolve().parents[1]
PORTRAIT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1200">
<rect width="800" height="1200" fill="#ddd"/>
</svg>"""


def open_page(
    browser,
    name: str,
    width: int = 1440,
    height: int = 1000,
    wait_ms: int = 2_300,
    query: str = "",
):
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto((SITE_ROOT / f"{name}.html").as_uri() + query, wait_until="domcontentloaded")
    page.wait_for_timeout(wait_ms)
    return page


def open_page_with_portrait_images(browser, name, width, height, query=""):
    page = browser.new_page(viewport={"width": width, "height": height})

    def route_media(route):
        if route.request.resource_type == "image":
            route.fulfill(status=200, content_type="image/svg+xml", body=PORTRAIT_SVG)
        else:
            route.continue_()

    page.route("**/*", route_media)
    page.goto((SITE_ROOT / f"{name}.html").as_uri() + query, wait_until="domcontentloaded")
    page.wait_for_timeout(100)
    return page


def assert_public_pages(browser):
    page = open_page(browser, "commercial", wait_ms=250)
    assert page.get_by_role("heading", name="商业项目", exact=True).count() == 1
    assert page.locator(".project-card").count() == 3
    page.close()

    page = open_page(browser, "index", width=390, height=844)
    assert page.locator("h1").count() == 1
    assert page.locator(".portfolio-sidebar").count() == 1
    assert page.locator("[data-menu-toggle]:visible").count() == 1
    page.close()


def assert_minimal_commercial_overview(browser):
    page = open_page(browser, "commercial", width=1280, height=720, wait_ms=250)
    assert page.locator("#project-grid .project-card").count() == 3
    assert page.locator(
        ".commercial-hero, .commercial-filters, #category-filters, #year-filter"
    ).count() == 0
    assert page.locator(
        ".project-card[href='commercial-detail.html?project=brand-a']"
    ).count() == 1
    assert page.locator(".project-card-info").count() == 3
    assert page.locator("#lightbox").count() == 0
    page.close()


def assert_interactions_are_accessible(browser):
    page = open_page(browser, "index")
    assert page.locator("nav a[aria-current='page']").count() == 1
    assert page.locator("button.selected-work").count() == 17
    assert page.locator(".selected-work:not(button)").count() == 0
    assert page.locator("button[data-project-prev]").count() == 1
    assert page.locator("button[data-project-next]").count() == 1
    page.close()

    page = open_page(browser, "about")
    for link in page.locator("a[target='_blank']").all():
        rel = (link.get_attribute("rel") or "").split()
        assert "noopener" in rel and "noreferrer" in rel
    page.close()


def assert_commercial_detail_is_accessible(browser):
    page = open_page(browser, "commercial-detail", wait_ms=250, query="?project=brand-a")
    assert page.get_by_role("link", name="返回商业项目").count() == 1
    assert page.get_by_role("link", name="获取报价", exact=True).count() == 1
    assert page.get_by_role("heading", name="2024春季广告", exact=True).count() == 1
    assert page.locator("button[data-commercial-prev]").count() == 1
    assert page.locator("button[data-commercial-next]").count() == 1
    assert page.locator("#lightbox").count() == 0
    assert page.locator(".commercial-viewer").get_attribute("tabindex") == "-1"
    page.close()


def assert_commercial_detail_sequence(browser):
    page = open_page(browser, "commercial-detail", wait_ms=250, query="?project=brand-a")
    viewer = page.locator(".commercial-viewer")
    assert viewer.count() == 1
    assert viewer.locator(".commercial-statement").is_visible()
    assert viewer.get_by_role("heading", name="2024春季广告", exact=True).count() == 1
    assert viewer.locator("[data-commercial-counter]").inner_text() == "1 / 4"
    assert page.get_by_role("link", name="获取报价", exact=True).count() == 1
    viewer.focus()
    viewer.press("ArrowRight")
    assert viewer.locator("img.commercial-media").is_visible()
    assert viewer.locator("[data-commercial-counter]").inner_text() == "2 / 4"
    viewer.locator("[data-commercial-prev]").click()
    viewer.locator("[data-commercial-prev]").click()
    assert viewer.locator("[data-commercial-counter]").inner_text() == "4 / 4"
    page.close()


def assert_missing_commercial_covers_have_clean_fallback(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.route("**/images/commercial/**", lambda route: route.abort())
    page.goto((SITE_ROOT / "commercial.html").as_uri(), wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    assert page.locator(".project-card-cover.is-missing").count() == 3
    assert page.locator(".project-card-cover.is-missing img:visible").count() == 0
    page.close()


def assert_font_loading_is_declared_in_markup(browser):
    for name in ("index", "commercial", "commercial-detail", "about", "videos"):
        query = "?project=brand-a" if name == "commercial-detail" else ""
        page = open_page(browser, name, wait_ms=100, query=query)
        assert page.locator("head > link[rel='preconnect'][href='https://fonts.gstatic.com']").count() == 1
        assert page.locator("head > link[rel='stylesheet'][href*='fonts.googleapis.com']").count() == 1
        page.close()


def assert_media_loading_is_deliberate(browser):
    page = open_page(browser, "index")
    first = page.locator(".selected-work > img:first-child").first
    assert first.get_attribute("loading") == "eager"
    assert first.get_attribute("fetchpriority") == "high"
    assert first.get_attribute("decoding") == "async"
    page.close()

    page = open_page(browser, "videos")
    assert page.locator("#video-grid iframe").count() == 0
    header_color = page.locator(".video-platform-header").first.evaluate(
        "element => getComputedStyle(element).color"
    )
    assert header_color == "rgb(17, 17, 17)"
    page.locator("button.video-placeholder").first.click()
    assert page.locator("#video-grid iframe").count() == 1
    page.close()


def assert_images_fade_after_loading(browser):
    index = open_page_with_portrait_images(browser, "index", 1280, 720)
    overview_image = index.locator(".selected-work img").first
    assert overview_image.evaluate(
        "node => node.classList.contains('image-load-fade')"
    )
    assert overview_image.evaluate(
        "node => node.classList.contains('is-loaded')"
    )

    overview_image.evaluate("node => node.classList.remove('is-loaded')")
    index.wait_for_timeout(350)
    assert overview_image.evaluate("node => getComputedStyle(node).opacity") == "0"
    overview_image.dispatch_event("load")
    index.wait_for_timeout(350)
    assert overview_image.evaluate("node => getComputedStyle(node).opacity") == "1"
    assert overview_image.evaluate(
        "node => getComputedStyle(node).transitionDuration.split(',')[0].trim()"
    ) == "0.3s"

    index.locator(".selected-work").first.click()
    index.locator("#project-viewer").press("ArrowRight")
    assert index.locator(".project-image").evaluate(
        "node => node.classList.contains('image-load-fade')"
    )
    index.close()

    commercial = open_page_with_portrait_images(browser, "commercial", 1280, 720)
    assert commercial.locator(".project-card-cover img").first.evaluate(
        "node => node.classList.contains('image-load-fade')"
    )
    commercial.close()

    detail = open_page_with_portrait_images(
        browser,
        "commercial-detail",
        1280,
        720,
        query="?project=brand-a",
    )
    detail.locator(".commercial-viewer").press("ArrowRight")
    assert detail.locator("img.commercial-media").evaluate(
        "node => node.classList.contains('image-load-fade')"
    )
    detail.close()

    about = open_page_with_portrait_images(browser, "about", 1280, 720)
    assert about.locator(".about-image img").evaluate(
        "node => node.classList.contains('image-load-fade')"
    )
    about.close()


def assert_reduced_motion_is_respected(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.emulate_media(reduced_motion="reduce")
    page.goto((SITE_ROOT / "index.html").as_uri(), wait_until="domcontentloaded")
    assert page.locator("html").evaluate("element => getComputedStyle(element).scrollBehavior") == "auto"
    assert page.locator("body").evaluate(
        "element => getComputedStyle(element).animationDuration"
    ) == "0s"
    assert page.locator(".selected-work img").first.evaluate(
        "element => getComputedStyle(element).transitionDuration"
    ) == "0s"
    assert page.locator(".selected-work img").first.evaluate(
        "element => getComputedStyle(element).opacity"
    ) == "1"
    page.locator(".selected-work").first.click()
    assert page.locator(".project-slide").evaluate(
        "element => getComputedStyle(element).animationDuration"
    ) == "0s"
    page.close()

    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.emulate_media(reduced_motion="reduce")
    page.goto(
        (SITE_ROOT / "commercial-detail.html").as_uri() + "?project=brand-a",
        wait_until="domcontentloaded",
    )
    assert page.locator(".commercial-slide").evaluate(
        "element => getComputedStyle(element).animationDuration"
    ) == "0s"
    page.close()


def assert_page_entry_fade_is_short(browser):
    for name in ("index", "videos", "commercial", "commercial-detail", "about"):
        query = "?project=brand-a" if name == "commercial-detail" else ""
        page = open_page(browser, name, wait_ms=50, query=query)
        animation = page.locator("body").evaluate(
            "node => ({ name: getComputedStyle(node).animationName, "
            "duration: getComputedStyle(node).animationDuration })"
        )
        assert animation == {"name": "pageFadeIn", "duration": "0.2s"}
        page.close()


def assert_responsive_breakpoints(browser):
    expectations = [
        (1101, "260px", False),
        (1100, "220px", False),
        (801, "220px", False),
        (800, "800px", True),
    ]
    for width, sidebar_width, mobile in expectations:
        page = open_page(browser, "index", width=width, height=844, wait_ms=100)
        actual = page.locator(".portfolio-sidebar").evaluate(
            "node => getComputedStyle(node).width"
        )
        assert actual == sidebar_width
        assert page.locator("[data-menu-toggle]").is_visible() is mobile
        assert page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
        page.close()


def assert_content_inventory_and_routes(browser):
    pages = {}
    for name in ("index", "videos", "commercial", "commercial-detail", "about"):
        errors = []
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.route(
            "**/*",
            lambda route: route.fulfill(
                status=200, content_type="image/svg+xml", body=PORTRAIT_SVG
            )
            if route.request.resource_type == "image"
            else route.continue_(),
        )
        page.on("console", lambda message, errors=errors: errors.append(message.text)
                if message.type == "error" else None)
        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
        query = "?project=brand-a" if name == "commercial-detail" else ""
        page.goto((SITE_ROOT / f"{name}.html").as_uri() + query, wait_until="domcontentloaded")
        page.wait_for_timeout(250)
        assert not errors, f"{name} emitted browser errors: {errors}"
        pages[name] = page

    assert pages["index"].evaluate("photoGroups.length") == 17
    assert pages["index"].evaluate(
        "photoGroups.reduce((n, group) => n + group.images.length, 0)"
    ) == 100
    assert pages["videos"].evaluate(
        "typeof videos !== 'undefined' ? videos.length : 0"
    ) == 15
    assert pages["commercial"].evaluate("commercialProjects.length") == 3
    assert pages["commercial"].evaluate(
        "commercialProjects.reduce((n, project) => n + project.items.length, 0)"
    ) == 10
    for page in pages.values():
        page.close()


def assert_gallery_columns_and_focus(browser):
    mobile = open_page(browser, "index", width=390, height=844, wait_ms=100)
    assert mobile.locator(".selected-column").count() == 2
    assert mobile.locator("#selected-grid").evaluate(
        "node => getComputedStyle(node).gap"
    ) == "10px"
    toggle = mobile.locator("[data-menu-toggle]")
    toggle.focus()
    assert toggle.evaluate("node => getComputedStyle(node).outlineStyle") != "none"
    mobile.close()

    desktop = open_page(browser, "index", width=1280, height=720, wait_ms=100)
    gallery_width = desktop.locator("#selected-grid").evaluate("node => node.clientWidth")
    expected_columns = 4 if gallery_width >= 1000 else 3 if gallery_width >= 700 else 2
    assert desktop.locator(".selected-column").count() == expected_columns

    sidebar_link = desktop.locator(".portfolio-nav a").first
    sidebar_link.focus()
    assert sidebar_link.evaluate("node => getComputedStyle(node).outlineStyle") != "none"
    selected = desktop.locator(".selected-work").first
    selected.focus()
    assert selected.evaluate("node => getComputedStyle(node).outlineStyle") != "none"
    selected.press("Enter")
    control = desktop.locator("[data-project-close]")
    control.focus()
    assert control.evaluate("node => getComputedStyle(node).outlineStyle") != "none"
    desktop.close()

    commercial = open_page(browser, "commercial", wait_ms=250)
    card = commercial.locator(".project-card").first
    card.focus()
    assert card.evaluate("node => getComputedStyle(node).outlineStyle") != "none"
    commercial.close()

    about = open_page(browser, "about", wait_ms=100)
    social_link = about.locator(".about-links a").first
    social_link.focus()
    assert social_link.evaluate("node => getComputedStyle(node).outlineStyle") != "none"
    about.close()


def assert_sparse_categories_keep_grid_columns(browser):
    for category in ("performance", "landscape"):
        desktop = open_page(
            browser,
            "index",
            width=1280,
            height=720,
            wait_ms=100,
            query=f"#category={category}",
        )
        assert desktop.locator(".selected-column").count() == 3
        assert desktop.locator(".selected-work").count() == 1
        desktop.close()

        mobile = open_page(
            browser,
            "index",
            width=390,
            height=844,
            wait_ms=100,
            query=f"#category={category}",
        )
        assert mobile.locator(".selected-column").count() == 2
        assert mobile.locator(".selected-work").count() == 1
        mobile.close()


def assert_minimal_shell_and_mobile_menu(browser):
    desktop = open_page(browser, "index", width=1280, height=720)
    assert desktop.locator(".portfolio-sidebar").count() == 1
    assert desktop.locator(".portfolio-nav-section").count() == 3
    assert desktop.locator(".portfolio-nav-heading").all_inner_texts() == [
        "PROJECTS 项目",
        "EDITORIAL",
        "INFO",
    ]
    assert desktop.locator(".portfolio-nav a[data-nav-link]").count() == 8
    projects = desktop.locator(".portfolio-nav-section").first
    portrait_item = projects.locator(".portfolio-nav-item").first
    assert portrait_item.locator(
        ":scope > a[href='index.html#category=portrait']"
    ).inner_text() == "人像"
    graduation = portrait_item.locator(
        ".portfolio-nav-child[href='index.html#collection=graduation']"
    )
    assert graduation.count() == 1
    assert graduation.inner_text() == "毕业照"
    assert desktop.locator(".portfolio-contact").count() == 0
    assert desktop.locator(
        ".portfolio-nav a[data-nav-link][href='about.html']"
    ).inner_text() == "关于我"
    assert desktop.locator(".portfolio-sidebar").evaluate(
        "node => ({ position: getComputedStyle(node).position, "
        "overflowY: getComputedStyle(node).overflowY })"
    ) == {"position": "fixed", "overflowY": "hidden"}
    assert desktop.locator(".navbar, .sub-nav, footer").count() == 0
    assert desktop.locator("[data-menu-toggle]:visible").count() == 0
    desktop.close()

    collection = open_page(
        browser,
        "index",
        width=1280,
        height=720,
        query="#collection=graduation",
    )
    active_child = collection.locator(
        ".portfolio-nav-child[href='index.html#collection=graduation']"
    )
    portrait_parent = collection.locator(
        ".portfolio-nav a[href='index.html#category=portrait']"
    )
    assert active_child.get_attribute("aria-current") == "page"
    assert "active" in (active_child.get_attribute("class") or "").split()
    assert "ancestor-active" in (
        portrait_parent.get_attribute("class") or ""
    ).split()
    assert portrait_parent.get_attribute("aria-current") is None
    collection.close()

    mobile = open_page(browser, "index", width=390, height=844)
    toggle = mobile.locator("[data-menu-toggle]")
    assert toggle.is_visible()
    assert mobile.locator(".portfolio-sidebar").evaluate(
        "node => ({ position: getComputedStyle(node).position, "
        "overflowY: getComputedStyle(node).overflowY })"
    ) == {"position": "static", "overflowY": "visible"}
    assert toggle.get_attribute("aria-expanded") == "false"
    assert mobile.locator(".portfolio-nav").get_attribute("data-expanded") == "false"
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert mobile.locator(".portfolio-nav").get_attribute("data-expanded") == "true"
    mobile.locator(".portfolio-nav a[data-nav-link][href='about.html']").click()
    assert mobile.locator("[data-menu-toggle]").get_attribute("aria-expanded") == "false"
    mobile.close()


def assert_selected_works_contract(browser):
    page = open_page(browser, "index", width=1280, height=720)
    assert page.locator(".filter-bar, .filter-sidebar, .mode-btn, .date-filter").count() == 0
    assert page.locator("#selected-grid .selected-work").count() == 17
    assert page.locator("#selected-grid .selected-work img").count() == 17
    assert page.locator(".watermark-overlay, .overlay, .stack-count").count() == 0
    assert page.evaluate("photoGroups.reduce((n, group) => n + group.images.length, 0)") == 100
    first_sources = page.evaluate("photoGroups.map(group => group.images[0].src)")
    rendered_sources = page.locator("#selected-grid .selected-work img").evaluate_all(
        "images => images.map(image => image.src)"
    )
    assert rendered_sources == first_sources
    page.close()


def assert_real_graduation_inventory(browser):
    page = open_page(
        browser,
        "index",
        width=1280,
        height=720,
        query="#collection=graduation",
    )
    assert page.evaluate(
        "photoGroups.filter(group => group.collection === 'graduation').length"
    ) == 6
    assert page.evaluate(
        "photoGroups.filter(group => group.collection === 'graduation')"
        ".reduce((total, group) => total + group.images.length, 0)"
    ) == 45
    assert page.locator("#selected-grid .selected-work").count() == 6
    assert page.locator("#selected-grid .selected-column").count() == 3
    page.close()


def assert_photo_project_viewer(browser):
    page = open_page(browser, "index", width=1280, height=720)
    trigger = page.locator("button.selected-work").first
    trigger.focus()
    trigger.press("Enter")
    viewer = page.locator("#project-viewer")
    assert viewer.get_attribute("hidden") is None
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


def mark_first_six_as_graduation(page):
    page.evaluate(
        "photoGroups.forEach(group => { group.collection = ''; });"
        "photoGroups.slice(0, 6).forEach(group => "
        "{ group.collection = 'graduation'; });"
    )


def assert_graduation_collection_state(browser):
    desktop = open_page(browser, "index", width=1280, height=720)
    mark_first_six_as_graduation(desktop)
    desktop.evaluate("location.hash = 'category=portrait'")
    desktop.wait_for_timeout(100)
    desktop.evaluate("location.hash = 'collection=graduation'")
    desktop.wait_for_timeout(100)

    assert desktop.locator("#selected-heading").inner_text() == "毕业照"
    assert desktop.locator("#selected-grid .selected-work").count() == 6
    assert desktop.locator("#selected-grid .selected-column").count() == 3
    assert desktop.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )

    desktop.set_viewport_size({"width": 390, "height": 844})
    desktop.wait_for_timeout(250)
    assert desktop.locator("#selected-heading").inner_text() == "毕业照"
    assert desktop.locator("#selected-grid .selected-work").count() == 6
    assert desktop.locator("#selected-grid .selected-column").count() == 2
    desktop.set_viewport_size({"width": 1280, "height": 720})
    desktop.wait_for_timeout(250)
    assert desktop.locator("#selected-grid .selected-column").count() == 3

    trigger = desktop.locator("#selected-grid .selected-work").first
    trigger.focus()
    trigger.press("Enter")
    assert "#work=" in desktop.url
    desktop.locator("[data-project-close]").click()
    assert desktop.url.endswith("#collection=graduation")
    assert trigger.evaluate("node => node === document.activeElement")

    trigger.press("Enter")
    desktop.go_back(wait_until="domcontentloaded")
    desktop.wait_for_timeout(100)
    assert desktop.url.endswith("#collection=graduation")
    assert desktop.locator("#selected-grid .selected-work").count() == 6
    desktop.go_back(wait_until="domcontentloaded")
    desktop.wait_for_timeout(100)
    assert desktop.url.endswith("#category=portrait")
    desktop.go_forward(wait_until="domcontentloaded")
    desktop.wait_for_timeout(100)
    assert desktop.url.endswith("#collection=graduation")
    desktop.go_forward(wait_until="domcontentloaded")
    desktop.wait_for_timeout(100)
    assert "#work=" in desktop.url
    assert desktop.locator("#project-viewer").get_attribute("hidden") is None
    desktop.close()

    mobile = open_page(browser, "index", width=390, height=844)
    mark_first_six_as_graduation(mobile)
    mobile.evaluate("location.hash = 'collection=graduation'")
    mobile.wait_for_timeout(100)
    assert mobile.locator("#selected-grid .selected-work").count() == 6
    assert mobile.locator("#selected-grid .selected-column").count() == 2
    assert mobile.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    mobile.close()


def assert_box_within_viewport(page, selector, width, height):
    box = page.locator(selector).bounding_box()
    assert box is not None
    assert box["x"] >= 0 and box["y"] >= 0
    assert box["x"] + box["width"] <= width + 1
    assert box["y"] + box["height"] <= height + 1


def assert_single_media_fits_viewport(browser):
    for width, height in ((1280, 720), (390, 844)):
        page = open_page_with_portrait_images(
            browser,
            "index",
            width,
            height,
            query="",
        )
        trigger = page.locator(".selected-work").first
        trigger.focus()
        page.evaluate("window.scrollTo(0, 300)")
        previous_scroll = page.evaluate("window.scrollY")
        assert previous_scroll > 0
        trigger.evaluate("node => node.click()")
        viewer = page.locator("#project-viewer")
        viewer.press("ArrowRight")
        assert page.evaluate("window.scrollY") == 0
        assert page.locator("body").evaluate(
            "node => getComputedStyle(node).overflowY"
        ) == "hidden"
        assert_box_within_viewport(page, ".project-image", width, height)
        page.mouse.wheel(0, 1000)
        page.wait_for_timeout(50)
        assert page.evaluate("window.scrollY") == 0
        viewer.locator("[data-project-close]").click()
        assert abs(page.evaluate("window.scrollY") - previous_scroll) <= 1
        page.close()

        commercial = open_page_with_portrait_images(
            browser,
            "commercial-detail",
            width,
            height,
            query="?project=brand-a",
        )
        commercial.locator(".commercial-viewer").press("ArrowRight")
        assert commercial.locator("body").evaluate(
            "node => getComputedStyle(node).overflowY"
        ) == "hidden"
        assert_box_within_viewport(
            commercial, "img.commercial-media", width, height
        )
        commercial.mouse.wheel(0, 1000)
        commercial.wait_for_timeout(50)
        assert commercial.evaluate("window.scrollY") == 0
        commercial.close()


def assert_video_and_about_are_restrained(browser):
    video_page = open_page(browser, "videos", width=1280, height=720)
    assert video_page.locator("#video-grid .video-work").count() == 15
    assert video_page.locator("#video-grid iframe").count() == 0
    assert video_page.locator(".video-work").first.evaluate(
        "node => getComputedStyle(node, '::before').content"
    ) == "none"
    video_page.locator("button.video-placeholder").first.click()
    assert video_page.locator("#video-grid iframe").count() == 1
    video_page.close()

    about = open_page(browser, "about", width=1280, height=720)
    assert about.locator(".about-composition").count() == 1
    assert about.locator(".about-image img").count() == 1
    assert about.locator(".about-links a[target='_blank']").count() == 4
    assert about.locator(".social-module, .social-icon").count() == 0
    assert "合作：sleepylagoon2894" in about.locator("main").inner_text()
    about.close()


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            assert_minimal_shell_and_mobile_menu(browser)
            assert_selected_works_contract(browser)
            assert_real_graduation_inventory(browser)
            assert_photo_project_viewer(browser)
            assert_graduation_collection_state(browser)
            assert_single_media_fits_viewport(browser)
            assert_video_and_about_are_restrained(browser)
            assert_minimal_commercial_overview(browser)
            assert_public_pages(browser)
            assert_interactions_are_accessible(browser)
            assert_commercial_detail_is_accessible(browser)
            assert_commercial_detail_sequence(browser)
            assert_missing_commercial_covers_have_clean_fallback(browser)
            assert_media_loading_is_deliberate(browser)
            assert_images_fade_after_loading(browser)
            assert_page_entry_fade_is_short(browser)
            assert_reduced_motion_is_respected(browser)
            assert_font_loading_is_declared_in_markup(browser)
            assert_responsive_breakpoints(browser)
            assert_content_inventory_and_routes(browser)
            assert_gallery_columns_and_focus(browser)
            assert_sparse_categories_keep_grid_columns(browser)
        finally:
            browser.close()
    print("site smoke checks passed")


if __name__ == "__main__":
    main()
