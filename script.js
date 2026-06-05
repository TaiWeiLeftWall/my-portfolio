// 瀛樺偍鎵€鏈夊彲鏌ョ湅鐨勫浘鐗囷紙鍗曠嫭鍥剧墖 + 鎴愮粍鍥剧墖锛?
let allImages = [];

// 褰撳墠绛涢€夋潯浠?
let currentCategory = 'all';
let currentYear = 'all';
let currentMonth = 'all';
let currentDisplayMode = 'stacked';

// 椤甸潰鍔犺浇瀹屾垚鍚庡垵濮嬪寲
// init — wait for both DOM and data
let _domReady = false, _dataReady = false;
function _init() {
    if (!_domReady || !_dataReady) return;
    const galleryGrid = document.getElementById('gallery-grid');
    const videoGrid = document.getElementById('video-grid');
    if (galleryGrid) {
        loadGallery();
        setupCategoryFilter();
        setupDateFilters();
        setupDisplayModeToggle();
    }
    if (videoGrid) loadVideos();
    setupLightbox();
}
document.addEventListener('DOMContentLoaded', function() { _domReady = true; _init(); });
document.addEventListener('data-ready', function() { _dataReady = true; _init(); });
setTimeout(function() { if (!_dataReady) { _dataReady = true; _init(); } }, 2000););

// 绐楀彛澶у皬鍙樺寲鏃堕噸鏂板竷灞€
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        const galleryGrid = document.getElementById('gallery-grid');
        if (galleryGrid && galleryGrid.querySelector('.masonry-columns')) {
            loadGallery(); // 閲嶆柊鍔犺浇浠ラ€傚簲鏂板垪鏁?
        }
    }, 250);
});

// 姘村嵃鍥剧墖URL
const watermarkUrl = 'icons/LOGO_black.png';
const transparentPixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';




// 鍔犺浇鐢诲粖鐓х墖
function loadGallery(category = 'all') {
    const galleryGrid = document.getElementById('gallery-grid');
    galleryGrid.innerHTML = '';

    // 鏋勫缓鎵€鏈夊浘鐗囧垪琛ㄧ敤浜庣伅绠卞鑸?
    allImages = [];

    // 绛涢€夊崟鐙浘鐗?
    let filteredPhotos = category === 'all'
        ? photos
        : photos.filter(photo => photo.category === category);

    // 绛涢€夋垚缁勫浘鐗?
    let filteredGroups = category === 'all'
        ? photoGroups
        : photoGroups.filter(group => group.category === category);

    // 鎸夊勾浠界瓫閫?
    if (currentYear !== 'all') {
        filteredPhotos = filteredPhotos.filter(photo => photo.date && photo.date.startsWith(currentYear));
        filteredGroups = filteredGroups.filter(group => group.date && group.date.startsWith(currentYear));
    }

    // 鎸夋湀浠界瓫閫夛紙缁撳悎骞翠唤锛?
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

    // 娣诲姞鍗曠嫭鍥剧墖鍒扮敾寤?
    filteredPhotos.forEach(photo => {
        const item = createGalleryItem(photo);
        galleryGrid.appendChild(item);

        // 娣诲姞鍒扮伅绠卞浘鐗囧垪琛?
        allImages.push({
            src: photo.src,
            title: photo.title,
            description: photo.description,
            type: 'single'
        });
    });

    // 娣诲姞鎴愮粍鍥剧墖鍒扮敾寤?
    if (currentDisplayMode === 'random') {
        // 闅忔満妯″紡锛氭瘡缁勫彧灞曠ず1寮犻殢鏈哄浘鐗?
        filteredGroups.forEach(group => {
            if (group.images.length === 0) return;
            const randomIndex = Math.floor(Math.random() * group.images.length);
            const randomImg = group.images[randomIndex];
            const item = createGalleryItem(randomImg);
            item.dataset.src = randomImg.src;
            insertIntoShortestColumn(item);
            allImages.push({
                src: randomImg.src,
                title: randomImg.title,
                description: randomImg.description,
                type: 'single'
            });
        });
        // Removed duplicate forEach
        /*
            if (group.images.length === 0) return;
            const randomIndex = Math.floor(Math.random() * group.images.length);
            const randomImg = group.images[randomIndex];
            const item = createGalleryItem(randomImg);
            item.dataset.src = randomImg.src;
            insertIntoShortestColumn(item);
        });
        */
    } else {
        // 鏃堕棿绾挎ā寮忥細鐎戝竷娴佸竷灞€
        filteredGroups.forEach(group => {
            const groupElement = createPhotoGroup(group);

            // 娣诲姞缁勫唴鍥剧墖鍒扮伅绠卞垪琛紝鍚屾椂璁板綍鍚岀粍鍥剧墖
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

            // 鐎戝竷娴佸竷灞€锛氭彃鍏ュ埌鏈€鐭垪
            insertIntoShortestColumn(groupElement);
        });
    }

    // 闅愯棌 masonry 瀹瑰櫒锛岀瓑鍥剧墖鍔犺浇瀹屾垚鍚庡啀鏄剧ず
    const columnsContainer = galleryGrid.querySelector('.masonry-columns');
    if (columnsContainer) {
        columnsContainer.style.opacity = '0';
        columnsContainer.style.transition = 'opacity 0.3s ease';

        // 绛夊緟鍥剧墖鍔犺浇瀹屾垚鍚庡啀鏄剧ず锛堜笉璋冩暣甯冨眬锛岄槻姝㈣烦鍔級
        imagesLoaded(columnsContainer, () => {
            requestAnimationFrame(() => {
                columnsContainer.style.opacity = '1';
            });
        });
    }
}

