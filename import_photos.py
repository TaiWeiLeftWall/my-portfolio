#!/usr/bin/env python3
"""
图片导入工具
- 压缩大于10MB的图片到10MB
- 按分类（年份+事件）存储到 images 目录
- 生成 photoGroups 格式（按事件分组）
"""

import os
import shutil
from PIL import Image
import re

# 源文件夹
SOURCE_DIR = r"G:\1A新闻片作品汇总\1A新闻片作品汇总\公务摄影"
# 目标目录
TARGET_BASE = r"C:\Users\1222\my-website\images\官方"
# 最大文件大小 (1.5MB)
MAX_SIZE_MB = 1.5
# 最大尺寸（宽或高）
MAX_DIMENSION = 2500

def get_file_size_mb(filepath):
    """获取文件大小(MB)"""
    return os.path.getsize(filepath) / (1024 * 1024)

def compress_image(src_path, dst_path):
    """压缩图片到指定大小和尺寸"""
    try:
        img = Image.open(src_path)

        # 检查并调整尺寸
        width, height = img.size
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            ratio = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)

        # 如果格式是 RGBA，转换为 RGB
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background

        # 保存，逐步降低质量直到合适 (1.5MB)
        for quality in [90, 80, 70, 60, 50, 40]:
            img.save(dst_path, 'JPEG', quality=quality, optimize=True)
            if os.path.getsize(dst_path) < MAX_SIZE_MB * 1024 * 1024:
                return True

        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False

def process_images():
    """处理所有图片"""
    os.makedirs(TARGET_BASE, exist_ok=True)

    # 存储生成的组照数据
    photo_groups = []

    years = ['2021', '2022', '2023', '2024']

    for year in years:
        year_dir = os.path.join(SOURCE_DIR, year)
        if not os.path.exists(year_dir):
            continue

        print(f"\n=== {year} 年 ===")

        # 获取所有事件目录
        try:
            events = [d for d in os.listdir(year_dir) if os.path.isdir(os.path.join(year_dir, d))]
        except Exception as e:
            print(f"  Error: {e}")
            continue

        events.sort()

        for event in events:
            event_dir = os.path.join(year_dir, event)
            print(f"\n处理: {event}")

            # 清理事件名
            safe_event = re.sub(r'[<>:"/\\|?*]', '_', event)
            event_category = f"{year}-{safe_event}"
            target_dir = os.path.join(TARGET_BASE, event_category)
            os.makedirs(target_dir, exist_ok=True)

            # 获取所有图片
            images = []
            try:
                for f in os.listdir(event_dir):
                    if f.startswith('.') or f.startswith('@'):
                        continue
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        images.append(f)
            except Exception as e:
                print(f"  Error reading: {e}")
                continue

            if not images:
                print(f"  无图片")
                continue

            # 处理每张图片
            group_images = []
            for img_name in sorted(images):
                src_path = os.path.join(event_dir, img_name)

                # 目标文件名
                dst_name = f"{safe_event}_{img_name}"
                dst_path = os.path.join(target_dir, dst_name)

                # 检查大小并处理
                try:
                    file_size = get_file_size_mb(src_path)
                    if file_size > MAX_SIZE_MB:
                        print(f"  压缩: {img_name} ({file_size:.1f}MB)...")
                        if compress_image(src_path, dst_path):
                            new_size = get_file_size_mb(dst_path)
                            print(f"    -> {new_size:.1f}MB")
                        else:
                            print(f"    失败，跳过")
                            continue
                    else:
                        # 检查尺寸
                        img = Image.open(src_path)
                        width, height = img.size
                        if width > MAX_DIMENSION or height > MAX_DIMENSION:
                            print(f"  调整尺寸: {img_name}")
                            compress_image(src_path, dst_path)
                        else:
                            # 直接复制
                            shutil.copy2(src_path, dst_path)

                    # 添加到组
                    rel_path = f"images/官方/{event_category}/{dst_name}"
                    group_images.append({
                        'src': rel_path,
                        'title': os.path.splitext(img_name)[0],
                        'description': ''
                    })

                except Exception as e:
                    print(f"  Error: {img_name} - {e}")
                    continue

            print(f"  完成: {len(group_images)} 张")

            # 提取日期
            month_match = re.search(r'(\d{4})(\d{2})', event)
            date_str = f"{year}-{month_match.group(2)}" if month_match else f"{year}-01"

            # 确定列数
            cols = 3
            if len(group_images) <= 4:
                cols = 2
            elif len(group_images) > 12:
                cols = 4

            # 添加到组照
            photo_groups.append({
                'category': 'official',
                'title': event,
                'description': '',
                'date': date_str,
                'cols': cols,
                'images': group_images
            })

    # 生成代码
    print("\n\n=== 生成代码 ===")

    code_lines = []
    code_lines.append("// 公务摄影照片组 - 由 import_photos.py 自动生成")
    code_lines.append("const photoGroups = [")
    code_lines.append("")

    for i, group in enumerate(photo_groups):
        code_lines.append(f"    {{")
        code_lines.append(f'        category: "official",')
        code_lines.append(f'        title: "{group["title"]}",')
        code_lines.append(f'        description: "",')
        code_lines.append(f'        date: "{group["date"]}",')
        code_lines.append(f'        cols: {group["cols"]},')
        code_lines.append(f'        images: [')

        for j, img in enumerate(group['images']):
            code_lines.append(f'            {{')
            code_lines.append(f'                src: "{img["src"]}",')
            code_lines.append(f'                title: "{img["title"]}",')
            code_lines.append(f'                description: ""')
            code_lines.append(f'            }}{"," if j < len(group["images"]) - 1 else ""}')

        code_lines.append(f'        ]')
        code_lines.append(f'    }}{"," if i < len(photo_groups) - 1 else ""}')
        code_lines.append("")

    code_lines.append("];")

    code = "\n".join(code_lines)

    # 保存
    output_file = os.path.join(os.path.dirname(__file__), "generated_groups.js")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(code)

    print(f"代码已保存: {output_file}")
    total_photos = sum(len(g['images']) for g in photo_groups)
    print(f"共 {len(photo_groups)} 个组, {total_photos} 张照片")

if __name__ == "__main__":
    process_images()
