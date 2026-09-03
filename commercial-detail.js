// Statement-first commercial project viewer.

let activeCommercialProject = null;
let commercialSlideIndex = 0;
let commercialDetailInitialized = false;

document.addEventListener('DOMContentLoaded', initializeCommercialDetail);
document.addEventListener('data-ready', initializeCommercialDetail);

function initializeCommercialDetail() {
    if (commercialDetailInitialized || typeof getProjectById !== 'function') return;

    const projectId = new URLSearchParams(location.search).get('project');
    if (!projectId) {
        location.href = 'commercial.html';
        return;
    }

    const project = getProjectById(projectId);
    if (!project) {
        const detail = document.getElementById('project-detail');
        if (detail) detail.innerHTML = '<p class="error-message">项目不存在</p>';
        commercialDetailInitialized = true;
        return;
    }

    commercialDetailInitialized = true;
    document.body.classList.add('project-open');
    bindCommercialControls();
    renderCommercialSequence(project);
}

function commercialSlideCount(project) {
    return 1 + project.items.length;
}

function renderCommercialSequence(project) {
    activeCommercialProject = project;
    setCommercialSlide(0);
    document.getElementById('commercial-viewer').focus({ preventScroll: true });
}

function setCommercialSlide(index) {
    if (!activeCommercialProject) return;

    const total = commercialSlideCount(activeCommercialProject);
    commercialSlideIndex = (index % total + total) % total;
    const slide = document.querySelector('[data-commercial-slide]');
    const content = commercialSlideIndex === 0
        ? createCommercialStatement(activeCommercialProject)
        : createCommercialMedia(
            activeCommercialProject.items[commercialSlideIndex - 1],
            activeCommercialProject
        );

    slide.replaceChildren(content);
    slide.classList.remove('is-entering');
    requestAnimationFrame(() => slide.classList.add('is-entering'));
    document.querySelector('[data-commercial-counter]').textContent =
        `${commercialSlideIndex + 1} / ${total}`;
}

function createCommercialStatement(project) {
    const statement = document.createElement('article');
    statement.className = 'commercial-statement';

    const client = document.createElement('p');
    client.className = 'commercial-client';
    client.textContent = project.client;

    const title = document.createElement('h1');
    title.textContent = project.title;

    const description = document.createElement('p');
    description.className = 'commercial-description';
    description.textContent = project.description;

    const meta = document.createElement('p');
    meta.className = 'commercial-meta';
    meta.textContent = `${project.year} · ${project.category}`;

    const contact = document.createElement('a');
    contact.className = 'commercial-contact';
    contact.href = 'about.html';
    contact.textContent = '获取报价';

    statement.append(client, title, description, meta, contact);
    return statement;
}

function createCommercialMedia(item, project) {
    if (item.type === 'video') {
        const wrapper = document.createElement('div');
        wrapper.className = 'commercial-video';
        const placeholder = document.createElement('button');
        placeholder.type = 'button';
        placeholder.className = 'commercial-video-placeholder';
        placeholder.setAttribute('aria-label', `播放视频：${item.title || project.title}`);
        placeholder.innerHTML = '<span aria-hidden="true">▶</span>';
        placeholder.addEventListener('click', () => loadCommercialVideo(placeholder, item, project));
        wrapper.appendChild(placeholder);
        return wrapper;
    }

    const image = document.createElement('img');
    image.className = 'commercial-media';
    image.src = item.src;
    image.alt = item.title || project.title || '项目图片';
    image.loading = 'eager';
    image.decoding = 'async';
    return image;
}

function loadCommercialVideo(placeholder, item, project) {
    const iframe = document.createElement('iframe');
    iframe.className = 'commercial-media commercial-media-video';
    iframe.src = item.src + (item.src.includes('?') ? '&autoplay=1' : '?autoplay=1');
    iframe.title = item.title || project.title || '项目视频';
    iframe.setAttribute(
        'allow',
        'accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; autoplay'
    );
    iframe.allowFullscreen = true;
    placeholder.parentElement.replaceChildren(iframe);
}

function bindCommercialControls() {
    const viewer = document.getElementById('commercial-viewer');
    const previous = viewer.querySelector('[data-commercial-prev]');
    const next = viewer.querySelector('[data-commercial-next]');

    previous.addEventListener('click', () => setCommercialSlide(commercialSlideIndex - 1));
    next.addEventListener('click', () => setCommercialSlide(commercialSlideIndex + 1));
    viewer.addEventListener('keydown', event => {
        const target = event.target;
        if (target !== viewer || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            setCommercialSlide(commercialSlideIndex - 1);
        }
        if (event.key === 'ArrowRight') {
            event.preventDefault();
            setCommercialSlide(commercialSlideIndex + 1);
        }
    });
}
