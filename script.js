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
        });
        // 瀑布流布局：插入到最短列
        filteredGroups.forEach(group => {
            if (group.images.length === 0) return;
            const randomIndex = Math.floor(Math.random() * group.images.length);
            const randomImg = group.images[randomIndex];
            const item = createGalleryItem(randomImg);
            item.dataset.src = randomImg.src;
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

    // 隐藏 masonry 容器，等图片加载完成后再显示
    const columnsContainer = galleryGrid.querySelector('.masonry-columns');
    if (columnsContainer) {
        columnsContainer.style.opacity = '0';
        columnsContainer.style.transition = 'opacity 0.3s ease';

        // 等待图片加载完成后再显示（不调整布局，防止跳动）
        imagesLoaded(columnsContainer, () => {
            requestAnimationFrame(() => {
                columnsContainer.style.opacity = '1';
            });
        });
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

// 图片加载检测
function imagesLoaded(container, callback) {
    const images = container.querySelectorAll('img');
    let loadedCount = 0;

    if (images.length === 0) {
        callback();
        return;
    }

    function checkComplete() {
        if (loadedCount >= images.length) {
            callback();
        }
    }

    images.forEach(img => {
        if (img.complete) {
            loadedCount++;
            checkComplete();
        } else {
            img.addEventListener('load', () => {
                loadedCount++;
                checkComplete();
            });
            img.addEventListener('error', () => {
                loadedCount++;
                checkComplete();
            });
        }
    });

    // 超时保护（5秒后强制执行）
    setTimeout(callback, 5000);
}

// 创建单独图片项
function createGalleryItem(photo) {
    const item = document.createElement('div');
    item.className = `gallery-item ${photo.orientation}`;
    item.innerHTML = `
        <div class="img-wrapper">
            <img src="${photo.src}" alt="" loading="lazy" draggable="false">
        </div>
        <img class="watermark-overlay" src="${watermarkUrl}" alt="watermark">
    `;

    // 图片加载完成后显示
    const img = item.querySelector('.img-wrapper img');
    img.addEventListener('load', () => img.classList.add('loaded'));
    img.addEventListener('error', () => img.classList.add('loaded'));

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
        <div class="stacked-cover">
            <div class="img-wrapper">
                <img src="${coverImg.src}" alt="" loading="lazy" draggable="false">
            </div>
            <img class="watermark-overlay" src="${watermarkUrl}" alt="watermark">
            ${otherCount > 0 ? `<div class="stacked-count">+${otherCount}</div>` : ''}
        </div>
    `;

    // 图片加载完成后显示
    const img = groupElement.querySelector('.img-wrapper img');
    img.addEventListener('load', () => img.classList.add('loaded'));
    img.addEventListener('error', () => img.classList.add('loaded'));

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

// 设置显示模式切换
function setupDisplayModeToggle() {
    const modeBtns = document.querySelectorAll('.mode-btn');

    modeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentDisplayMode = btn.dataset.mode;
            loadGallery(currentCategory);
        });
    });
}

// 加载视频（带懒加载）
function loadVideos() {
    const videoGrid = document.getElementById('video-grid');
    videoGrid.innerHTML = '';

    videos.forEach(video => {
        const item = document.createElement('div');
        item.className = 'video-item';
        item.innerHTML = `
            <div class="video-wrapper">
                <div class="video-placeholder" data-src="${video.url}">▶</div>
            </div>
        `;
        videoGrid.appendChild(item);

        // 点击占位符加载 iframe
        const placeholder = item.querySelector('.video-placeholder');
        placeholder.addEventListener('click', () => {
            loadVideoIframe(placeholder, video);
        });
    });

    // 使用 IntersectionObserver 预加载（滚动到视口时自动加载）
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const placeholder = entry.target;
                    loadVideoIframe(placeholder, videos.find(v => v.url === placeholder.dataset.src));
                    observer.unobserve(placeholder);
                }
            });
        }, { rootMargin: '200px' });

        document.querySelectorAll('.video-placeholder').forEach(el => {
            observer.observe(el);
        });
    }
}

// 加载单个视频 iframe
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
        if (e.key === 'Escape') {
            closeLightbox();
        }
        if (e.key === 'ArrowLeft') {
            navigateLightbox(-1);
        }
        if (e.key === 'ArrowRight') {
            navigateLightbox(1);
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

function openLightbox(src, title, description, groupImages = []) {
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const previewStrip = document.getElementById('lightbox-preview-strip');

    // 找到当前图片索引
    currentImageIndex = allImages.findIndex(img => img.src === src);

    lightboxImg.src = src;
    lightboxCaption.textContent = '';

    // 如果有组图片，显示预览条
    currentGroupImages = groupImages;
    if (currentGroupImages.length > 1) {
        previewStrip.style.display = 'flex';
        setupPreviewStrip(src, groupImages);
    } else {
        previewStrip.style.display = 'none';
        previewStrip.innerHTML = '';
    }

    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
}

// 设置预览条：懒加载 + 预热相邻1张
let previewObserver = null;

function setupPreviewStrip(activeSrc, groupImages) {
    const previewStrip = document.getElementById('lightbox-preview-strip');
    previewStrip.innerHTML = '';

    // 找到当前激活索引
    const activeIndex = groupImages.findIndex(img => img.src === activeSrc);
    const len = groupImages.length;

    groupImages.forEach((img, index) => {
        const item = document.createElement('div');
        item.className = 'lightbox-preview-item' + (img.src === activeSrc ? ' active' : '');
        item.dataset.index = index;

        const imgEl = document.createElement('img');
        imgEl.alt = '';

        // 计算与当前激活项的距离
        const dist = Math.abs(index - activeIndex);

        if (dist === 0) {
            // 当前项：立即加载
            imgEl.src = img.src;
        } else if (dist === 1) {
            // 相邻项：预加载
            imgEl.src = img.src;
        } else {
            // 其余项：懒加载
            imgEl.dataset.lazySrc = img.src;
            imgEl.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"%3E%3C/svg%3E';
        }

        item.appendChild(imgEl);

        item.addEventListener('click', (e) => {
            e.stopPropagation();
            if (img.src !== activeSrc) {
                navigateToImage(img.src, groupImages);
            }
        });

        previewStrip.appendChild(item);
    });

    // 设置 IntersectionObserver 懒加载其余预览项
    if (previewObserver) previewObserver.disconnect();
    previewObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                const lazySrc = img.dataset.lazySrc;
                if (lazySrc) {
                    img.src = lazySrc;
                    delete img.dataset.lazySrc;
                }
            }
        });
    }, { root: previewStrip, threshold: 0.1 });

    previewStrip.querySelectorAll('img[data-lazy-src]').forEach(img => {
        previewObserver.observe(img);
    });
}

// 导航到指定图片（在组内）
function navigateToImage(src, groupImages) {
    const lightboxImg = document.getElementById('lightbox-img');
    const previewStrip = document.getElementById('lightbox-preview-strip');

    // 更新主图
    lightboxImg.src = src;

    // 更新预览条激活状态
    const items = previewStrip.querySelectorAll('.lightbox-preview-item');
    items.forEach(item => {
        const index = parseInt(item.dataset.index);
        const img = groupImages[index];
        if (img.src === src) {
            item.classList.add('active');
            const imgEl = item.querySelector('img');
            // 如果是懒加载项，现在加载
            if (imgEl.dataset.lazySrc) {
                imgEl.src = img.src;
                delete imgEl.dataset.lazySrc;
            }
            // 预热相邻
            preloadAdjacent(index, groupImages);
        } else {
            item.classList.remove('active');
        }
    });
}

// 预加载相邻图片
function preloadAdjacent(currentIndex, groupImages) {
    const len = groupImages.length;
    const previewStrip = document.getElementById('lightbox-preview-strip');
    const items = previewStrip.querySelectorAll('.lightbox-preview-item');

    [currentIndex - 1, currentIndex + 1].forEach(offset => {
        if (offset < 0 || offset >= len) return;
        const item = items[offset];
        if (!item) return;
        const imgEl = item.querySelector('img');
        if (imgEl.dataset.lazySrc) {
            imgEl.src = groupImages[offset].src;
            delete imgEl.dataset.lazySrc;
        }
    });
}

function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
    currentGroupImages = [];
    if (previewObserver) {
        previewObserver.disconnect();
    }
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

    // 检测是否跨组：比较 src 列表是否相同
    const isSameGroup = groupImages.length > 1 &&
        currentGroupImages.length === groupImages.length &&
        currentGroupImages.every((g, i) => g.src === groupImages[i].src);

    if (isSameGroup) {
        // 同组内导航：只更新主图和预览条激活状态
        navigateToImage(img.src, groupImages);
    } else {
        openLightbox(img.src, img.title, img.description, groupImages);
    }
}
