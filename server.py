import http.server
import socketserver
import os
import json
import urllib.request
import urllib.error
import sys

# Configuration
PORT = 8001
API_BASE = "https://api.tensorlake.ai/v1/namespaces/default"
API_KEY = os.environ.get("TENSORLAKE_API_KEY")

if not API_KEY:
    print("Error: TENSORLAKE_API_KEY environment variable not set.")
    # Try to load from .env manually if not in env
    try:
        with open(".env") as f:
            for line in f:
                if line.startswith("TENSORLAKE_API_KEY="):
                    API_KEY = line.strip().split("=", 1)[1]
                    break
    except Exception:
        pass

if not API_KEY:
    print("CRITICAL: Could not find API Key.")
    sys.exit(1)

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/proxy/"):
            self.handle_proxy("GET")
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/proxy/"):
            self.handle_proxy("POST")
        else:
            self.send_error(404, "Not Found")

    def handle_proxy(self, method):
        # Strip /api/proxy to get the target path (e.g. /applications/...)
        target_path = self.path[len("/api/proxy"):]
        target_url = f"{API_BASE}{target_path}"
        
        print(f"Proxying {method} to {target_url}")

        # Read body if POST
        data = None
        if method == "POST":
            content_length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(content_length)

        # Prepare request
        req = urllib.request.Request(target_url, data=data, method=method)
        
        # Use key from header if provided, otherwise fallback to server's key
        user_key = self.headers.get('X-TensorLake-API-Key')
        final_key = user_key if user_key else API_KEY
        
        req.add_header("Authorization", f"Bearer {final_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                # Forward headers
                for k, v in response.getheaders():
                    # Skip hop-by-hop headers
                    if k.lower() not in ['transfer-encoding', 'connection', 'keep-alive']:
                        self.send_header(k, v)
                self.send_header("Access-Control-Allow-Origin", "*") # Allow local
                self.end_headers()
                self.wfile.write(response.read())

        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            print(f"Proxy Error: {e}")
            self.send_error(500, str(e))

print(f"Starting proxy server at http://localhost:{PORT}")
print(f"Proxying requests to {API_BASE}")

with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
