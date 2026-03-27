// ==========================================
// 公共组件 - 导航栏和页脚
// ==========================================
(function() {
    const logoPath = 'images/icons/LOGO_white.png';

    // 检测当前页面
    const page = location.pathname.split('/').pop() || 'index.html';

    // 渲染导航栏
    function renderNavbar() {
        const nav = document.querySelector('nav.navbar');
        if (!nav) return;

        const activeIndex = page === 'index.html' ? 'active' : '';
        const activeVideos = page === 'videos.html' ? 'active' : '';
        const activeAbout = page === 'about.html' ? 'active' : '';

        nav.innerHTML = `
        <div class="nav-container">
            <a href="index.html" class="logo">
                <img src="${logoPath}" alt="沉礁" class="logo-img">
                <span class="logo-text">沉礁</span>
            </a>
            <ul class="nav-links">
                <li><a href="index.html" class="${activeIndex}">作品</a></li>
                <li><a href="videos.html" class="${activeVideos}">视频</a></li>
                <li><a href="about.html" class="${activeAbout}">关于</a></li>
            </ul>
        </div>`;
    }

    // 渲染页脚
    function renderFooter() {
        const footer = document.querySelector('footer');
        if (!footer) return;

        footer.innerHTML = `
        <div class="container">
            <img src="${logoPath}" alt="沉礁" class="footer-logo">
            <p>&copy; 2026 沉礁. All rights reserved.</p>
            <div class="social-links">
                <a href="#" id="instagram-link">Instagram</a>
                <a href="#" id="weibo-link">微博</a>
                <a href="https://www.xiaohongshu.com/user/profile/5ed20dde0000000001007763" target="_blank" id="xiaohongshu-link">小红书</a>
            </div>
        </div>`;
    }

    renderNavbar();
    renderFooter();
})();
