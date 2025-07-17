from flask import Flask
from threading import Thread

app = Flask('app')

@app.route('/')
def main():
    return "I'm alive! Support bot is running."

@app.route('/status')
def status():
    return {
        "status": "running",
        "service": "telegram_support_bot",
        "version": "1.0.0"
    }

def run():
    app.run(host="0.0.0.0", port=8080, debug=False)

def keep_alive():
    server = Thread(target=run)
    server.daemon = True
    server.start()
    print("Flask server started on port 8080")