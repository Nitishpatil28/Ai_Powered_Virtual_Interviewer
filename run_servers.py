#!/usr/bin/env python3
"""
Script to run both Flask app and WebSocket server simultaneously
"""

import subprocess
import sys
import time
import threading
import os


def run_flask_app():
    """Run the Flask application on port 5000"""
    print("Starting Flask app on port 5000...")
    try:
        subprocess.run([
            sys.executable, "app.py"
        ], cwd=os.getcwd())
    except KeyboardInterrupt:
        print("Flask app stopped")
    except Exception as e:
        print(f"Error running Flask app: {e}")


def run_websocket_server():
    """Run the WebSocket server on port 5001"""
    print("Starting WebSocket server on port 5001...")
    try:
        subprocess.run([
            sys.executable, "websocket_server.py"
        ], cwd=os.getcwd())
    except KeyboardInterrupt:
        print("WebSocket server stopped")
    except Exception as e:
        print(f"Error running WebSocket server: {e}")


def main():
    """Run both servers simultaneously"""
    print("=" * 60)
    print("AI-Powered Virtual Interviewer - Dual Server Mode")
    print("=" * 60)
    print("Starting both Flask app (port 5000) and WebSocket server (port 5001)")
    print("Press Ctrl+C to stop both servers")
    print("=" * 60)

    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()

    # Give Flask app a moment to start
    time.sleep(2)

    # Start WebSocket server in a separate thread
    websocket_thread = threading.Thread(target=run_websocket_server, daemon=True)
    websocket_thread.start()

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("Shutting down servers...")
        print("Both servers stopped successfully!")
        print("=" * 60)
        sys.exit(0)


if __name__ == "__main__":
    main()
