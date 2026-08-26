// 存储所有可查看的图片（单独图片 + 成组图片）
let allImages = [];

// 当前筛选条件
let currentCategory = 'all';
let currentYear = 'all';
let currentMonth = 'all';
let currentDisplayMode = 'stacked';

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 根据当前页面加载内容
    const galleryGrid = document.getElementById('gallery-grid');
    const videoGrid = document.getElementById('video-grid');

    if (galleryGrid) {
        loadGallery();
        setupCategoryFilter();
        setupDateFilters();
        setupDisplayModeToggle();
    }

    if (videoGrid) {
        loadVideos();
    }

    setupLightbox();
});

// 窗口大小变化时重新布局
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        const galleryGrid = document.getElementById('gallery-grid');
        if (galleryGrid && galleryGrid.querySelector('.masonry-columns')) {
            loadGallery(); // 重新加载以适应新列数
        }
    }, 250);
});

// 水印图片URL
const watermarkUrl = 'icons/LOGO_black.png';

// 加载画廊照片
function loadGallery(category = 'all') {
    const galleryGrid = document.getElementById('gallery-grid');
    galleryGrid.innerHTML = '';
    getOrCreateColumns();

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

    // 按月份筛选（结合年份）
    if (currentMonth !== 'all') {
        const monthStr = '-' + currentMonth;
        filteredPhotos = filteredPhotos.filter(photo => {
            if (!photo.date) return false;
            if (currentYear !== 'all') {
                return photo.date === currentYear + monthStr;
            }
            return photo.date.endsWith(monthStr);
        });
        filteredGroups = filteredGroups.filter(group => {
            if (!group.date) return false;
            if (currentYear !== 'all') {
                return group.date === currentYear + monthStr;
            }
            return group.date.endsWith(monthStr);
        });
    }

    // 添加单独图片到画廊
    filteredPhotos.forEach(photo => {
        const item = createGalleryItem(photo);
        insertIntoShortestColumn(item);

        // 添加到灯箱图片列表
        allImages.push({
            src: photo.src,
            title: photo.title,
            description: photo.description,
            type: 'single'
        });
    });

    // 添加成组图片到画廊
    if (currentDisplayMode === 'random') {
        // 随机模式：每组只展示1张随机图片
        filteredGroups.forEach(group => {
            if (group.images.length === 0) return;
            const randomIndex = Math.floor(Math.random() * group.images.length);
            const randomImg = group.images[randomIndex];
            const item = createGalleryItem(randomImg);
            item.dataset.src = randomImg.src;
            allImages.push({
                src: randomImg.src,
                title: randomImg.title,
                description: randomImg.description,
                type: 'single'
            });
            insertIntoShortestColumn(item);
        });
    } else {
        // 时间线模式：瀑布流布局
        filteredGroups.forEach(group => {
            const groupElement = createPhotoGroup(group);

            // 添加组内图片到灯箱列表，同时记录同组图片
            group.images.forEach((img, imgIndex) => {
                allImages.push({
                    src: img.src,
                    title: img.title,
                    description: img.description,
                    type: 'group',
                    groupTitle: group.title,
                    groupImages: group.images,
                    groupIndex: imgIndex
                });
            });

            // 瀑布流布局：插入到最短列
            insertIntoShortestColumn(groupElement);
        });
    }

    // 优先加载首张作品，其余图片继续懒加载
    const columnsContainer = galleryGrid.querySelector('.masonry-columns');
    if (columnsContainer) {
        columnsContainer.style.opacity = '0';
        columnsContainer.style.transition = 'opacity 0.3s ease';

        const firstImage = columnsContainer.querySelector('.gallery-item > img:first-child, .stacked-cover > img:first-child');
        if (firstImage) {
            firstImage.loading = 'eager';
            firstImage.setAttribute('fetchpriority', 'high');
            firstImage.decoding = 'async';
        }

        let revealed = false;
        const revealGallery = () => {
            if (revealed) return;
            revealed = true;
            requestAnimationFrame(() => {
                columnsContainer.style.opacity = '1';
            });
        };

        if (!firstImage || firstImage.complete) {
            revealGallery();
        } else {
            firstImage.addEventListener('load', revealGallery, { once: true });
            firstImage.addEventListener('error', revealGallery, { once: true });
            setTimeout(revealGallery, 600);
        }
    }
}

// 瀑布流：将元素插入到最短列
function insertIntoShortestColumn(element) {
    const galleryGrid = document.getElementById('gallery-grid');
    const columns = getOrCreateColumns();

    let shortestColumn = columns[0];
    let minHeight = columns[0].offsetHeight;

    for (let i = 1; i < columns.length; i++) {
        if (columns[i].offsetHeight < minHeight) {
            minHeight = columns[i].offsetHeight;
            shortestColumn = columns[i];
        }
    }

    shortestColumn.appendChild(element);
}

