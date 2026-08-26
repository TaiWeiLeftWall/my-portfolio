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
    assert "品牌广告 · 产品拍摄 · 视频制作" in page.locator(".commercial-hero").inner_text()
    assert page.locator("#lightbox[role='dialog'][aria-modal='true']").count() == 1
    assert page.locator("button.lightbox-close").count() == 1
    assert page.locator("#year-filter[aria-label='年份']").count() == 1
    assert page.locator("#category-filters .category-btn[aria-pressed]").count() == 4
    assert page.locator("#category-filters .category-btn.active[aria-pressed='true']").count() == 1
    page.close()

    page = open_page(browser, "index", width=390, height=844)
    assert page.locator("h1").count() == 1
    assert page.locator("nav a:visible").count() == 4
    assert page.locator(".filter-sidebar button:visible, .filter-sidebar select:visible").count() >= 7
    for control in page.locator(".filter-sidebar button:visible, .filter-sidebar select:visible").all():
        assert control.bounding_box()["height"] >= 44
    for link in page.locator(".nav-links a:visible").all():
        assert link.bounding_box()["height"] >= 44
    page.close()


def assert_interactions_are_accessible(browser):
    page = open_page(browser, "index")
    assert page.locator("nav a[aria-current='page']").count() == 1
    assert page.locator(".mode-btn[aria-pressed]").count() == 2
    assert page.locator(".mode-btn.active[aria-pressed='true']").count() == 1
    assert page.locator("#year-filter[aria-label='年份']").count() == 1
    assert page.locator("#month-filter[aria-label='月份']").count() == 1
    assert page.locator("button.gallery-item, button.stacked-cover").count() > 0
    assert page.locator(".gallery-item:not(button), .stacked-cover:not(button)").count() == 0
    assert page.locator("#lightbox[role='dialog'][aria-modal='true']").count() == 1
    assert page.locator("button.lightbox-close").count() == 1

    first_tile = page.locator("button.gallery-item, button.stacked-cover").first
    first_tile.focus()
    page.keyboard.press("Enter")
    assert page.locator("#lightbox.active").count() == 1
    assert page.locator("#lightbox .lightbox-close:focus").count() == 1
    page.keyboard.press("Escape")
    assert page.locator("#lightbox.active").count() == 0
    assert first_tile.evaluate("element => element === document.activeElement")
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


def assert_random_mode_uses_displayed_images(browser):
    page = open_page(browser, "index")
    page.evaluate(
        """
        const groupCount = photoGroups.length;
        let call = 0;
        Math.random = () => call++ < groupCount ? 0 : 0.999999;
        """
    )
    page.get_by_role("button", name="随机", exact=True).click()
    displayed = page.locator(".gallery-item > img:first-child").evaluate_all(
        "images => images.map(image => image.src)"
    )
    lightbox_sources = page.evaluate("allImages.map(image => image.src)")
    assert sorted(displayed) == sorted(lightbox_sources)
    page.close()


def assert_media_loading_is_deliberate(browser):
    page = open_page(browser, "index")
    first = page.locator(".gallery-item > img:first-child, .stacked-cover > img:first-child").first
    assert first.get_attribute("loading") == "eager"
    assert first.get_attribute("fetchpriority") == "high"
    assert first.get_attribute("decoding") == "async"
    page.close()

    page = open_page(browser, "videos")
    assert page.locator("#video-grid iframe").count() == 0
    header_color = page.locator(".video-platform-header").first.evaluate(
        "element => getComputedStyle(element).color"
    )
    assert header_color == "rgb(29, 29, 31)"
    page.locator("button.video-placeholder").first.click()
    assert page.locator("#video-grid iframe").count() == 1
    page.close()


def assert_reduced_motion_is_respected(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.emulate_media(reduced_motion="reduce")
    page.goto((SITE_ROOT / "index.html").as_uri(), wait_until="domcontentloaded")
    assert page.locator("html").evaluate("element => getComputedStyle(element).scrollBehavior") == "auto"
    page.close()


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            assert_public_pages(browser)
            assert_interactions_are_accessible(browser)
            assert_commercial_detail_is_accessible(browser)
            assert_missing_commercial_covers_have_clean_fallback(browser)
            assert_random_mode_uses_displayed_images(browser)
            assert_media_loading_is_deliberate(browser)
            assert_reduced_motion_is_respected(browser)
            assert_font_loading_is_declared_in_markup(browser)
        finally:
            browser.close()
    print("site smoke checks passed")


if __name__ == "__main__":
    main()
