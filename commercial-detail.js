// ==========================================
// 鍟嗕笟椤圭洰璇︽儏椤甸€昏緫
// ==========================================

const transparentPixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
let allImages = [];
let currentImageIndex = 0;
let currentGroupImages = [];

let _domReady = false, _dataReady = false;
function _init() {
    if (!_domReady || !_dataReady) return;
    const params = new URLSearchParams(location.search);
    const projectId = params.get('project');

    if (!projectId) {
        location.href = 'commercial.html';
        return;
    }

    const project = getProjectById(projectId);

    if (!project) {
        document.getElementById('project-detail').innerHTML = '<p class="error-message">椤圭洰涓嶅瓨鍦?/p>';
        return;
    }

    // 璁剧疆鍓鑸爣棰橈紙鍥犱负璇︽儏椤甸渶瑕佹樉绀鸿繑鍥為摼鎺ワ級
    const subNavTitle = document.querySelector('.sub-nav-title');
    if (subNavTitle) {
        subNavTitle.textContent = '鍟嗕笟椤圭洰';
    }

    // 娓叉煋椤圭洰淇℃伅
    document.getElementById('detail-client').textContent = project.client;
    document.getElementById('detail-title').textContent = project.title;
    document.getElementById('detail-description').textContent = project.description;

    // 娓叉煋濯掍綋
    const mediaGrid = document.getElementById('detail-media');
    const lightboxImages = [];

    project.items.forEach((item, index) => {
        if (item.type === 'image') {
            const div = document.createElement('div');
            div.className = 'media-item media-image';
            div.innerHTML = `<img src="${transparentPixel}" data-src="${item.src}" alt="${item.title || ''}" loading="lazy" decoding="async">`;
            div.addEventListener('click', () => {
                openLightbox(item.src, item.title || '', '', lightboxImages);
            });
            mediaGrid.appendChild(div);

            const img = div.querySelector('img');
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
                <div class="video-placeholder" data-src="${item.src}" data-poster="${item.poster || ''}">
                    <span class="play-icon">鈻?/span>
                </div>
            `;

            const placeholder = div.querySelector('.video-placeholder');
            placeholder.addEventListener('click', () => {
                loadVideoIframe(placeholder, item);
            });

            mediaGrid.appendChild(div);
        }
    });

    allImages = lightboxImages;

    // 璁剧疆鐏
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
        if (event.key === 'Escape') closeLightbox();
        if (event.key === 'ArrowLeft') navigateLightbox(-1);
        if (event.key === 'ArrowRight') navigateLightbox(1);
    });

    let touchStartX = 0;
    lightbox.addEventListener('touchstart', (event) => {
        touchStartX = event.changedTouches[0].screenX;
    }, { passive: true });
    lightbox.addEventListener('touchend', (event) => {
        const difference = touchStartX - event.changedTouches[0].screenX;
        if (Math.abs(difference) > 50) navigateLightbox(difference > 0 ? 1 : -1);
    }, { passive: true });

    const previous = document.createElement('div');
    previous.className = 'lightbox-nav lightbox-prev';
    previous.innerHTML = '&#10094;';
    previous.addEventListener('click', (event) => {
        event.stopPropagation();
        navigateLightbox(-1);
    });

    const next = document.createElement('div');
    next.className = 'lightbox-nav lightbox-next';
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

    currentImageIndex = allImages.findIndex((item) => item.src === src);
    image.src = src;
    caption.textContent = title || description || '';
    currentGroupImages = groupImages;
    previews.innerHTML = '';
    if (currentGroupImages.length > 1) {
        previews.style.display = 'flex';
        currentGroupImages.forEach((item) => {
            const preview = document.createElement('div');
            preview.className = 'lightbox-preview-item' + (item.src === src ? ' active' : '');
            preview.innerHTML = `<img src="${item.src}" alt="">`;
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
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    if (!lightbox) return;
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
    currentGroupImages = [];
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
document.addEventListener('DOMContentLoaded', function() { _domReady = true; _init(); });
document.addEventListener('data-ready', function() { _dataReady = true; _init(); });
setTimeout(function() { if (!_dataReady) { _dataReady = true; _init(); } }, 2000);




// 鍔犺浇瑙嗛 iframe
function loadVideoIframe(placeholder, video) {
    if (placeholder.dataset.loaded) return;
    placeholder.dataset.loaded = 'true';

    const wrapper = placeholder.parentElement;
    const iframe = document.createElement('iframe');
    iframe.src = video.src + (video.src.includes('?') ? '&autoplay=1' : '?autoplay=1');
    iframe.title = video.title || '瑙嗛';
    iframe.setAttribute('allow', 'accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; autoplay');
    iframe.allowFullscreen = true;
    wrapper.replaceChild(iframe, placeholder);
}
