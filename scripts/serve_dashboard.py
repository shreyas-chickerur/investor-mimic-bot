#!/usr/bin/env python3
"""
Simple HTTP server to view strategy performance dashboard

Usage:
    python3 scripts/serve_dashboard.py
    
Then open: http://localhost:8080/strategy_performance.html
"""
import http.server
import socketserver
import os
from pathlib import Path

PORT = 8080

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Set the directory to serve from
        super().__init__(*args, directory=str(Path(__file__).parent.parent), **kwargs)
    
    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        print("=" * 60)
        print(f"📊 Strategy Performance Dashboard Server")
        print("=" * 60)
        print(f"Server running at: http://localhost:{PORT}")
        print(f"Dashboard URL: http://localhost:{PORT}/dashboard/strategy_performance.html")
        print("")
        print("Press Ctrl+C to stop the server")
        print("=" * 60)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✅ Server stopped")
