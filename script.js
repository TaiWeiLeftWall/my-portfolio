// 存储所有可查看的图片（单独图片 + 成组图片）
let allImages = [];

// 当前筛选条件
let currentCategory = 'all';
let currentYear = 'all';
let currentMonth = 'all';

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 根据当前页面加载内容
    const galleryGrid = document.getElementById('gallery-grid');
    const videoGrid = document.getElementById('video-grid');

    if (galleryGrid) {
        loadGallery();
        setupCategoryFilter();
        setupDateFilters();
    }

    if (videoGrid) {
        loadVideos();
    }

    setupLightbox();
});

// 加载画廊照片
function loadGallery(category = 'all') {
    const galleryGrid = document.getElementById('gallery-grid');
    galleryGrid.innerHTML = '';

    // 构建所有图片列表用于灯箱导航
    allImages = [];

    // 筛选单独图片
    let filteredPhotos = category === 'all'
        ? photos
        : photos.filter(photo => photo.category === category);

    // 筛选成组图片
    let filteredGroups = category === 'all'
        ? photoGroups
        : photoGroups.filter(group => group.category === category);

    // 按年份筛选
    if (currentYear !== 'all') {
        filteredPhotos = filteredPhotos.filter(photo => photo.date && photo.date.startsWith(currentYear));
        filteredGroups = filteredGroups.filter(group => group.date && group.date.startsWith(currentYear));
    }

    // 按月份筛选
    if (currentMonth !== 'all') {
        filteredPhotos = filteredPhotos.filter(photo => photo.date && photo.date.endsWith('-' + currentMonth));
        filteredGroups = filteredGroups.filter(group => group.date && group.date.endsWith('-' + currentMonth));
    }

    // 添加单独图片到画廊
    filteredPhotos.forEach(photo => {
        const item = createGalleryItem(photo);
        galleryGrid.appendChild(item);

        // 添加到灯箱图片列表
        allImages.push({
            src: photo.src,
            title: photo.title,
            description: photo.description,
            type: 'single'
        });
    });

    // 添加成组图片到画廊
    filteredGroups.forEach(group => {
        const groupElement = createPhotoGroup(group);
        galleryGrid.appendChild(groupElement);

        // 添加组内图片到灯箱列表
        group.images.forEach(img => {
            allImages.push({
                src: img.src,
                title: img.title,
                description: img.description,
                type: 'group',
                groupTitle: group.title
            });
        });
    });
}

// 创建单独图片项
function createGalleryItem(photo) {
    const item = document.createElement('div');
    item.className = `gallery-item ${photo.orientation}`;
    item.innerHTML = `
        <img src="${photo.src}" alt="${photo.title}" loading="lazy">
        <div class="overlay">
            <h3>${photo.title}</h3>
            <p>${photo.description || ''}</p>
        </div>
    `;

    // 点击打开灯箱
    item.addEventListener('click', () => {
        openLightbox(photo.src, photo.title, photo.description);
    });

    return item;
}

// 创建成组图片 - 叠放样式
function createPhotoGroup(group) {
    const groupElement = document.createElement('div');
    groupElement.className = 'photo-group-stacked';

    const coverImg = group.images[0];
    const otherCount = group.images.length - 1;

    groupElement.innerHTML = `
        <div class="stacked-cover">
            <img src="${coverImg.src}" alt="${coverImg.title}" loading="lazy">
            ${otherCount > 0 ? `<div class="stacked-count">+${otherCount}</div>` : ''}
            <div class="stacked-overlay">
                <span class="stacked-title">${group.title}</span>
            </div>
        </div>
    `;

    // 点击打开组内第一张图片
    groupElement.querySelector('.stacked-cover').addEventListener('click', () => {
        openLightbox(coverImg.src, coverImg.title, coverImg.description);
    });

    return groupElement;
}

// 设置分类筛选
function setupCategoryFilter() {
    const categoryBtns = document.querySelectorAll('.category-btn');

    categoryBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // 更新激活状态
            categoryBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // 更新当前分类
            currentCategory = btn.dataset.category;

            // 加载对应分类的照片
            loadGallery(currentCategory);
        });
    });
}

