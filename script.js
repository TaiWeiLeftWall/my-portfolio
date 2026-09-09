const CATEGORY_LABELS = {
    portrait: '人像',
    stilllife: '静物',
    performance: '演出',
    landscape: '风光',
};

const COLLECTIONS = {
    graduation: { title: '毕业照', category: 'portrait' },
    poster: { title: '海报拍摄', category: 'portrait' },
    objects: { title: '小物件', category: 'stilllife' },
    jewelry: { title: '首饰', category: 'stilllife' },
    digital: { title: '数码', category: 'stilllife' },
};

const overviewCoverIndexByProjectId = new Map();
const overviewOrderByProjectId = new Map();
let nextOverviewOrder = 0;
let activeProject = null;
let activeSlideIndex = 0;
let projectReturnFocus = null;
let projectReturnScrollY = 0;
let projectReturnHash = '#selected';
let projectClosePendingHash = '';
let resizeTimer = null;

function projectIdFor(group, index) {
    const raw = `${group.category || 'work'}-${group.date || 'undated'}-${index}`;
    return raw.toLowerCase().replace(/[^a-z0-9-]+/g, '-');
}

function shuffled(items) {
    const result = [...items];
    for (let index = result.length - 1; index > 0; index -= 1) {
        const swapIndex = Math.floor(Math.random() * (index + 1));
        [result[index], result[swapIndex]] = [result[swapIndex], result[index]];
    }
    return result;
}

function randomizeOverviewProjects(projects) {
    const newProjectIds = [];
    projects.forEach(project => {
        if (!overviewCoverIndexByProjectId.has(project.id)) {
            overviewCoverIndexByProjectId.set(
                project.id,
                Math.floor(Math.random() * project.images.length),
            );
        }
        if (!overviewOrderByProjectId.has(project.id)) newProjectIds.push(project.id);
    });

    shuffled(newProjectIds).forEach(projectId => {
        overviewOrderByProjectId.set(projectId, nextOverviewOrder);
        nextOverviewOrder += 1;
    });

    return projects
        .map(project => {
            const coverIndex = Math.min(
                overviewCoverIndexByProjectId.get(project.id),
                project.images.length - 1,
            );
            return { ...project, overviewImage: project.images[coverIndex] };
        })
        .sort((a, b) => (
            overviewOrderByProjectId.get(a.id) - overviewOrderByProjectId.get(b.id)
        ));
}

function getPortfolioProjects() {
    if (typeof photoGroups === 'undefined' || !Array.isArray(photoGroups)) return [];
    const projects = photoGroups
        .map((group, index) => ({
            id: projectIdFor(group, index),
            category: group.category || '',
            collection: group.collection || '',
            categoryLabel: CATEGORY_LABELS[group.category] || group.category || '',
            title: group.title || '',
            description: group.description || '',
            date: group.date || '',
            images: Array.isArray(group.images) ? group.images : [],
        }))
        .filter(project => {
            if (project.images.length > 0) return true;
            console.warn(`Skipping empty portfolio project: ${project.id}`);
            return false;
        });
    return randomizeOverviewProjects(projects);
}

function overviewColumnCount(category = 'all') {
    if (category === 'performance' || category === 'landscape') {
        return window.matchMedia('(max-width: 800px)').matches ? 2 : 3;
    }
    const grid = document.getElementById('selected-grid');
    const width = grid ? grid.clientWidth : 0;
    if (width >= 1000) return 4;
    if (width >= 700) return 3;
    return 2;
}

function projectLabel(project) {
    return [project.title, project.categoryLabel, project.date].filter(Boolean).join(' · ') || '摄影项目';
}

function imageAlt(project, image) {
    return [image.title, project.title, project.categoryLabel, project.date].filter(Boolean).join(' · ') || '摄影作品';
}

function createSelectedWork(project, projectIndex) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'selected-work';
    button.dataset.projectId = project.id;
    button.setAttribute('aria-label', `查看项目：${projectLabel(project)}`);

    const image = document.createElement('img');
    image.src = project.overviewImage.src;
    image.alt = imageAlt(project, project.overviewImage);
    image.loading = projectIndex === 0 ? 'eager' : 'lazy';
    image.decoding = 'async';
    image.draggable = false;
    if (projectIndex === 0) image.setAttribute('fetchpriority', 'high');
    enableImageLoadFade(image);
    image.addEventListener('error', () => {
        image.hidden = true;
        if (!button.querySelector('.image-fallback')) {
            const fallback = document.createElement('span');
            fallback.className = 'image-fallback';
            fallback.textContent = '图片暂不可用';
            button.appendChild(fallback);
        }
    });

    button.appendChild(image);
    button.addEventListener('click', () => openProject(project.id, 0, button));
    return button;
}

