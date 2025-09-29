"""
Flask health check server to keep bot alive on Render
Runs in a separate thread alongside the Discord bot
"""

from flask import Flask
from threading import Thread
import os

try:
    # Prefer a production WSGI server when available
    from waitress import serve as wsgi_serve
except Exception:
    wsgi_serve = None

try:
    # Guaranteed stdlib WSGI server (not Flask dev server)
    from wsgiref.simple_server import make_server as wsgi_make_server
except Exception:
    wsgi_make_server = None

app = Flask(__name__)

@app.route('/')
def home():
    return {
        "status": "online",
        "service": "Discord Registration Bot",
        "message": "Bot is running successfully"
    }, 200

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

@app.route('/ping')
def ping():
    return {"message": "pong"}, 200

def run():
    """Run HTTP server (production WSGI if available)."""
    port = int(os.getenv('PORT', 8080))
    if wsgi_serve is not None:
        # Waitress is a production WSGI server, avoids Flask dev warning
        print("✅ Health server using Waitress WSGI")
        wsgi_serve(app, host='0.0.0.0', port=port)
    elif wsgi_make_server is not None:
        # Fallback to stdlib WSGI to avoid Flask dev server warning
        print("✅ Health server using wsgiref WSGI")
        httpd = wsgi_make_server('0.0.0.0', port, app)
        httpd.serve_forever()
    else:
        # Fallback to Flask's built-in server
        print("⚠️ Health server falling back to Flask dev server")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    """Start Flask server in background thread"""
    server_thread = Thread(target=run, daemon=True)
    server_thread.start()
    print(f"✅ Health check server started on port {os.getenv('PORT', 8080)}")