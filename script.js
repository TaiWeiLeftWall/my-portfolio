const CATEGORY_LABELS = {
    portrait: '人像',
    stilllife: '静物',
    performance: '演出摄影',
    landscape: '风光',
    news: '新闻摄影',
};

const COLLECTIONS = {
    graduation: { title: '毕业照', category: 'portrait' },
    poster: { title: '海报拍摄', category: 'portrait' },
    objects: { title: '小物件', category: 'stilllife' },
    jewelry: { title: '首饰', category: 'stilllife' },
    digital: { title: '数码', category: 'stilllife' },
};

const PERFORMANCE_GENRES = {
    rock: { label: '摇滚现场', series: {
        gr: 'GR摇滚节', newyear: '跨年演出', livehouse: 'Livehouse现场',
    } },
    campus: { label: '校园演出现场', series: {
        corridor: '藤廊音乐会', lawn: '草坪音乐会', welcome: '迎新晚会', 'campus-other': '其他校内演出',
    } },
};

function performanceGenre(project) {
    const series = project.collection.replace(/^performance-/, '');
    return Object.keys(PERFORMANCE_GENRES).find(key =>
        Object.hasOwn(PERFORMANCE_GENRES[key].series, series)) || '';
}

function performancePath(project) {
    const genre = PERFORMANCE_GENRES[performanceGenre(project)];
    return genre ? `${genre.label} / ${genre.series[project.collection.replace(/^performance-/, '')]}` : '';
}

function performanceFilterLink(label, genre, series, active) {
    const link = document.createElement('a');
    link.href = `#category=performance${genre === 'all' ? '' : `&genre=${genre}`}${series ? `&series=${series}` : ''}`;
    link.textContent = label;
    if (active) link.setAttribute('aria-current', 'true');
    return link;
}

function performanceTitle(project) {
    const [scene, event] = project.title.split('｜');
    return event ? { scene, event } : { scene: '摇滚现场', event: project.title };
}

function isPerformanceArchive(project) {
    return project.images[0]?.src.startsWith('images/performance-archive/')
        || Boolean(performanceThumbnail(project.images[0]?.src));
}

function performanceThumbnail(src) {
    return typeof PERFORMANCE_ARCHIVE_MEDIA !== 'undefined'
        && Object.hasOwn(PERFORMANCE_ARCHIVE_MEDIA, src)
        ? PERFORMANCE_ARCHIVE_MEDIA[src] : '';
}

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
                Math.floor(Math.random() * (project.category === 'performance'
                    ? Math.min(3, project.images.length) : project.images.length)),
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
            sourceIndex: index,
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
    if (['performance', 'landscape', 'news'].includes(category)) {
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
    const overviewSrc = project.overviewImage.src;
    image.src = /^images\/news\/\d{2}-\d{3}\.jpg$/.test(overviewSrc)
        ? overviewSrc.replace('images/news/', 'images/news/thumbs/')
        : performanceThumbnail(overviewSrc) || overviewSrc;
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
    if (project.category === 'performance') {
        const { scene, event } = performanceTitle(project);
        const caption = document.createElement('span');
        caption.className = 'performance-caption';
        const title = document.createElement('span');
        title.className = 'performance-card-title';
        title.textContent = scene;
        const meta = document.createElement('span');
        meta.className = 'performance-card-meta';
        meta.textContent = `${event} · ${project.date.slice(0, 4)}`;
        const categoryPath = document.createElement('span');
        categoryPath.className = 'performance-card-meta';
        categoryPath.textContent = performancePath(project);
        caption.append(title, meta, categoryPath);
        button.appendChild(caption);
    }
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

function setPerformanceOverview(enabled) {
    document.getElementById('selected-view').classList.toggle('performance-overview', enabled);
    document.getElementById('selected-heading').classList.toggle('visually-hidden', !enabled);
    document.querySelector('[data-performance-overview]').hidden = !enabled;
    document.querySelector('[data-performance-filters]').hidden = !enabled;
    document.querySelector('[data-performance-subfilters]').hidden = true;
}

function renderOverview(category = 'all', genre = 'all', series = '') {
    setPerformanceOverview(category === 'performance');
    const heading = document.getElementById('selected-heading');
    if (heading) heading.textContent = category === 'all'
        ? '林伟杰 WEIJIE LIN 摄影作品集'
        : (CATEGORY_LABELS[category] || '摄影作品');
    let projects = getPortfolioProjects().filter(project => category === 'all'
        ? project.category !== 'news' && !isPerformanceArchive(project)
        : project.category === category);
    if (category === 'performance') {
        // The full archive uses the same session-stable shuffle as the other categories.
        const filters = document.querySelector('[data-performance-filters]');
        // Keep the previous theatre URL useful; the old broad music URL falls back to all.
        if (genre === 'theatre') { genre = 'campus'; series = 'campus-other'; }
        const activeGenre = Object.hasOwn(PERFORMANCE_GENRES, genre) ? genre : 'all';
        const group = PERFORMANCE_GENRES[activeGenre];
        const activeSeries = group && Object.hasOwn(group.series, series) ? series : '';
        filters.replaceChildren(...['all', ...Object.keys(PERFORMANCE_GENRES)].map(key =>
            performanceFilterLink(key === 'all' ? '全部' : PERFORMANCE_GENRES[key].label, key, '', key === activeGenre)));
        const subfilters = document.querySelector('[data-performance-subfilters]');
        subfilters.hidden = !group;
        subfilters.replaceChildren(...(group ? [
            performanceFilterLink('该类全部', activeGenre, '', !activeSeries),
            ...Object.entries(group.series).map(([key, label]) =>
                performanceFilterLink(label, activeGenre, key, key === activeSeries)),
        ] : []));
        if (group) projects = projects.filter(p => performanceGenre(p) === activeGenre);
        if (activeSeries) projects = projects.filter(p => p.collection === `performance-${activeSeries}`);
        const selectionLabel = group ? [group.label, group.series[activeSeries]].filter(Boolean).join(' / ') : '全部演出';
        document.querySelector('[data-performance-status]').textContent = `${selectionLabel} · ${projects.length} 组`;
        if (!projects.length) {
            const empty = document.createElement('p');
            empty.className = 'portfolio-empty';
            empty.textContent = '此分类暂无作品，可切换其他分类浏览。';
            document.getElementById('selected-grid').replaceChildren(empty);
            return;
        }
    }
    renderProjectOverview(projects, ['performance', 'landscape', 'news'].includes(category));
}

function renderCollection(collectionId) {
    const collection = COLLECTIONS[collectionId];
    if (!collection) return false;
    setPerformanceOverview(false);
    const heading = document.getElementById('selected-heading');
    if (heading) heading.textContent = collection.title;
    const projects = getPortfolioProjects()
        .filter(project => project.collection === collectionId);
    renderProjectOverview(projects, true);
    return true;
}

function slideCount(project) {
    return project.images.length + (project.category === 'performance' ? 0 : 1);
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
        // Changing slides must not invent an overview history entry for a direct link.
        history.state,
        '',
        `#work=${encodeURIComponent(activeProject.id)}&slide=${activeSlideIndex}`,
    );
    updateActiveNavigation();
}