// 鐎戝竷娴侊細灏嗗厓绱犳彃鍏ュ埌鏈€鐭垪
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

// 鑾峰彇鎴栧垱寤哄垪瀹瑰櫒
function getOrCreateColumns() {
    const galleryGrid = document.getElementById('gallery-grid');

    // 鏍规嵁灞忓箷瀹藉害鍐冲畾鍒楁暟
    const width = window.innerWidth;
    let columnCount = 3;
    if (width <= 480) {
        columnCount = 1;
    } else if (width <= 1024) {
        columnCount = 2;
    }

    // 妫€鏌ユ槸鍚﹀凡鏈夊垪瀹瑰櫒涓斿垪鏁扮浉鍚?
    let columnsContainer = galleryGrid.querySelector('.masonry-columns');
    const existingColumns = columnsContainer ? columnsContainer.querySelectorAll('.masonry-column') : [];

    if (!columnsContainer || existingColumns.length !== columnCount) {
        // 閲嶆柊鍒涘缓鍒楀鍣?
        columnsContainer = document.createElement('div');
        columnsContainer.className = 'masonry-columns';
        galleryGrid.innerHTML = ''; // 娓呯┖鐜版湁鍐呭
        galleryGrid.appendChild(columnsContainer);

        // 鍒涘缓鎸囧畾鏁伴噺鐨勫垪
        for (let i = 0; i < columnCount; i++) {
            const column = document.createElement('div');
            column.className = 'masonry-column';
            columnsContainer.appendChild(column);
        }
    }

    return columnsContainer.querySelectorAll('.masonry-column');
}

// 鍥剧墖鍔犺浇妫€娴?
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

    // 瓒呮椂淇濇姢锛?绉掑悗寮哄埗鎵ц锛?
    setTimeout(callback, 5000);
}

// 鍒涘缓鍗曠嫭鍥剧墖椤?
function createGalleryItem(photo) {
    const item = document.createElement('div');
    item.className = 'gallery-item';
    item.innerHTML = `
        <div class="img-wrapper">
            <img src="${transparentPixel}" data-src="${photo.src}" alt="" loading="lazy" decoding="async" draggable="false">
        </div>
        <img class="watermark-overlay" src="${watermarkUrl}" alt="watermark">
    `;

    // 鍥剧墖鍔犺浇瀹屾垚鍚庢樉绀?
    const img = item.querySelector('.img-wrapper img');
    img.addEventListener('load', () => img.classList.add('loaded'));
    img.addEventListener('error', () => img.classList.add('loaded'));
    observeLazyImage(img);

    // 鐐瑰嚮鎵撳紑鐏
    item.addEventListener('click', () => {
        openLightbox(photo.src, '', '', []);
    });

    return item;
}

