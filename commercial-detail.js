// ==========================================
// 鍟嗕笟椤圭洰璇︽儏椤甸€昏緫
// ==========================================

const transparentPixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';

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
document.addEventListener('DOMContentLoaded', function() { _domReady = true; _init(); });
document.addEventListener('data-ready', function() { _dataReady = true; _init(); });
setTimeout(function() { if (!_dataReady) { _dataReady = true; _init(); } }, 2000););




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
