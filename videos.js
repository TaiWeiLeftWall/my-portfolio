document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('video-grid')) renderVideos();
});

function renderVideos() {
    const videoGrid = document.getElementById('video-grid');
    if (!videoGrid || typeof videos === 'undefined') return;
    videoGrid.innerHTML = '';

    const platformLabels = {
        bilibili: 'Bilibili',
        xiaohongshu: '小红书',
        douyin: '抖音',
    };
    const groups = {};
    videos.forEach(video => {
        const platform = video.platform || '';
        const source = video.source || '';
        if (!groups[platform]) groups[platform] = {};
        if (!groups[platform][source]) groups[platform][source] = [];
        groups[platform][source].push(video);
    });

    Object.keys(groups).forEach(platform => {
        const section = document.createElement('section');
        section.className = 'video-section';
        if (platform) {
            const header = document.createElement('h2');
            header.className = 'video-platform-header';
            header.textContent = platformLabels[platform] || platform;
            section.appendChild(header);
        }

        Object.keys(groups[platform]).forEach(source => {
            if (source) {
                const label = document.createElement('p');
                label.className = 'video-source-label';
                label.textContent = source;
                section.appendChild(label);
            }
            const grid = document.createElement('div');
            grid.className = 'video-grid';
            groups[platform][source].forEach(video => grid.appendChild(createVideoWork(video)));
            section.appendChild(grid);
        });
        videoGrid.appendChild(section);
    });
}

function createVideoWork(video) {
    const item = document.createElement('article');
    item.className = 'video-item video-work';
    const wrapper = document.createElement('div');
    wrapper.className = 'video-wrapper';
    item.appendChild(wrapper);

    if (video.url.includes('bilibili')) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'video-placeholder';
        button.dataset.src = video.url;
        button.setAttribute('aria-label', `播放视频：${video.title || '视频'}`);
        button.innerHTML = '<span aria-hidden="true">▶</span>';
        button.addEventListener('click', () => loadVideoIframe(button, video));
        wrapper.appendChild(button);
    } else {
        const link = document.createElement('a');
        link.href = video.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'video-external-link';
        link.setAttribute('aria-label', `在新窗口打开视频：${video.title || '视频'}`);
        link.innerHTML = '<span class="video-placeholder video-external" aria-hidden="true">↗</span>';
        wrapper.appendChild(link);
    }
    return item;
}

function loadVideoIframe(placeholder, video) {
    if (!video || placeholder.dataset.loaded) return;
    placeholder.dataset.loaded = 'true';
    const iframe = document.createElement('iframe');
    iframe.src = `${video.url}${video.url.includes('?') ? '&' : '?'}autoplay=0`;
    iframe.title = video.title || '视频';
    iframe.setAttribute('allow', 'accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
    iframe.allowFullscreen = true;
    placeholder.parentElement.replaceChild(iframe, placeholder);
}