// 鍒涘缓鎴愮粍鍥剧墖 - 鍙犳斁鏍峰紡
function createPhotoGroup(group) {
    const groupElement = document.createElement('div');
    groupElement.className = 'photo-group-stacked';

    // 闅忔満閫夋嫨涓€寮犲浘鐗囦綔涓哄皝闈?
    const randomIndex = Math.floor(Math.random() * group.images.length);
    const coverImg = group.images[randomIndex];
    const otherCount = group.images.length - 1;

    groupElement.innerHTML = `
        <div class="stacked-cover">
            <div class="img-wrapper">
                <img src="${transparentPixel}" data-src="${coverImg.src}" alt="" loading="lazy" decoding="async" draggable="false">
            </div>
            <img class="watermark-overlay" src="${watermarkUrl}" alt="watermark">
            ${otherCount > 0 ? `<div class="stacked-count">+${otherCount}</div>` : ''}
        </div>
    `;

    // 鍥剧墖鍔犺浇瀹屾垚鍚庢樉绀?
    const img = groupElement.querySelector('.img-wrapper img');
    img.addEventListener('load', () => img.classList.add('loaded'));
    img.addEventListener('error', () => img.classList.add('loaded'));
    observeLazyImage(img);

    // 鐐瑰嚮鎵撳紑缁勫唴闅忔満涓€寮犲浘鐗囷紝鍚屾椂浼犻€掓暣缁勫浘鐗囩敤浜庨瑙?
    groupElement.querySelector('.stacked-cover').addEventListener('click', () => {
        openLightbox(coverImg.src, '', '', group.images);
    });

    return groupElement;
}

// 璁剧疆鍒嗙被绛涢€?
function setupCategoryFilter() {
    const categoryBtns = document.querySelectorAll('.category-btn');

    categoryBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // 鏇存柊婵€娲荤姸鎬?
            categoryBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // 鏇存柊褰撳墠鍒嗙被
            currentCategory = btn.dataset.category;

            // 鍔犺浇瀵瑰簲鍒嗙被鐨勭収鐗?
            loadGallery(currentCategory);
        });
    });
}

// 璁剧疆鏃ユ湡绛涢€?
function setupDateFilters() {
    const yearFilter = document.getElementById('year-filter');
    const monthFilter = document.getElementById('month-filter');

    if (!yearFilter || !monthFilter) return;

    // 鏀堕泦鎵€鏈夊勾浠?
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

    // 濉厖骞翠唤涓嬫媺妗?
    const sortedYears = Array.from(years).sort().reverse();
    sortedYears.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year + '骞?;
        yearFilter.appendChild(option);
    });

    // 濉厖鏈堜唤涓嬫媺妗?
    const sortedMonths = Array.from(months).sort();
    const monthNames = ['01鏈?, '02鏈?, '03鏈?, '04鏈?, '05鏈?, '06鏈?, '07鏈?, '08鏈?, '09鏈?, '10鏈?, '11鏈?, '12鏈?];
    sortedMonths.forEach(month => {
        const option = document.createElement('option');
        option.value = month;
        option.textContent = monthNames[parseInt(month) - 1];
        monthFilter.appendChild(option);
    });

    // 骞翠唤绛涢€変簨浠?
    yearFilter.addEventListener('change', () => {
        currentYear = yearFilter.value;
        // 閲嶇疆鏈堜唤閫夋嫨
        monthFilter.value = 'all';
        currentMonth = 'all';
        loadGallery(currentCategory);
    });

    // 鏈堜唤绛涢€変簨浠?
    monthFilter.addEventListener('change', () => {
        currentMonth = monthFilter.value;
        loadGallery(currentCategory);
    });
}

// 璁剧疆鏄剧ず妯″紡鍒囨崲
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

