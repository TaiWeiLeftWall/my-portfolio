#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BiliBili Video Info Proxy
Run: python video_proxy.py
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse

PORT = 8765

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            bvid = params.get('bvid', [None])[0]

            if not bvid:
                self.send_error(400, 'Missing bvid')
                return

            url = 'https://api.bilibili.com/x/web-interface/view?bvid=' + bvid
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Referer': 'https://www.bilibili.com'
                })
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())

                    if data['code'] == 0:
                        result = {
                            'title': data['data']['title'],
                            'description': data['data']['desc'],
                            'tname': data['data']['tname'],
                            'pic': data['data']['pic'],
                            'duration': data['data']['duration']
                        }
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode('utf-8'))
                    else:
                        self.send_error(502, 'API error')
            except Exception as e:
                self.send_error(502, str(e))
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            msg = '<html><body><h1>BiliBili Proxy</h1><p>API: /api?bvid=BV号</p></body></html>'
            self.wfile.write(msg.encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('', PORT), ProxyHandler)
    print('Proxy running on http://localhost:' + str(PORT))
    server.serve_forever()
