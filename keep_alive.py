"""
Flask health check server to keep bot alive on Render
Runs in a separate thread alongside the Discord bot
"""

from flask import Flask
from threading import Thread
import os

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
    """Run Flask server"""
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    """Start Flask server in background thread"""
    server_thread = Thread(target=run, daemon=True)
    server_thread.start()
    print(f"✅ Health check server started on port {os.getenv('PORT', 8080)}")