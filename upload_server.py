#!/usr/bin/env python3
"""简单的图片上传服务器"""

import http.server
import socketserver
import os
import cgi
import json
from urllib.parse import urlparse, parse_qs

PORT = 8080
UPLOAD_DIR = "images"

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
                        filepath = os.path.join(UPLOAD_DIR, filename)

                        # 处理重名文件
                        if os.path.exists(filepath):
                            name, ext = os.path.splitext(filename)
                            counter = 1
                            while os.path.exists(filepath):
                                filename = f"{name}_{counter}{ext}"
                                filepath = os.path.join(UPLOAD_DIR, filename)
                                counter += 1

                        with open(filepath, 'wb') as f:
                            f.write(item.file.read())

                        result.append({
                            'success': True,
                            'filename': filename,
                            'path': f'images/{filename}'
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
    # 确保 images 目录存在
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    with socketserver.TCPServer(("", PORT), UploadHandler) as httpd:
        print(f"上传服务器运行在 http://localhost:{PORT}")
        print(f"图片将上传到: {os.path.abspath(UPLOAD_DIR)}")
        httpd.serve_forever()
