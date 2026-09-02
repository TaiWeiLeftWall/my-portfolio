// Commercial project overview. Project order follows the CMS export.

const transparentPixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';

document.addEventListener('DOMContentLoaded', renderCommercialProjects);
document.addEventListener('data-ready', renderCommercialProjects);

function renderCommercialProjects() {
    const grid = document.getElementById('project-grid');
    if (!grid || typeof commercialProjects === 'undefined') return;

    grid.replaceChildren(...commercialProjects.map(createProjectCard));
}

function createProjectCard(project) {
    const items = Array.isArray(project.items) ? project.items : [];
    const imageCount = items.filter(item => item.type === 'image').length;
    const videoCount = items.filter(item => item.type === 'video').length;
    const card = document.createElement('a');
    card.className = 'project-card';
    card.href = `commercial-detail.html?project=${project.id}`;

    card.innerHTML = `
        <div class="project-card-cover">
            <img src="${transparentPixel}" data-src="${project.cover}" alt="${project.client}" loading="lazy" decoding="async">
            <span class="missing-cover-text" hidden>暂无封面</span>
        </div>
        <div class="project-card-info">
            <h2 class="project-client">${project.client}</h2>
            <p class="project-title">${project.title}</p>
            <p class="project-meta">
                <span>${project.year}</span>
                <span>${project.category}</span>
                <span>${imageCount} 图${videoCount ? ` · ${videoCount} 视频` : ''}</span>
            </p>
        </div>
    `;

    const image = card.querySelector('img');
    const cover = card.querySelector('.project-card-cover');
    const missingText = card.querySelector('.missing-cover-text');

    image.addEventListener('load', () => image.classList.add('loaded'));
    image.addEventListener('error', () => {
        cover.classList.add('is-missing');
        cover.setAttribute('aria-label', `${project.client} 暂无封面`);
        missingText.hidden = false;
    });
    observeLazyImage(image);

    return card;
}