// 设置日期筛选
function setupDateFilters() {
    const yearFilter = document.getElementById('year-filter');
    const monthFilter = document.getElementById('month-filter');

    if (!yearFilter || !monthFilter) return;

    // 收集所有年份
    const years = new Set();
    const months = new Set();

    photos.forEach(photo => {
        if (photo.date) {
            const [year, month] = photo.date.split('-');
            years.add(year);
            months.add(month);
        }
    });

    photoGroups.forEach(group => {
        if (group.date) {
            const [year, month] = group.date.split('-');
            years.add(year);
            months.add(month);
        }
    });

    // 填充年份下拉框
    const sortedYears = Array.from(years).sort().reverse();
    sortedYears.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year + '年';
        yearFilter.appendChild(option);
    });

    // 填充月份下拉框
    const sortedMonths = Array.from(months).sort();
    const monthNames = ['01月', '02月', '03月', '04月', '05月', '06月', '07月', '08月', '09月', '10月', '11月', '12月'];
    sortedMonths.forEach(month => {
        const option = document.createElement('option');
        option.value = month;
        option.textContent = monthNames[parseInt(month) - 1];
        monthFilter.appendChild(option);
    });

    // 年份筛选事件
    yearFilter.addEventListener('change', () => {
        currentYear = yearFilter.value;
        // 重置月份选择
        monthFilter.value = 'all';
        currentMonth = 'all';
        loadGallery(currentCategory);
    });

    // 月份筛选事件
    monthFilter.addEventListener('change', () => {
        currentMonth = monthFilter.value;
        loadGallery(currentCategory);
    });
}

// 加载视频
function loadVideos() {
    const videoGrid = document.getElementById('video-grid');
    videoGrid.innerHTML = '';

    videos.forEach(video => {
        const item = document.createElement('div');
        item.className = 'video-item';
        item.innerHTML = `
            <div class="video-wrapper">
                <iframe
                    src="${video.url}"
                    title="${video.title}"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowfullscreen>
                </iframe>
            </div>
            <div class="video-info">
                <h3>${video.title}</h3>
                <p>${video.description || ''}</p>
            </div>
        `;
        videoGrid.appendChild(item);
    });
}

// 灯箱功能
let currentImageIndex = 0;

function setupLightbox() {
    const lightbox = document.getElementById('lightbox');
    const closeBtn = document.querySelector('.lightbox-close');

    if (!lightbox) return;

    // 关闭灯箱
    closeBtn.addEventListener('click', closeLightbox);

    // 点击背景关闭
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });

    // ESC 键关闭
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeLightbox();
        }
        // 左右箭头切换图片
        if (e.key === 'ArrowLeft') {
            navigateLightbox(-1);
        }
        if (e.key === 'ArrowRight') {
            navigateLightbox(1);
        }
    });

    // 添加导航按钮
    const prevBtn = document.createElement('div');
    prevBtn.className = 'lightbox-nav lightbox-prev';
    prevBtn.innerHTML = '&#10094;';
    prevBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        navigateLightbox(-1);
    });

    const nextBtn = document.createElement('div');
    nextBtn.className = 'lightbox-nav lightbox-next';
    nextBtn.innerHTML = '&#10095;';
    nextBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        navigateLightbox(1);
    });

    lightbox.appendChild(prevBtn);
    lightbox.appendChild(nextBtn);
}

function openLightbox(src, title, description) {
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxCaption = document.getElementById('lightbox-caption');

    // 找到当前图片索引
    currentImageIndex = allImages.findIndex(img => img.src === src);

    lightboxImg.src = src;

    let captionText = title;
    if (description) {
        captionText += ` - ${description}`;
    }
    lightboxCaption.textContent = captionText;

    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
}

function navigateLightbox(direction) {
    if (allImages.length === 0) return;

    currentImageIndex += direction;

    // 循环导航
    if (currentImageIndex < 0) {
        currentImageIndex = allImages.length - 1;
    }
    if (currentImageIndex >= allImages.length) {
        currentImageIndex = 0;
    }

    const img = allImages[currentImageIndex];
    openLightbox(img.src, img.title, img.description);
}
