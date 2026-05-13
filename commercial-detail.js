// ==========================================
// 商业项目详情页逻辑
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    const params = new URLSearchParams(location.search);
    const projectId = params.get('project');

    if (!projectId) {
        location.href = 'commercial.html';
        return;
    }

    const project = getProjectById(projectId);

    if (!project) {
        document.getElementById('project-detail').innerHTML = '<p class="error-message">项目不存在</p>';
        return;
    }

    // 设置副导航标题（因为详情页需要显示返回链接）
    const subNavTitle = document.querySelector('.sub-nav-title');
    if (subNavTitle) {
        subNavTitle.textContent = '商业项目';
    }

    // 渲染项目信息
    document.getElementById('detail-client').textContent = project.client;
    document.getElementById('detail-title').textContent = project.title;
    document.getElementById('detail-description').textContent = project.description;

    // 渲染媒体
    const mediaGrid = document.getElementById('detail-media');
    const lightboxImages = [];

    project.items.forEach((item, index) => {
        if (item.type === 'image') {
            const div = document.createElement('div');
            div.className = 'media-item media-image';
            div.innerHTML = `<img src="${item.src}" alt="${item.title || ''}" loading="lazy">`;
            div.addEventListener('click', () => {
                openLightbox(item.src, item.title || '', '', lightboxImages);
            });
            mediaGrid.appendChild(div);

            lightboxImages.push({
                src: item.src,
                title: item.title || '',
                description: ''
            });
        } else if (item.type === 'video') {
            const div = document.createElement('div');
            div.className = 'media-item media-video';
            div.innerHTML = `
                <div class="video-placeholder" data-src="${item.src}" data-poster="${item.poster || ''}">
                    <span class="play-icon">▶</span>
                </div>
            `;

            const placeholder = div.querySelector('.video-placeholder');
            placeholder.addEventListener('click', () => {
                loadVideoIframe(placeholder, item);
            });

            mediaGrid.appendChild(div);
        }
    });

    // 设置灯箱
    setupLightbox();
});

// 加载视频 iframe
function loadVideoIframe(placeholder, video) {
    if (placeholder.dataset.loaded) return;
    placeholder.dataset.loaded = 'true';

    const wrapper = placeholder.parentElement;
    const iframe = document.createElement('iframe');
    iframe.src = video.src + (video.src.includes('?') ? '&autoplay=1' : '?autoplay=1');
    iframe.title = video.title || '视频';
    iframe.setAttribute('allow', 'accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; autoplay');
    iframe.allowFullscreen = true;
    wrapper.replaceChild(iframe, placeholder);
}