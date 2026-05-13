// ==========================================
// 商业项目列表页逻辑
// ==========================================

let currentCategory = 'all';
let currentYear = 'all';
let allImages = [];

document.addEventListener('DOMContentLoaded', function() {
    setupFilters();
    loadProjects();

    // 设置灯箱
    setupLightbox();
});

// 设置筛选器
function setupFilters() {
    const categoryList = document.getElementById('category-filters');
    const yearSelect = document.getElementById('year-filter');

    // 添加分类按钮
    const categories = getCommercialCategories();
    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'category-btn';
        btn.dataset.category = cat;
        btn.textContent = cat;
        btn.addEventListener('click', () => selectCategory(cat));
        categoryList.appendChild(btn);
    });

    // 填充年份下拉框
    const years = getCommercialYears();
    years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year + '年';
        yearSelect.appendChild(option);
    });

    // 年份筛选事件
    yearSelect.addEventListener('change', () => {
        currentYear = yearSelect.value;
        loadProjects();
    });
}

// 选择分类
function selectCategory(category) {
    document.querySelectorAll('#category-filters .category-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.category === category);
    });
    currentCategory = category;
    loadProjects();
}

// 加载项目
function loadProjects() {
    const grid = document.getElementById('project-grid');
    grid.innerHTML = '';
    allImages = [];

    let filtered = commercialProjects;

    // 按分类筛选
    if (currentCategory !== 'all') {
        filtered = filtered.filter(p => p.category === currentCategory);
    }

    // 按年份筛选
    if (currentYear !== 'all') {
        filtered = filtered.filter(p => p.year === parseInt(currentYear));
    }

    // 按年份倒序
    filtered.sort((a, b) => b.year - a.year);

    if (filtered.length === 0) {
        grid.innerHTML = '<p class="no-projects">暂无项目</p>';
        return;
    }

    // 生成项目卡片
    filtered.forEach(project => {
        const card = createProjectCard(project);
        grid.appendChild(card);

        // 收集灯箱图片
        project.items.filter(item => item.type === 'image').forEach(img => {
            allImages.push({
                src: img.src,
                title: img.title || '',
                description: ''
            });
        });
    });

    // 淡入动画
    setTimeout(() => {
        grid.style.opacity = '1';
    }, 50);
}

// 创建项目卡片
function createProjectCard(project) {
    const card = document.createElement('a');
    card.className = 'project-card';
    card.href = `commercial-detail.html?project=${project.id}`;

    const hasVideo = project.items.some(item => item.type === 'video');
    const imageCount = project.items.filter(item => item.type === 'image').length;
    const videoCount = project.items.filter(item => item.type === 'video').length;

    card.innerHTML = `
        <div class="project-card-cover">
            <img src="${project.cover}" alt="${project.client}" loading="lazy">
            ${hasVideo ? '<div class="media-badge video-badge">视频</div>' : ''}
        </div>
        <div class="project-card-info">
            <h3 class="project-client">${project.client}</h3>
            <p class="project-title">${project.title}</p>
            <div class="project-meta">
                <span class="project-year">${project.year}</span>
                <span class="project-category">${project.category}</span>
                <span class="project-counts">
                    ${imageCount > 0 ? `<span class="count-item">${imageCount}图</span>` : ''}
                    ${videoCount > 0 ? `<span class="count-item">${videoCount}视频</span>` : ''}
                </span>
            </div>
        </div>
    `;

    return card;
}