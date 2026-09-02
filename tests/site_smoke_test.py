"""Browser-level regression checks for the public static portfolio.

Run after installing ``tests/requirements.txt`` and Playwright Chromium.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright


SITE_ROOT = Path(__file__).resolve().parents[1]


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
    assert page.locator("button.selected-work").count() == 12
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
    assert page.locator("button.media-image").count() == 3
    assert page.locator(".media-image:not(button)").count() == 0
    assert page.locator("#lightbox[role='dialog'][aria-modal='true']").count() == 1
    assert page.locator("button.lightbox-close").count() == 1

    first_image = page.locator("button.media-image").first
    first_image.focus()
    page.keyboard.press("Enter")
    assert page.locator("#lightbox.active").count() == 1
    assert page.locator("#lightbox .lightbox-close:focus").count() == 1
    page.keyboard.press("Escape")
    assert first_image.evaluate("element => element === document.activeElement")
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


def assert_reduced_motion_is_respected(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.emulate_media(reduced_motion="reduce")
    page.goto((SITE_ROOT / "index.html").as_uri(), wait_until="domcontentloaded")
    assert page.locator("html").evaluate("element => getComputedStyle(element).scrollBehavior") == "auto"
    page.close()


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
    mobile.locator(".portfolio-nav a[data-nav-link][href='about.html']").click()
    assert mobile.locator("[data-menu-toggle]").get_attribute("aria-expanded") == "false"
    mobile.close()


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


def assert_video_and_about_are_restrained(browser):
    video_page = open_page(browser, "videos", width=1280, height=720)
    assert video_page.locator("#video-grid .video-work").count() == 15
    assert video_page.locator("#video-grid iframe").count() == 0
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
            assert_photo_project_viewer(browser)
            assert_video_and_about_are_restrained(browser)
            assert_minimal_commercial_overview(browser)
            assert_public_pages(browser)
            assert_interactions_are_accessible(browser)
            assert_commercial_detail_is_accessible(browser)
            assert_missing_commercial_covers_have_clean_fallback(browser)
            assert_media_loading_is_deliberate(browser)
            assert_reduced_motion_is_respected(browser)
            assert_font_loading_is_declared_in_markup(browser)
        finally:
            browser.close()
    print("site smoke checks passed")


if __name__ == "__main__":
    main()