function createSelectedColumn(projects, sourceOffset) {
    const column = document.createElement('div');
    column.className = 'selected-column';
    projects.forEach((project, index) => {
        column.appendChild(createSelectedWork(project, sourceOffset + index));
    });
    return column;
}

function renderProjectOverview(projects, fixedColumns = false) {
    const grid = document.getElementById('selected-grid');
    if (!grid) return;
    if (!projects.length) {
        const empty = document.createElement('p');
        empty.className = 'portfolio-empty';
        empty.textContent = '暂无作品';
        grid.replaceChildren(empty);
        return;
    }

    const requestedColumns = fixedColumns
        ? (window.matchMedia('(max-width: 800px)').matches ? 2 : 3)
        : overviewColumnCount();
    const columnCount = fixedColumns ? requestedColumns : Math.min(requestedColumns, projects.length);
    const baseSize = Math.floor(projects.length / columnCount);
    const remainder = projects.length % columnCount;
    let sourceOffset = 0;
    const columns = Array.from({ length: columnCount }, (_, columnIndex) => {
        const columnSize = baseSize + (columnIndex < remainder ? 1 : 0);
        const column = createSelectedColumn(
            projects.slice(sourceOffset, sourceOffset + columnSize),
            sourceOffset,
        );
        sourceOffset += columnSize;
        return column;
    });
    grid.replaceChildren(...columns);
}

function renderOverview(category = 'all') {
    const heading = document.getElementById('selected-heading');
    if (heading) heading.textContent = category === 'all'
        ? '沉礁摄影作品集'
        : (CATEGORY_LABELS[category] || '摄影作品');
    const projects = getPortfolioProjects().filter(project => category === 'all' || project.category === category);
    renderProjectOverview(projects, category === 'performance' || category === 'landscape');
}

function renderCollection(collectionId) {
    const collection = COLLECTIONS[collectionId];
    if (!collection) return false;
    const heading = document.getElementById('selected-heading');
    if (heading) heading.textContent = collection.title;
    const projects = getPortfolioProjects()
        .filter(project => project.collection === collectionId);
    renderProjectOverview(projects, true);
    return true;
}

function slideCount(project) {
    return 1 + project.images.length;
}

function wrapSlide(index, total) {
    return (index % total + total) % total;
}

function createStatementSlide(project) {
    const statement = document.createElement('article');
    statement.className = 'project-statement';

    if (project.categoryLabel) {
        const category = document.createElement('p');
        category.className = 'project-category';
        category.textContent = project.categoryLabel;
        statement.appendChild(category);
    }

    const heading = document.createElement('h2');
    heading.textContent = project.title || [project.categoryLabel, project.date].filter(Boolean).join(' · ');
    statement.appendChild(heading);

    if (project.description) {
        const description = document.createElement('p');
        description.className = 'project-description';
        description.textContent = project.description;
        statement.appendChild(description);
    }

    const metadata = document.createElement('p');
    metadata.className = 'project-metadata';
    metadata.textContent = [project.date, `${project.images.length} 张图片`].filter(Boolean).join(' · ');
    statement.appendChild(metadata);
    return statement;
}

function createImageSlide(project, imageIndex) {
    const figure = document.createElement('figure');
    figure.className = 'project-figure';
    const record = project.images[imageIndex];
    const image = document.createElement('img');
    image.className = 'project-image';
    image.src = record.src;
    image.alt = imageAlt(project, record);
    image.loading = 'eager';
    image.decoding = 'async';
    enableImageLoadFade(image);
    image.addEventListener('error', () => {
        const fallback = document.createElement('p');
        fallback.className = 'image-fallback project-image-fallback';
        fallback.textContent = '图片暂不可用';
        figure.replaceChildren(fallback);
    });
    figure.appendChild(image);
    return figure;
}

function updateProjectHash() {
    if (!activeProject) return;
    history.replaceState(
        { ...(history.state || {}), portfolioProject: true },
        '',
        `#work=${encodeURIComponent(activeProject.id)}&slide=${activeSlideIndex}`,
    );
    updateActiveNavigation();
}

