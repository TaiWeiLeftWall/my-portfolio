#!/usr/bin/env python3
"""
图片导入工具
- 压缩大于10MB的图片到10MB
- 按分类（年份+事件）存储到 images 目录
- 生成 data.js 代码
"""

import os
import sys
from PIL import Image
import re

# 源文件夹
SOURCE_DIR = r"G:\1A新闻片作品汇总\1A新闻片作品汇总\公务摄影"
# 目标目录
TARGET_BASE = r"C:\Users\1222\my-website\images\官方"
# 最大文件大小 (10MB)
MAX_SIZE = 10 * 1024 * 1024
# 最大尺寸（宽或高）
MAX_DIMENSION = 3000
# 压缩质量
QUALITY = 85

def get_file_size_mb(filepath):
    """获取文件大小(MB)"""
    return os.path.getsize(filepath) / (1024 * 1024)

def compress_image(src_path, dst_path, max_size_mb=10, max_dimension=3000):
    """压缩图片到指定大小和尺寸"""
    try:
        img = Image.open(src_path)

        # 检查并调整尺寸
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            # 按比例缩放
            ratio = min(max_dimension / width, max_dimension / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 如果格式是 RGBA，转换为 RGB
        if img.mode == 'RGBA':
            img = img.convert('RGB')

        # 逐步降低质量直到文件大小合适
        quality = 95
        img.save(dst_path, 'JPEG', quality=quality, optimize=True)

        # 如果文件还是太大，继续降低质量
        while os.path.getsize(dst_path) > max_size_mb * 1024 * 1024 and quality > 50:
            quality -= 5
            img.save(dst_path, 'JPEG', quality=quality, optimize=True)

        return True
    except Exception as e:
        print(f"  压缩失败: {src_path} - {e}")
        return False

def process_images():
    """处理所有图片"""
    # 创建目标目录
    os.makedirs(TARGET_BASE, exist_ok=True)

    # 存储生成的数据
    photo_entries = []

    # 遍历年份目录
    years = ['2021', '2022', '2023', '2024']

    for year in years:
        year_dir = os.path.join(SOURCE_DIR, year)
        if not os.path.exists(year_dir):
            continue

        print(f"\n=== Processing {year} ===")

        # 获取该年份下所有事件目录
        try:
            events = [d for d in os.listdir(year_dir) if os.path.isdir(os.path.join(year_dir, d))]
        except PermissionError:
            print(f"  Permission denied, skipping {year}")
            continue
        events.sort()

        for event in events:
            event_dir = os.path.join(year_dir, event)
            print(f"\nProcessing: {event}")

            # 创建事件目录
            # 清理事件名中的非法字符
            safe_event = re.sub(r'[<>:"/\\|?*]', '_', event)
            event_category = f"{year}-{safe_event}"
            target_dir = os.path.join(TARGET_BASE, event_category)
            os.makedirs(target_dir, exist_ok=True)

            # 获取该事件下所有图片（排除 Mac 系统文件）
            images = []
            try:
                for f in os.listdir(event_dir):
                    # 跳过 Mac 临时文件和目录
                    if f.startswith('._') or f.startswith('.@') or f.startswith('__'):
                        continue
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        images.append(f)
            except PermissionError:
                print(f"  Permission denied, skipping")
                continue

            if not images:
                print(f"  No images, skipping")
                continue

            # 清理事件名作为标题
            title = event

            for img_name in images:
                src_path = os.path.join(event_dir, img_name)

                # 生成目标文件名
                dst_name = f"{safe_event}_{img_name}"
                dst_path = os.path.join(target_dir, dst_name)

                # 检查是否需要压缩
                try:
                    file_size = get_file_size_mb(src_path)
                except:
                    print(f"  Cannot read: {img_name}, skipping")
                    continue

                needs_compress = file_size > 10

                if needs_compress:
                    print(f"  Compressing: {img_name} ({file_size:.1f}MB) -> ", end="")
                    if compress_image(src_path, dst_path):
                        new_size = get_file_size_mb(dst_path)
                        print(f"{new_size:.1f}MB")
                    else:
                        print("Failed, skipping")
                        continue
                else:
                    # 直接复制或调整尺寸
                    try:
                        img = Image.open(src_path)
                        width, height = img.size
                        # 如果尺寸太大也需要压缩
                        if width > MAX_DIMENSION or height > MAX_DIMENSION:
                            print(f"  Resizing: {img_name}")
                            compress_image(src_path, dst_path)
                        else:
                            img.save(dst_path, quality=95, optimize=True)
                            print(f"  Copying: {img_name}")
                    except Exception as e:
                        print(f"  Copy failed: {img_name} - {e}")
                        continue

                # 生成相对路径
                rel_path = f"images/官方/{event_category}/{dst_name}"

                # 生成日期格式 YYYY-MM
                month_match = re.search(r'(\d{4})(\d{2})', event)
                if month_match:
                    date_str = f"{month_match.group(1)}-{month_match.group(2)}"
                else:
                    date_str = f"{year}-01"

                # 生成条目
                # 检测图片方向
                try:
                    img = Image.open(dst_path)
                    width, height = img.size
                    orientation = "vertical" if height > width * 1.2 else "horizontal"
                except:
                    orientation = "horizontal"

                entry = f"""    {{
        category: "official",
        orientation: "{orientation}",
        title: "{title}",
        description: "",
        date: "{date_str}",
        src: "{rel_path}"
    }}"""
                photo_entries.append(entry)

    # 生成 data.js 代码
    print("\n\n=== Generated Code ===\n")
    code = "const photos = [\n" + ",\n".join(photo_entries) + "\n];"

    # 保存到文件
    output_file = os.path.join(os.path.dirname(__file__), "generated_photos.js")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"Code saved to: {output_file}")
    except Exception as e:
        print(f"Failed to save code: {e}")
        # Print to stdout
        print(code)

    print(f"\nTotal photos processed: {len(photo_entries)}")

if __name__ == "__main__":
    process_images()
