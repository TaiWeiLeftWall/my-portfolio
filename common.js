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
    img.classList.remove('is-loaded');
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

function enableImageLoadFade(img) {
    if (!img || img.classList.contains('image-load-fade')) return;
    img.classList.add('image-load-fade');
    const reveal = () => img.classList.add('is-loaded');
    img.addEventListener('load', reveal);
    if (img.complete && img.naturalWidth > 0 && !img.dataset.src) {
        requestAnimationFrame(reveal);
    }
}

function enableStaticImageLoadFades() {
    document.querySelectorAll('img').forEach(enableImageLoadFade);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enableStaticImageLoadFades, { once: true });
} else {
    enableStaticImageLoadFades();
}

// ==========================================
// Minimal portfolio shell
// ==========================================
const PORTFOLIO_NAVIGATION = {
    primary: [
        { href: 'index.html', label: 'Selected Works' },
    ],
    sections: [
        {
            label: 'PROJECTS 项目',
            items: [
                {
                    href: 'index.html#category=portrait',
                    label: '人像',
                    id: 'portrait',
                    children: [
                        { href: 'index.html#collection=graduation', label: '毕业照' },
                        { href: 'index.html#collection=poster', label: '海报拍摄' },
                    ],
                },
                {
                    href: 'index.html#category=stilllife',
                    label: '静物',
                    id: 'stilllife',
                    children: [
                        { href: 'index.html#collection=objects', label: '小物件' },
                        { href: 'index.html#collection=jewelry', label: '首饰' },
                        { href: 'index.html#collection=digital', label: '数码' },
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
        {
            label: 'INFO',
            items: [
                { href: 'about.html', label: '关于我' },
            ],
        },
    ],
};

function renderPortfolioLink(item, className = '', attributes = '') {
    const classAttribute = className ? ` class="${className}"` : '';
    const extraAttributes = attributes ? ` ${attributes}` : '';
    return `<a href="${item.href}"${classAttribute} data-nav-link${extraAttributes}>${item.label}</a>`;
}

function renderPortfolioNavItem(item) {
    if (!Array.isArray(item.children) || !item.children.length) {
        return `<div class="portfolio-nav-item">${renderPortfolioLink(item)}</div>`;
    }

    const childrenId = `portfolio-nav-children-${item.id}`;
    const parentAttributes = `data-nav-parent aria-expanded="false" aria-controls="${childrenId}"`;
    const children = `<div class="portfolio-nav-children" id="${childrenId}" hidden>${item.children.map(child => renderPortfolioLink(child, 'portfolio-nav-child')).join('')}</div>`;
    return `<div class="portfolio-nav-item">${renderPortfolioLink(item, '', parentAttributes)}${children}</div>`;
}

function renderPortfolioNavSections(sections) {
    return sections.map(section => `
        <section class="portfolio-nav-section">
            <p class="portfolio-nav-heading">${section.label}</p>
            <div class="portfolio-nav-items">
                ${section.items.map(renderPortfolioNavItem).join('')}
            </div>
        </section>`).join('');
}

function setMenuExpanded(expanded) {
    const nav = document.querySelector('.portfolio-nav');
    const toggle = document.querySelector('[data-menu-toggle]');
    if (!nav || !toggle) return;
    nav.dataset.expanded = String(expanded);
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.textContent = expanded ? '关闭' : '菜单';
}

function setSubmenuExpanded(parentLink, expanded) {
    const childrenId = parentLink?.getAttribute('aria-controls');
    const children = childrenId ? document.getElementById(childrenId) : null;
    if (!parentLink || !children) return;
    parentLink.setAttribute('aria-expanded', String(expanded));
    children.hidden = !expanded;
}

function setOnlySubmenuExpanded(activeParent) {
    document.querySelectorAll('[data-nav-parent]').forEach(parentLink => {
        setSubmenuExpanded(parentLink, parentLink === activeParent);
    });
}

function updateActiveNavigation() {
    const page = location.pathname.split('/').pop() || 'index.html';
    const current = `${page}${location.hash}`;
    const ancestorItem = PORTFOLIO_NAVIGATION.sections
        .flatMap(section => section.items)
        .find(item => item.children?.some(child => child.href === current));
    const ancestorHref = ancestorItem?.href || '';
    document.querySelectorAll('.portfolio-nav a[data-nav-link]').forEach(link => {
        const href = link.getAttribute('href');
        const commercialDetail = page === 'commercial-detail.html' && href === 'commercial.html';
        const selectedState = page === 'index.html'
            && (location.hash === '#selected' || location.hash.startsWith('#work='))
            && href === 'index.html';
        const active = href === current || (!location.hash && href === page) || commercialDetail || selectedState;
        link.classList.toggle('active', active);
        link.classList.toggle('ancestor-active', href === ancestorHref);
        if (active) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });

    const owningParent = [...document.querySelectorAll('[data-nav-parent]')].find(parentLink => {
        const parentHref = parentLink.getAttribute('href');
        const childHrefs = [...parentLink.parentElement.querySelectorAll('.portfolio-nav-child')]
            .map(child => child.getAttribute('href'));
        return parentHref === current || childHrefs.includes(current);
    });
    setOnlySubmenuExpanded(owningParent || null);
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
                <div class="portfolio-nav-primary">
                    ${PORTFOLIO_NAVIGATION.primary.map(item => renderPortfolioLink(item)).join('')}
                </div>
                <div class="portfolio-nav-sections">
                    ${renderPortfolioNavSections(PORTFOLIO_NAVIGATION.sections)}
                </div>
            </div>
        </nav>`;

    placeholder.replaceWith(shell);
    document.querySelector('.sub-nav')?.remove();
    document.querySelector('footer')?.remove();

    shell.querySelector('[data-menu-toggle]').addEventListener('click', event => {
        setMenuExpanded(event.currentTarget.getAttribute('aria-expanded') !== 'true');
    });
    shell.querySelectorAll('a[data-nav-link]').forEach(link => {
        link.addEventListener('click', event => {
            if (!link.matches('[data-nav-parent]')) {
                setMenuExpanded(false);
                return;
            }

            const page = location.pathname.split('/').pop() || 'index.html';
            const current = `${page}${location.hash}`;
            const isCurrentParent = link.getAttribute('href') === current;
            if (isCurrentParent) {
                event.preventDefault();
                const expanded = link.getAttribute('aria-expanded') === 'true';
                setSubmenuExpanded(link, !expanded);
                return;
            }
            setOnlySubmenuExpanded(link);
        });
    });
    window.addEventListener('hashchange', updateActiveNavigation);
    updateActiveNavigation();
}

renderPortfolioShell();