// 获取或创建列容器
function getOrCreateColumns() {
    const galleryGrid = document.getElementById('gallery-grid');

    // 根据屏幕宽度决定列数
    const width = window.innerWidth;
    let columnCount = 3;
    if (width <= 480) {
        columnCount = 1;
    } else if (width <= 1024) {
        columnCount = 2;
    }

    // 检查是否已有列容器且列数相同
    let columnsContainer = galleryGrid.querySelector('.masonry-columns');
    const existingColumns = columnsContainer ? columnsContainer.querySelectorAll('.masonry-column') : [];

    if (!columnsContainer || existingColumns.length !== columnCount) {
        // 重新创建列容器
        columnsContainer = document.createElement('div');
        columnsContainer.className = 'masonry-columns';
        galleryGrid.innerHTML = ''; // 清空现有内容
        galleryGrid.appendChild(columnsContainer);

        // 创建指定数量的列
        for (let i = 0; i < columnCount; i++) {
            const column = document.createElement('div');
            column.className = 'masonry-column';
            columnsContainer.appendChild(column);
        }
    }

    return columnsContainer.querySelectorAll('.masonry-column');
}

// 创建单独图片项
function createGalleryItem(photo) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `gallery-item`;
    item.setAttribute('aria-label', `查看照片：${photo.title || photo.description || '摄影作品'}`);
    item.innerHTML = `
        <img src="${photo.src}" alt="${photo.title || photo.description || '摄影作品'}" loading="lazy" decoding="async" draggable="false">
        <img class="watermark-overlay" src="${watermarkUrl}" alt="" aria-hidden="true">
    `;

    // 点击打开灯箱
    item.addEventListener('click', () => {
        openLightbox(photo.src, '', '', []);
    });

    return item;
}

// 创建成组图片 - 叠放样式
function createPhotoGroup(group) {
    const groupElement = document.createElement('div');
    groupElement.className = 'photo-group-stacked';

    // 随机选择一张图片作为封面
    const randomIndex = Math.floor(Math.random() * group.images.length);
    const coverImg = group.images[randomIndex];
    const otherCount = group.images.length - 1;

    groupElement.innerHTML = `
        <button type="button" class="stacked-cover" aria-label="查看组图：${group.title || '摄影作品组'}，共 ${group.images.length} 张">
            <img src="${coverImg.src}" alt="${coverImg.title || group.title || '摄影作品组'}" loading="lazy" decoding="async" draggable="false">
            <img class="watermark-overlay" src="${watermarkUrl}" alt="" aria-hidden="true">
            ${otherCount > 0 ? `<span class="stacked-count" aria-hidden="true">+${otherCount}</span>` : ''}
        </button>
    `;

    // 点击打开组内随机一张图片，同时传递整组图片用于预览
    groupElement.querySelector('.stacked-cover').addEventListener('click', () => {
        openLightbox(coverImg.src, '', '', group.images);
    });

    return groupElement;
}

// 设置分类筛选
function setupCategoryFilter() {
    const categoryBtns = document.querySelectorAll('.category-btn');

    categoryBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // 更新激活状态
            categoryBtns.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-pressed', 'false');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-pressed', 'true');

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

// 设置显示模式切换
function setupDisplayModeToggle() {
    const modeBtns = document.querySelectorAll('.mode-btn');

    modeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modeBtns.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-pressed', 'false');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-pressed', 'true');
            currentDisplayMode = btn.dataset.mode;
            loadGallery(currentCategory);
        });
    });
}

// 加载视频（带懒加载）
﻿function loadVideos() {
    const videoGrid = document.getElementById('video-grid');
    videoGrid.innerHTML = '';

    const platformLabels = {
        bilibili: 'Bilibili',
        xiaohongshu: '\u5c0f\u7ea2\u4e66',
        douyin: '\u6296\u97f3'
    };

    const groups = {};
    videos.forEach(v => {
        const p = v.platform || '';
        const s = v.source || '';
        if (!groups[p]) groups[p] = {};
        if (!groups[p][s]) groups[p][s] = [];
        groups[p][s].push(v);
    });

    Object.keys(groups).forEach(platform => {
        const sources = groups[platform];
        const section = document.createElement('div');
        section.className = 'video-section';

        if (platform) {
            const header = document.createElement('div');
            header.className = 'video-platform-header';
            header.textContent = platformLabels[platform] || platform;
            section.appendChild(header);
        }

        Object.keys(sources).forEach(source => {
            if (source) {
                const label = document.createElement('div');
                label.className = 'video-source-label';
                label.textContent = source;
                section.appendChild(label);
            }

            const grid = document.createElement('div');
            grid.className = 'video-grid';

            sources[source].forEach(video => {
                const item = document.createElement('div');
                item.className = 'video-item';
                var isBilibili = video.url.indexOf('bilibili') >= 0;
                if (isBilibili) {
                    item.innerHTML = '<div class="video-wrapper"><button type="button" class="video-placeholder" data-src="' + video.url + '" aria-label="播放视频：' + (video.title || '视频') + '"><span aria-hidden="true">\u25b6</span></button></div>';
                } else {
                    item.innerHTML = '<a href="' + video.url + '" target="_blank" rel="noopener noreferrer" class="video-external-link" aria-label="在新窗口打开视频：' + (video.title || '视频') + '"><div class="video-wrapper"><span class="video-placeholder video-external" aria-hidden="true">\u2197</span></div></a>';
                }
                grid.appendChild(item);

                const placeholder = item.querySelector('button.video-placeholder');
                if (placeholder) {
                    placeholder.addEventListener('click', function() {
                        loadVideoIframe(this, video);
                    });
                }
            });

            section.appendChild(grid);
        });

        videoGrid.appendChild(section);
    });

}