// 鍔犺浇瑙嗛锛堝甫鎳掑姞杞斤級
function loadVideos() {
    const videoGrid = document.getElementById('video-grid');
    videoGrid.innerHTML = '';

    videos.forEach(video => {
        const item = document.createElement('div');
        item.className = 'video-item';
        item.innerHTML = `
            <div class="video-wrapper">
                <div class="video-placeholder" data-src="${video.url}">鈻?/div>
            </div>
        `;
        videoGrid.appendChild(item);

        // 鐐瑰嚮鍗犱綅绗﹀姞杞?iframe
        const placeholder = item.querySelector('.video-placeholder');
        placeholder.addEventListener('click', () => {
            loadVideoIframe(placeholder, video);
        });
    });

    // 浣跨敤 IntersectionObserver 棰勫姞杞斤紙婊氬姩鍒拌鍙ｆ椂鑷姩鍔犺浇锛?
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

// 鍔犺浇鍗曚釜瑙嗛 iframe
function loadVideoIframe(placeholder, video) {
    if (!video || placeholder.dataset.loaded) return;
    placeholder.dataset.loaded = 'true';

    const wrapper = placeholder.parentElement;
    const iframe = document.createElement('iframe');
    iframe.src = video.url + (video.url.includes('?') ? '&autoplay=0' : '?autoplay=0');
    iframe.title = video.title || '瑙嗛';
    iframe.setAttribute('allow', 'accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
    iframe.allowFullscreen = true;
    wrapper.replaceChild(iframe, placeholder);
}

// 鐏鍔熻兘
let currentImageIndex = 0;
let currentGroupImages = []; // 褰撳墠缁勭殑鎵€鏈夊浘鐗?

function setupLightbox() {
    const lightbox = document.getElementById('lightbox');
    const closeBtn = document.querySelector('.lightbox-close');

    if (!lightbox) return;

    // 鍏抽棴鐏
    closeBtn.addEventListener('click', closeLightbox);

    // 鐐瑰嚮鑳屾櫙鍏抽棴
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });

    // ESC 閿叧闂?& 宸﹀彸绠ご鍒囨崲
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

    // 瑙︽懜鎵嬪娍鏀寔
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

    // 娣诲姞瀵艰埅鎸夐挳
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

    // 鎵惧埌褰撳墠鍥剧墖绱㈠紩
    currentImageIndex = allImages.findIndex(img => img.src === src);

    lightboxImg.src = src;
    lightboxCaption.textContent = '';

    // 濡傛灉鏈夌粍鍥剧墖锛屾樉绀洪瑙堟潯
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

// 璁剧疆棰勮鏉★細鎳掑姞杞?+ 棰勭儹鐩搁偦1寮?
let previewObserver = null;

function setupPreviewStrip(activeSrc, groupImages) {
    const previewStrip = document.getElementById('lightbox-preview-strip');
    previewStrip.innerHTML = '';

    // 鎵惧埌褰撳墠婵€娲荤储寮?
    const activeIndex = groupImages.findIndex(img => img.src === activeSrc);
    const len = groupImages.length;

    groupImages.forEach((img, index) => {
        const item = document.createElement('div');
        item.className = 'lightbox-preview-item' + (img.src === activeSrc ? ' active' : '');
        item.dataset.index = index;

        const imgEl = document.createElement('img');
        imgEl.alt = '';

        // 璁＄畻涓庡綋鍓嶆縺娲婚」鐨勮窛绂?
        const dist = Math.abs(index - activeIndex);

        if (dist === 0) {
            // 褰撳墠椤癸細绔嬪嵆鍔犺浇
            imgEl.src = img.src;
        } else if (dist === 1) {
            // 鐩搁偦椤癸細棰勫姞杞?
            imgEl.src = img.src;
        } else {
            // 鍏朵綑椤癸細鎳掑姞杞?
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

    // 璁剧疆 IntersectionObserver 鎳掑姞杞藉叾浣欓瑙堥」
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

// 瀵艰埅鍒版寚瀹氬浘鐗囷紙鍦ㄧ粍鍐咃級
function navigateToImage(src, groupImages) {
    const lightboxImg = document.getElementById('lightbox-img');
    const previewStrip = document.getElementById('lightbox-preview-strip');

    // 鏇存柊涓诲浘
    lightboxImg.src = src;

    // 鏇存柊棰勮鏉℃縺娲荤姸鎬?
    const items = previewStrip.querySelectorAll('.lightbox-preview-item');
    items.forEach(item => {
        const index = parseInt(item.dataset.index);
        const img = groupImages[index];
        if (img.src === src) {
            item.classList.add('active');
            const imgEl = item.querySelector('img');
            // 濡傛灉鏄噿鍔犺浇椤癸紝鐜板湪鍔犺浇
            if (imgEl.dataset.lazySrc) {
                imgEl.src = img.src;
                delete imgEl.dataset.lazySrc;
            }
            // 棰勭儹鐩搁偦
            preloadAdjacent(index, groupImages);
        } else {
            item.classList.remove('active');
        }
    });
}

// 棰勫姞杞界浉閭诲浘鐗?
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

    // 寰幆瀵艰埅
    if (currentImageIndex < 0) {
        currentImageIndex = allImages.length - 1;
    }
    if (currentImageIndex >= allImages.length) {
        currentImageIndex = 0;
    }

    const img = allImages[currentImageIndex];
    const groupImages = img.groupImages || [];

    // 妫€娴嬫槸鍚﹁法缁勶細姣旇緝 src 鍒楄〃鏄惁鐩稿悓
    const isSameGroup = groupImages.length > 1 &&
        currentGroupImages.length === groupImages.length &&
        currentGroupImages.every((g, i) => g.src === groupImages[i].src);

    if (isSameGroup) {
        // 鍚岀粍鍐呭鑸細鍙洿鏂颁富鍥惧拰棰勮鏉℃縺娲荤姸鎬?
        navigateToImage(img.src, groupImages);
    } else {
        openLightbox(img.src, img.title, img.description, groupImages);
    }
}