function showProjectSlide(index, updateHash = true) {
    if (!activeProject) return;
    const total = slideCount(activeProject);
    activeSlideIndex = wrapSlide(index, total);
    const host = document.querySelector('[data-project-slide]');
    host.replaceChildren(activeSlideIndex === 0
        ? createStatementSlide(activeProject)
        : createImageSlide(activeProject, activeSlideIndex - 1));
    document.querySelector('[data-slide-counter]').textContent = `${activeSlideIndex + 1} / ${total}`;
    if (updateHash) updateProjectHash();
}

function openProject(projectId, slideIndex = 0, trigger = document.activeElement, pushHistory = true) {
    const project = getPortfolioProjects().find(item => item.id === projectId);
    if (!project) return false;
    if (pushHistory && !location.hash.startsWith('#work=')) {
        projectReturnHash = location.hash || '#selected';
    }
    activeProject = project;
    projectReturnFocus = trigger && typeof trigger.focus === 'function' ? trigger : null;
    projectReturnScrollY = window.scrollY;
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    document.body.classList.add('project-open');
    document.getElementById('selected-view').hidden = true;
    const viewer = document.getElementById('project-viewer');
    viewer.hidden = false;
    showProjectSlide(Number.isFinite(Number(slideIndex)) ? Number(slideIndex) : 0, false);
    if (pushHistory) {
        history.pushState(
            { portfolioProject: true },
            '',
            `#work=${encodeURIComponent(activeProject.id)}&slide=${activeSlideIndex}`,
        );
    }
    updateActiveNavigation();
    viewer.focus({ preventScroll: true });
    return true;
}

function closeProject() {
    const viewer = document.getElementById('project-viewer');
    if (!viewer || viewer.hidden) return;
    viewer.hidden = true;
    document.getElementById('selected-view').hidden = false;
    document.body.classList.remove('project-open');
    const shouldReturnThroughHistory = history.state?.portfolioProject === true;
    if (shouldReturnThroughHistory) {
        projectClosePendingHash = projectReturnHash;
        history.back();
    } else {
        history.replaceState(null, '', projectReturnHash);
        updateActiveNavigation();
    }
    const returnTarget = projectReturnFocus;
    activeProject = null;
    projectReturnFocus = null;
    returnTarget?.focus({ preventScroll: true });
    window.scrollTo({ top: projectReturnScrollY, left: 0, behavior: 'instant' });
    projectReturnScrollY = 0;
}

function parsePortfolioHash() {
    const params = new URLSearchParams(location.hash.replace(/^#/, ''));
    if (params.has('work')) {
        const opened = openProject(params.get('work'), Number(params.get('slide') || 0), null, false);
        if (opened) return;
    }

    if (activeProject) {
        activeProject = null;
        document.getElementById('project-viewer').hidden = true;
        document.getElementById('selected-view').hidden = false;
        document.body.classList.remove('project-open');
        window.scrollTo({ top: projectReturnScrollY, left: 0, behavior: 'instant' });
        projectReturnScrollY = 0;
    }
    const currentOverviewHash = location.hash || '#selected';
    if (projectClosePendingHash && currentOverviewHash === projectClosePendingHash) {
        projectClosePendingHash = '';
        updateActiveNavigation();
        return;
    }
    projectClosePendingHash = '';
    const collection = params.get('collection');
    if (collection && renderCollection(collection)) return;
    const category = params.get('category');
    renderOverview(Object.prototype.hasOwnProperty.call(CATEGORY_LABELS, category) ? category : 'all');
}

function setupProjectViewer() {
    const viewer = document.getElementById('project-viewer');
    if (!viewer) return;
    viewer.querySelector('[data-project-close]').addEventListener('click', closeProject);
    viewer.querySelector('[data-project-prev]').addEventListener('click', () => showProjectSlide(activeSlideIndex - 1));
    viewer.querySelector('[data-project-next]').addEventListener('click', () => showProjectSlide(activeSlideIndex + 1));
    viewer.addEventListener('keydown', event => {
        if (!activeProject || event.target.matches('input, textarea, select')) return;
        if (event.key === 'ArrowLeft') showProjectSlide(activeSlideIndex - 1);
        else if (event.key === 'ArrowRight') showProjectSlide(activeSlideIndex + 1);
        else if (event.key === 'Escape') closeProject();
        else return;
        event.preventDefault();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('selected-grid')) return;
    setupProjectViewer();
    parsePortfolioHash();
    window.addEventListener('hashchange', parsePortfolioHash);
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (activeProject) return;
            parsePortfolioHash();
        }, 150);
    });
});