function loadVideoIframe(placeholder, video) {
    if (!video || placeholder.dataset.loaded) return;
    placeholder.dataset.loaded = 'true';

    const wrapper = placeholder.parentElement;
    const iframe = document.createElement('iframe');
    iframe.src = video.url + (video.url.includes('?') ? '&autoplay=0' : '?autoplay=0');
    iframe.title = video.title || '视频';
    iframe.setAttribute('allow', 'accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
    iframe.allowFullscreen = true;
    wrapper.replaceChild(iframe, placeholder);
}

// 灯箱功能
let currentImageIndex = 0;
let currentGroupImages = []; // 当前组的所有图片
let lightboxReturnFocus = null;

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

    // ESC 键关闭 & 左右箭头切换
    document.addEventListener('keydown', (e) => {
        if (!lightbox.classList.contains('active')) return;

        if (e.key === 'Escape') {
            closeLightbox();
            return;
        }
        if (e.key === 'ArrowLeft') {
            navigateLightbox(-1);
        }
        if (e.key === 'ArrowRight') {
            navigateLightbox(1);
        }
        if (e.key === 'Tab') {
            const focusable = Array.from(lightbox.querySelectorAll('button:not([disabled])'))
                .filter((element) => element.offsetParent !== null);
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    });

    // 触摸手势支持
    let touchStartX = 0;
    lightbox.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    lightbox.addEventListener('touchend', (e) => {
        const touchEndX = e.changedTouches[0].screenX;
        const diff = touchStartX - touchEndX;
        if (Math.abs(diff) > 50) {
            navigateLightbox(diff > 0 ? 1 : -1);
        }
    }, { passive: true });

    // 添加导航按钮
    const prevBtn = document.createElement('button');
    prevBtn.type = 'button';
    prevBtn.className = 'lightbox-nav lightbox-prev';
    prevBtn.setAttribute('aria-label', '上一张图片');
    prevBtn.innerHTML = '&#10094;';
    prevBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        navigateLightbox(-1);
    });

    const nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.className = 'lightbox-nav lightbox-next';
    nextBtn.setAttribute('aria-label', '下一张图片');
    nextBtn.innerHTML = '&#10095;';
    nextBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        navigateLightbox(1);
    });

    lightbox.appendChild(prevBtn);
    lightbox.appendChild(nextBtn);
}

function openLightbox(src, title, description, groupImages = []) {
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const previewStrip = document.getElementById('lightbox-preview-strip');

    // 找到当前图片索引
    currentImageIndex = allImages.findIndex(img => img.src === src);

    if (!lightbox.classList.contains('active')) {
        lightboxReturnFocus = document.activeElement;
    }

    lightboxImg.src = src;
    lightboxImg.alt = title || description || '摄影作品大图';
    lightboxCaption.textContent = title || description || '';

    // 如果有组图片，显示预览条
    currentGroupImages = groupImages;
    if (currentGroupImages.length > 1) {
        previewStrip.innerHTML = '';
        previewStrip.style.display = 'flex';

        currentGroupImages.forEach((img, index) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'lightbox-preview-item' + (img.src === src ? ' active' : '');
            item.setAttribute('aria-label', `查看缩略图 ${index + 1}`);
            if (img.src === src) item.setAttribute('aria-current', 'true');
            item.innerHTML = `<img src="${img.src}" alt="" loading="lazy" decoding="async">`;
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                openLightbox(img.src, '', '', currentGroupImages);
            });
            previewStrip.appendChild(item);
        });
    } else {
        previewStrip.style.display = 'none';
    }

    lightbox.classList.add('active');
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.querySelector('.lightbox-close').focus();
}

function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    if (!lightbox.classList.contains('active')) return;
    lightbox.classList.remove('active');
    lightbox.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    currentGroupImages = [];
    if (lightboxReturnFocus && typeof lightboxReturnFocus.focus === 'function') {
        lightboxReturnFocus.focus();
    }
    lightboxReturnFocus = null;
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
    const groupImages = img.groupImages || [];
    openLightbox(img.src, img.title, img.description, groupImages);
}
