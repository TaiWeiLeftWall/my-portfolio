// ==========================================
// 商业项目详情页逻辑
// ==========================================

const transparentPixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
let allImages = [];
let currentImageIndex = 0;
let currentGroupImages = [];
let lightboxReturnFocus = null;

let _domReady = false, _dataReady = false, _initialized = false;
function _init() {
    if (!_domReady || !_dataReady || _initialized) return;
    _initialized = true;
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

    // 设置副导航标题
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
            const mediaButton = document.createElement('button');
            mediaButton.type = 'button';
            mediaButton.className = 'media-item media-image';
            mediaButton.setAttribute('aria-label', `查看项目图片 ${index + 1}`);
            mediaButton.innerHTML = `<img src="${transparentPixel}" data-src="${item.src}" alt="${item.title || project.title || '项目图片'}" loading="lazy" decoding="async">`;
            mediaButton.addEventListener('click', () => {
                openLightbox(item.src, item.title || '', '', lightboxImages);
            });
            mediaGrid.appendChild(mediaButton);

            const img = mediaButton.querySelector('img');
            img.addEventListener('load', () => img.classList.add('loaded'));
            img.addEventListener('error', () => img.classList.add('loaded'));
            observeLazyImage(img);

            lightboxImages.push({
                src: item.src,
                title: item.title || '',
                description: ''
            });
        } else if (item.type === 'video') {
            const div = document.createElement('div');
            div.className = 'media-item media-video';
            div.innerHTML = `
                <button type="button" class="video-placeholder" data-src="${item.src}" data-poster="${item.poster || ''}" aria-label="播放视频：${item.title || project.title || '项目视频'}">
                    <span class="play-icon" aria-hidden="true">▶</span>
                </button>
            `;

            const placeholder = div.querySelector('.video-placeholder');
            placeholder.addEventListener('click', () => {
                loadVideoIframe(placeholder, item);
            });

            mediaGrid.appendChild(div);
        }
    });

    allImages = lightboxImages;

    // 设置灯箱
    setupLightbox();
}

function setupLightbox() {
    const lightbox = document.getElementById('lightbox');
    const closeBtn = document.querySelector('.lightbox-close');

    if (!lightbox || !closeBtn || lightbox.dataset.ready === 'true') return;
    lightbox.dataset.ready = 'true';
    closeBtn.addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', (event) => {
        if (event.target === lightbox) closeLightbox();
    });
    document.addEventListener('keydown', (event) => {
        if (!lightbox.classList.contains('active')) return;
        if (event.key === 'Escape') {
            closeLightbox();
            return;
        }
        if (event.key === 'ArrowLeft') navigateLightbox(-1);
        if (event.key === 'ArrowRight') navigateLightbox(1);
        if (event.key === 'Tab') {
            const focusable = Array.from(lightbox.querySelectorAll('button:not([disabled])'))
                .filter((element) => element.offsetParent !== null);
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });

    let touchStartX = 0;
    lightbox.addEventListener('touchstart', (event) => {
        touchStartX = event.changedTouches[0].screenX;
    }, { passive: true });
    lightbox.addEventListener('touchend', (event) => {
        const difference = touchStartX - event.changedTouches[0].screenX;
        if (Math.abs(difference) > 50) navigateLightbox(difference > 0 ? 1 : -1);
    }, { passive: true });

    const previous = document.createElement('button');
    previous.type = 'button';
    previous.className = 'lightbox-nav lightbox-prev';
    previous.setAttribute('aria-label', '上一张图片');
    previous.innerHTML = '&#10094;';
    previous.addEventListener('click', (event) => {
        event.stopPropagation();
        navigateLightbox(-1);
    });

    const next = document.createElement('button');
    next.type = 'button';
    next.className = 'lightbox-nav lightbox-next';
    next.setAttribute('aria-label', '下一张图片');
    next.innerHTML = '&#10095;';
    next.addEventListener('click', (event) => {
        event.stopPropagation();
        navigateLightbox(1);
    });

    lightbox.appendChild(previous);
    lightbox.appendChild(next);
}

function openLightbox(src, title, description, groupImages = []) {
    const lightbox = document.getElementById('lightbox');
    const image = document.getElementById('lightbox-img');
    const caption = document.getElementById('lightbox-caption');
    const previews = document.getElementById('lightbox-preview-strip');
    if (!lightbox || !image || !caption || !previews) return;

    if (!lightbox.classList.contains('active')) {
        lightboxReturnFocus = document.activeElement;
    }
    currentImageIndex = allImages.findIndex((item) => item.src === src);
    image.src = src;
    image.alt = title || description || '项目图片大图';
    caption.textContent = title || description || '';
    currentGroupImages = groupImages;
    previews.innerHTML = '';
    if (currentGroupImages.length > 1) {
        previews.style.display = 'flex';
        currentGroupImages.forEach((item, previewIndex) => {
            const preview = document.createElement('button');
            preview.type = 'button';
            preview.className = 'lightbox-preview-item' + (item.src === src ? ' active' : '');
            preview.setAttribute('aria-label', `查看缩略图 ${previewIndex + 1}`);
            if (item.src === src) preview.setAttribute('aria-current', 'true');
            preview.innerHTML = `<img src="${item.src}" alt="" loading="lazy" decoding="async">`;
            preview.addEventListener('click', (event) => {
                event.stopPropagation();
                openLightbox(item.src, item.title || '', item.description || '', currentGroupImages);
            });
            previews.appendChild(preview);
        });
    } else {
        previews.style.display = 'none';
    }

    lightbox.classList.add('active');
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.querySelector('.lightbox-close').focus();
}

function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    if (!lightbox || !lightbox.classList.contains('active')) return;
    lightbox.classList.remove('active');
    lightbox.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    currentGroupImages = [];
    if (lightboxReturnFocus && typeof lightboxReturnFocus.focus === 'function') {
        lightboxReturnFocus.focus();
    }
    lightboxReturnFocus = null;
}

function navigateLightbox(direction) {
    if (!allImages.length) return;
    currentImageIndex = (currentImageIndex + direction + allImages.length) % allImages.length;
    const image = allImages[currentImageIndex];
    openLightbox(
        image.src,
        image.title || '',
        image.description || '',
        currentGroupImages
    );
}
document.addEventListener('DOMContentLoaded', function() {
    _domReady = true;
    _dataReady = typeof commercialProjects !== 'undefined' || _dataReady;
    _init();
});
document.addEventListener('data-ready', function() { _dataReady = true; _init(); });




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
