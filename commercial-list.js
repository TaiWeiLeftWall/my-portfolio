// ==========================================
// 鍟嗕笟椤圭洰鍒楄〃椤甸€昏緫
// ==========================================

let currentCategory = 'all';
let currentYear = 'all';
let allImages = [];
const transparentPixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';

let _domReady = false, _dataReady = false;
function _init() {
    if (!_domReady || !_dataReady) return;
    setupFilters();
    loadProjects();
    initLightbox();
}
document.addEventListener('DOMContentLoaded', function() { _domReady = true; _init(); });
document.addEventListener('data-ready', function() { _dataReady = true; _init(); });
setTimeout(function() { if (!_dataReady) { _dataReady = true; _init(); } }, 2000););

function initLightbox() {
    const lightbox = document.getElementById('lightbox');
    const closeBtn = document.querySelector('.lightbox-close');

    if (!lightbox || !closeBtn) return;

    closeBtn.addEventListener('click', () => {
        lightbox.classList.remove('active');
        document.body.style.overflow = '';
    });

    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            lightbox.classList.remove('active');
            document.body.style.overflow = '';
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.classList.contains('active')) {
            lightbox.classList.remove('active');
            document.body.style.overflow = '';
        }
    });
}




// 璁剧疆绛涢€夊櫒
function setupFilters() {
    const categoryList = document.getElementById('category-filters');
    const yearSelect = document.getElementById('year-filter');

    // 娣诲姞鍒嗙被鎸夐挳
    const categories = getCommercialCategories();
    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'category-btn';
        btn.dataset.category = cat;
        btn.textContent = cat;
        btn.addEventListener('click', () => selectCategory(cat));
        categoryList.appendChild(btn);
    });

    // 濉厖骞翠唤涓嬫媺妗?
    const years = getCommercialYears();
    years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year + '骞?;
        yearSelect.appendChild(option);
    });

    // 骞翠唤绛涢€変簨浠?
    yearSelect.addEventListener('change', () => {
        currentYear = yearSelect.value;
        loadProjects();
    });
}

// 閫夋嫨鍒嗙被
function selectCategory(category) {
    document.querySelectorAll('#category-filters .category-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.category === category);
    });
    currentCategory = category;
    loadProjects();
}

// 鍔犺浇椤圭洰
function loadProjects() {
    const grid = document.getElementById('project-grid');
    grid.innerHTML = '';
    allImages = [];

    let filtered = commercialProjects;

    // 鎸夊垎绫荤瓫閫?
    if (currentCategory !== 'all') {
        filtered = filtered.filter(p => p.category === currentCategory);
    }

    // 鎸夊勾浠界瓫閫?
    if (currentYear !== 'all') {
        filtered = filtered.filter(p => p.year === parseInt(currentYear));
    }

    // 鎸夊勾浠藉€掑簭
    filtered.sort((a, b) => b.year - a.year);

    if (filtered.length === 0) {
        grid.innerHTML = '<p class="no-projects">鏆傛棤椤圭洰</p>';
        return;
    }

    // 鐢熸垚椤圭洰鍗＄墖
    filtered.forEach(project => {
        const card = createProjectCard(project);
        grid.appendChild(card);

        // 鏀堕泦鐏鍥剧墖
        project.items.filter(item => item.type === 'image').forEach(img => {
            allImages.push({
                src: img.src,
                title: img.title || '',
                description: ''
            });
        });
    });

    // 娣″叆鍔ㄧ敾
    setTimeout(() => {
        grid.style.opacity = '1';
    }, 50);
}

// 鍒涘缓椤圭洰鍗＄墖
function createProjectCard(project) {
    const card = document.createElement('a');
    card.className = 'project-card';
    card.href = `commercial-detail.html?project=${project.id}`;

    const hasVideo = project.items.some(item => item.type === 'video');
    const imageCount = project.items.filter(item => item.type === 'image').length;
    const videoCount = project.items.filter(item => item.type === 'video').length;

    card.innerHTML = `
        <div class="project-card-cover">
            <img src="${transparentPixel}" data-src="${project.cover}" alt="${project.client}" loading="lazy" decoding="async">
            ${hasVideo ? '<div class="media-badge video-badge">瑙嗛</div>' : ''}
        </div>
        <div class="project-card-info">
            <h3 class="project-client">${project.client}</h3>
            <p class="project-title">${project.title}</p>
            <div class="project-meta">
                <span class="project-year">${project.year}</span>
                <span class="project-category">${project.category}</span>
                <span class="project-counts">
                    ${imageCount > 0 ? `<span class="count-item">${imageCount}鍥?/span>` : ''}
                    ${videoCount > 0 ? `<span class="count-item">${videoCount}瑙嗛</span>` : ''}
                </span>
            </div>
        </div>
    `;

    const img = card.querySelector('.project-card-cover img');
    img.addEventListener('load', () => img.classList.add('loaded'));
    img.addEventListener('error', () => img.classList.add('loaded'));
    observeLazyImage(img);

    return card;
}
