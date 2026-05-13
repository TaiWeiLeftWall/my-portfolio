// ==========================================
// 商业项目数据
// ==========================================

const commercialProjects = [
    {
        id: "brand-a",
        client: "品牌A",
        title: "2024春季广告",
        description: "为品牌A拍摄2024春季系列产品广告，涵盖服装、包袋及配饰等全线产品。",
        cover: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-a/cover.jpg",
        year: 2024,
        category: "广告",
        items: [
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-a/1.jpg" },
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-a/2.jpg" },
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-a/3.jpg" }
        ]
    },
    {
        id: "brand-b",
        client: "品牌B",
        title: "品牌形象片",
        description: "为品牌B打造全新品牌形象片，突出品牌理念与产品特色。",
        cover: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-b/cover.jpg",
        year: 2024,
        category: "视频",
        items: [
            { type: "video", src: "https://www.youtube.com/embed/example1", poster: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-b/poster.jpg" },
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-b/1.jpg" },
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-b/2.jpg" }
        ]
    },
    {
        id: "brand-c",
        client: "品牌C",
        title: "产品目录拍摄",
        description: "品牌C 2024年度产品目录全部产品的专业拍摄。",
        cover: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-c/cover.jpg",
        year: 2023,
        category: "电商",
        items: [
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-c/1.jpg" },
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-c/2.jpg" },
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-c/3.jpg" },
            { type: "image", src: "https://pub-0f1fd51184d04cc28d2ffffbd03a30de.r2.dev/images/commercial/brand-c/4.jpg" }
        ]
    }
];

// 根据 ID 获取项目
function getProjectById(id) {
    return commercialProjects.find(p => p.id === id) || null;
}

// 获取所有年份
function getCommercialYears() {
    const years = new Set(commercialProjects.map(p => p.year));
    return Array.from(years).sort().reverse();
}

// 获取所有分类
function getCommercialCategories() {
    const categories = new Set(commercialProjects.map(p => p.category));
    return Array.from(categories).sort();
}