function showProjectSlide(index, updateHash = true) {
    if (!activeProject) return;
    const total = slideCount(activeProject);
    const photoFirst = activeProject.category === 'performance';
    // Retain existing slide=1 URLs for the first photograph, including old 25GR links.
    activeSlideIndex = photoFirst ? wrapSlide(index - 1, total) + 1 : wrapSlide(index, total);
    const host = document.querySelector('[data-project-slide]');
    host.replaceChildren(activeSlideIndex === 0
        ? createStatementSlide(activeProject)
        : createImageSlide(activeProject, activeSlideIndex - 1));
    document.querySelector('[data-slide-counter]').textContent = `${activeSlideIndex + (photoFirst ? 0 : 1)} / ${total}`;
    if (updateHash) updateProjectHash();
}

function openProject(projectId, slideIndex = 0, trigger = document.activeElement, pushHistory = true) {
    const project = getPortfolioProjects().find(item => item.id === projectId);
    if (!project) return false;
    if (!pushHistory && !activeProject && project.category === 'performance') {
        if (!projectReturnHash.startsWith('#category=performance')) {
            projectReturnHash = '#category=performance';
        }
        const returnParams = new URLSearchParams(projectReturnHash.slice(1));
        renderOverview('performance', returnParams.get('genre'), returnParams.get('series'));
    }
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
    const photoFirst = project.category === 'performance';
    viewer.classList.toggle('performance-viewer', photoFirst);
    document.querySelector('[data-performance-heading]').hidden = !photoFirst;
    document.querySelector('[data-performance-info]').open = false;
    viewer.querySelector('[data-project-prev]').textContent = photoFirst ? '←' : '';
    viewer.querySelector('[data-project-next]').textContent = photoFirst ? '→' : '';
    if (photoFirst) {
        const { scene, event } = performanceTitle(project);
        document.querySelector('[data-performance-title]').textContent = scene;
        document.querySelector('[data-performance-description]').textContent =
            [performancePath(project), event, project.description, project.date, `${project.images.length} 张图片`].filter(Boolean).join(' · ');
    }
    const requestedSlide = Number.isFinite(Number(slideIndex)) ? Number(slideIndex) : 0;
    showProjectSlide(photoFirst && requestedSlide === 0 ? 1 : requestedSlide, false);
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
    renderOverview(Object.prototype.hasOwnProperty.call(CATEGORY_LABELS, category) ? category : 'all', params.get('genre'), params.get('series'));
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
