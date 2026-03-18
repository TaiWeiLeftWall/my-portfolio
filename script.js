// 存储所有可查看的图片（单独图片 + 成组图片）
let allImages = [];

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 根据当前页面加载内容
    const galleryGrid = document.getElementById('gallery-grid');
    const videoGrid = document.getElementById('video-grid');

    if (galleryGrid) {
        loadGallery();
        setupCategoryFilter();
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
    const filteredPhotos = category === 'all'
        ? photos
        : photos.filter(photo => photo.category === category);

    // 筛选成组图片
    const filteredGroups = category === 'all'
        ? photoGroups
        : photoGroups.filter(group => group.category === category);

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

// 创建成组图片
function createPhotoGroup(group) {
    const groupElement = document.createElement('div');
    groupElement.className = 'photo-group';

    // 确定列类
    const colsClass = `cols-${group.cols}`;

    groupElement.innerHTML = `
        <div class="photo-group-header">
            <span class="photo-group-badge">组照</span>
            <span class="photo-group-title">${group.title}</span>
        </div>
        <div class="photo-group-grid ${colsClass}">
            ${group.images.map(img => `
                <div class="photo-group-item">
                    <img src="${img.src}" alt="${img.title}" loading="lazy">
                </div>
            `).join('')}
        </div>
    `;

    // 为组内每张图片添加点击事件
    const items = groupElement.querySelectorAll('.photo-group-item');
    items.forEach((item, index) => {
        item.addEventListener('click', () => {
            const img = group.images[index];
            openLightbox(img.src, img.title, img.description);
        });
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

            // 加载对应分类的照片
            const category = btn.dataset.category;
            loadGallery(category);
        });
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
