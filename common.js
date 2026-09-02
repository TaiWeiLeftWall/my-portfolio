// === Lazy loading image helpers (shared) ===
let lazyImageObserver = null;

function getLazyImageObserver() {
    if (!('IntersectionObserver' in window)) return null;
    if (!lazyImageObserver) {
        lazyImageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                loadLazyImage(entry.target);
                lazyImageObserver.unobserve(entry.target);
            });
        }, { rootMargin: '600px 0px', threshold: 0.01 });
    }
    return lazyImageObserver;
}

function loadLazyImage(img) {
    if (!img || !img.dataset.src) return;
    img.src = img.dataset.src;
    delete img.dataset.src;
}

function observeLazyImage(img) {
    const observer = getLazyImageObserver();
    if (observer) {
        observer.observe(img);
    } else {
        loadLazyImage(img);
    }
}

// ==========================================
// Minimal portfolio shell
// ==========================================
const PORTFOLIO_LINKS = [
    ['index.html', 'Selected Works'],
    ['index.html#category=portrait', '人像'],
    ['index.html#category=performance', '演出'],
    ['index.html#category=landscape', '风光'],
    ['videos.html', '视频'],
    ['commercial.html', '商业项目'],
    ['about.html', 'About'],
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
    const page = location.pathname.split('/').pop() || 'index.html';
    const current = `${page}${location.hash}`;
    document.querySelectorAll('.portfolio-nav a[data-nav-link]').forEach(link => {
        const href = link.getAttribute('href');
        const commercialDetail = page === 'commercial-detail.html' && href === 'commercial.html';
        const selectedState = page === 'index.html'
            && (location.hash === '#selected' || location.hash.startsWith('#work='))
            && href === 'index.html';
        const active = href === current || (!location.hash && href === page) || commercialDetail || selectedState;
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
            <span class="portfolio-role">杭州自由摄影师</span>
            <button type="button" data-menu-toggle aria-expanded="false" aria-controls="portfolio-navigation">菜单</button>
        </div>
        <nav class="portfolio-nav" id="portfolio-navigation" data-expanded="false" aria-label="作品集导航">
            <div class="portfolio-nav-links">
                ${PORTFOLIO_LINKS.map(([href, label]) => `<a href="${href}" data-nav-link>${label}</a>`).join('')}
            </div>
            <div class="portfolio-contact"><a href="about.html">合作：sleepylagoon2894</a></div>
        </nav>`;

    placeholder.replaceWith(shell);
    document.querySelector('.sub-nav')?.remove();
    document.querySelector('footer')?.remove();

    shell.querySelector('[data-menu-toggle]').addEventListener('click', event => {
        setMenuExpanded(event.currentTarget.getAttribute('aria-expanded') !== 'true');
    });
    shell.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => setMenuExpanded(false));
    });
    window.addEventListener('hashchange', updateActiveNavigation);
    updateActiveNavigation();
}

renderPortfolioShell();
