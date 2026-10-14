"""
Local Demo HTTP Server for WebMCP Reference Application.
Runs a lightweight python http.server to host demo_app.html.
"""

import http.server
import os
import socketserver
import sys

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        # Quiet logger
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

def serve(port: int = PORT):
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"🚀 WebMCP Demo App Server running at http://localhost:{port}/demo_app.html")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    serve()
