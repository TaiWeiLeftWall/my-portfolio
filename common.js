// ==========================================
// 公共组件 - 导航栏和页脚 (Apple Style)
// ==========================================
(function() {
    const logoPath = 'icons/LOGO_black.png';

    // 检测当前页面
    const page = location.pathname.split('/').pop() || 'index.html';

    // 强制刷新 data.js，避免浏览器缓存旧数据
    const dataScript = document.querySelector('script[src^="data.js"]');
    if (dataScript) {
        const fresh = document.createElement('script');
        fresh.src = 'data.js?t=' + Date.now();
        dataScript.parentNode.replaceChild(fresh, dataScript);
    }

    // 渲染导航栏 - Apple双层导航
    function renderNavbar() {
        const nav = document.querySelector('nav.navbar');
        if (!nav) return;

        const activeIndex = page === 'index.html' ? 'active' : '';
        const activeCommercial = page === 'commercial.html' ? 'active' : '';
        const activeVideos = page === 'videos.html' ? 'active' : '';
        const activeAbout = page === 'about.html' ? 'active' : '';

        nav.innerHTML = `
        <div class="nav-container">
            <a href="index.html" class="logo">
                <img src="${logoPath}" alt="沉礁" class="logo-img">
            </a>
            <ul class="nav-links">
                <li><a href="index.html" class="${activeIndex}">图片</a></li>
                <li><a href="commercial.html" class="${activeCommercial}">商业</a></li>
                <li><a href="videos.html" class="${activeVideos}">视频</a></li>
                <li><a href="about.html" class="${activeAbout}">关于</a></li>
            </ul>
        </div>`;
    }

    // 渲染副导航栏
    function renderSubNav() {
        // 检查是否已存在副导航
        if (document.querySelector('.sub-nav')) return;

        const nav = document.querySelector('nav.navbar');
        if (!nav) return;

        // 根据页面设置标题
        const subNavTitles = {
            'index.html': '摄影作品集',
            'commercial.html': '商业项目',
            'commercial-detail.html': '商业项目',
            'videos.html': '影像作品',
            'about.html': '关于'
        };

        const subNavTitle = subNavTitles[page] || '沉礁摄影作品集';

        const subNav = document.createElement('div');
        subNav.className = 'sub-nav';
        subNav.innerHTML = `
        <div class="sub-nav-container">
            <span class="sub-nav-title">${subNavTitle}</span>
        </div>`;

        nav.parentNode.insertBefore(subNav, nav.nextSibling);
    }

    // 渲染页脚 - Apple Parchment风格
    function renderFooter() {
        const footer = document.querySelector('footer');
        if (!footer) return;

        footer.innerHTML = `
        <div class="container">
            <img src="${logoPath}" alt="沉礁" class="footer-logo">
            <p>&copy; 2026 沉礁. All rights reserved.</p>
            <div class="social-links">
                <a href="https://www.douyin.com/user/MS4wLjABAAAA7JQxOJE2ZpmOut3zgFxONESR0I6k9DhHVqTRPIfoVkJjBkw6tTMeSqQBqC6pa87S" target="_blank">抖音</a>
                <a href="https://space.bilibili.com/7611277" target="_blank">哔哩哔哩</a>
                <a href="https://www.xiaohongshu.com/user/profile/5ed20dde0000000001007763" target="_blank">小红书</a>
            </div>
        </div>`;
    }

    renderNavbar();
    renderSubNav();
    renderFooter();
})();