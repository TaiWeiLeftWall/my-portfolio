#!/usr/bin/env python3
"""简单的图片上传服务器"""

import http.server
import socketserver
import os
import cgi
import json
from urllib.parse import urlparse, parse_qs
from PIL import Image
from PIL.ExifTags import TAGS
import io
from datetime import datetime

PORT = 8080
UPLOAD_DIR = os.path.join("images", "images")


def get_exif_date(image_data):
    """从图片EXIF数据中提取日期"""
    try:
        img = Image.open(io.BytesIO(image_data))
        exif = img._getexif()
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) == 'DateTimeOriginal':
                    # Format: "YYYY:MM:DD HH:MM:SS"
                    return value.split(' ')[0].replace(':', '-')[:7]  # "YYYY-MM"
    except:
        pass
    return None

class UploadHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/upload':
            content_type = self.headers.get('Content-Type')
            if 'multipart/form-data' in content_type:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': content_type,
                    }
                )

                files = form.list
                result = []

                for item in files:
                    if item.filename:
                        filename = os.path.basename(item.filename)

                        # 读取文件数据用于EXIF提取
                        file_data = item.file.read()
                        item.file.seek(0)

                        # 获取日期（优先EXIF，其次当前日期）
                        exif_date = get_exif_date(file_data)
                        date_folder = exif_date or datetime.now().strftime('%Y-%m')

                        # 创建日期子目录
                        date_dir = os.path.join(UPLOAD_DIR, date_folder)
                        os.makedirs(date_dir, exist_ok=True)

                        filepath = os.path.join(date_dir, filename)

                        # 处理重名文件
                        if os.path.exists(filepath):
                            name, ext = os.path.splitext(filename)
                            counter = 1
                            while os.path.exists(filepath):
                                filename = f"{name}_{counter}{ext}"
                                filepath = os.path.join(date_dir, filename)
                                counter += 1

                        with open(filepath, 'wb') as f:
                            f.write(file_data)

                        result.append({
                            'success': True,
                            'filename': filename,
                            'path': f'images/{date_folder}/{filename}'
                        })

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
                return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        # 返回上传页面
        if self.path == '/' or self.path == '/upload':
            self.path = '/upload-tool.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

if __name__ == '__main__':
    # 确保 images/images 目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    with socketserver.TCPServer(("", PORT), UploadHandler) as httpd:
        print(f"上传服务器运行在 http://localhost:{PORT}")
        print(f"图片将上传到: {os.path.abspath(UPLOAD_DIR)}")
        httpd.serve_forever()
