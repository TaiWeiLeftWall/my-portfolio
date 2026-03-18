// ==========================================
// 在这里添加你的摄影作品和视频
// ==========================================

// 摄影师名称（在所有页面显示）
const photographerName = "摄影师名称";

// 单独的图片作品
// orientation: 图片方向 - 'horizontal'(3:2横版) 或 'vertical'(2:3竖版)
// title: 作品标题
// description: 作品描述（可选）
// src: 图片URL（可以使用本地路径如 'images/photo1.jpg'）
const photos = [
    // 风光类 - 横版
    {
        category: "landscape",
        orientation: "horizontal",
        title: "日出金山",
        description: "清晨的阳光洒在山峰上",
        src: "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1200&h=800&fit=crop"
    },
    // 风光类 - 竖版
    {
        category: "landscape",
        orientation: "vertical",
        title: "峡谷深处",
        description: "大自然的鬼斧神工",
        src: "https://images.unsplash.com/photo-1474044159687-1ee9f3a51722?w=800&h=1200&fit=crop"
    },
    {
        category: "landscape",
        orientation: "horizontal",
        title: "湖面倒影",
        description: "平静的湖面如镜",
        src: "https://images.unsplash.com/photo-1439066615861-d1af74d74000?w=1200&h=800&fit=crop"
    },
    {
        category: "landscape",
        orientation: "horizontal",
        title: "银河星空",
        description: "夜晚的星空璀璨",
        src: "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=1200&h=800&fit=crop"
    },
    // 人像类 - 竖版为主
    {
        category: "portrait",
        orientation: "vertical",
        title: "少女",
        description: "自然光人像",
        src: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=800&h=1200&fit=crop"
    },
    {
        category: "portrait",
        orientation: "vertical",
        title: "眼神",
        description: "特写人像",
        src: "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800&h=1200&fit=crop"
    },
    {
        category: "portrait",
        orientation: "vertical",
        title: "侧脸",
        description: "光影人像",
        src: "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=800&h=1200&fit=crop"
    },
    // 街头类
    {
        category: "street",
        orientation: "horizontal",
        title: "城市角落",
        description: "日常街景",
        src: "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1200&h=800&fit=crop"
    },
    {
        category: "street",
        orientation: "horizontal",
        title: "雨夜",
        description: "雨中的城市",
        src: "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=1200&h=800&fit=crop"
    },
    // 旅行类
    {
        category: "travel",
        orientation: "horizontal",
        title: "古镇清晨",
        description: "清晨的古镇街道",
        src: "https://images.unsplash.com/photo-1532274402911-5a369e4c4bb5?w=1200&h=800&fit=crop"
    },
    {
        category: "travel",
        orientation: "horizontal",
        title: "海滩日落",
        description: "热带海滩的日落",
        src: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1200&h=800&fit=crop"
    }
];

// 成组的图片作品
// title: 组照标题
// category: 分类
// description: 组照描述（可选）
// cols: 每行图片数量 (2, 3, 或 4)
// images: 图片数组 [{src, title, description}]
const photoGroups = [
    {
        category: "portrait",
        title: "人像系列 - 自然光",
        description: "一组自然光人像作品",
        cols: 3,
        images: [
            {
                src: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=600&h=900&fit=crop",
                title: "午后阳光",
                description: ""
            },
            {
                src: "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=600&h=900&fit=crop",
                title: "窗边",
                description: ""
            },
            {
                src: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=600&h=900&fit=crop",
                title: "微笑",
                description: ""
            }
        ]
    },
    {
        category: "landscape",
        title: "山川风光",
        description: "登山途中记录的美景",
        cols: 2,
        images: [
            {
                src: "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=900&h=600&fit=crop",
                title: "云海",
                description: ""
            },
            {
                src: "https://images.unsplash.com/photo-1454496522488-7a8e488e8606?w=900&h=600&fit=crop",
                title: "雪峰",
                description: ""
            }
        ]
    },
    {
        category: "travel",
        title: "日本之旅",
        description: "东京大阪漫步",
        cols: 3,
        images: [
            {
                src: "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=600&h=800&fit=crop",
                title: "寺庙",
                description: ""
            },
            {
                src: "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600&h=800&fit=crop",
                title: "街头",
                description: ""
            },
            {
                src: "https://images.unsplash.com/photo-1526481280693-3bfa7568e0f3?w=600&h=800&fit=crop",
                title: "夜景",
                description: ""
            }
        ]
    },
    {
        category: "street",
        title: "城市扫街",
        description: "日常citywalk",
        cols: 4,
        images: [
            {
                src: "https://images.unsplash.com/photo-1517732306149-e8f829eb588a?w=600&h=800&fit=crop",
                title: "行人",
                description: ""
            },
            {
                src: "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=600&h=800&fit=crop",
                title: "都市",
                description: ""
            },
            {
                src: "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?w=600&h=800&fit=crop",
                title: "黄昏",
                description: ""
            },
            {
                src: "https://images.unsplash.com/photo-1519501025264-65ba15a82390?w=600&h=800&fit=crop",
                title: "夜色",
                description: ""
            }
        ]
    }
];

// 视频作品
// title: 视频标题
// description: 视频描述（可选）
// url: 视频链接（支持 YouTube/Vimeo）
// type: 'youtube' 或 'vimeo'
const videos = [
    {
        title: "延时摄影 - 城市日落",
        description: "记录城市从黄昏到夜晚的变化",
        url: "https://www.youtube.com/embed/dQw4w9WgXcQ",
        type: "youtube"
    },
    {
        title: "风景短片 - 山川之美",
        description: "探索大自然的壮丽景色",
        url: "https://www.youtube.com/embed/dQw4w9WgXcQ",
        type: "youtube"
    },
    {
        title: "人像短片 - 光影故事",
        description: "用光线讲述人物故事",
        url: "https://www.youtube.com/embed/dQw4w9WgXcQ",
        type: "youtube"
    }
];

// 社交媒体链接
const socialLinks = {
    instagram: "https://instagram.com/yourusername",
    weibo: "https://weibo.com/yourusername",
    xiaohongshu: "https://xiaohongshu.com/user/profile/xxx"
};

// 联系方式
const contact = {
    email: "email@example.com",
    wechat: "photographer",
    phone: "+86 123 4567 8900"
};
