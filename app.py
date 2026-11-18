from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

from ledger import get_summary, get_transactions, process_command

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/style.css")
def styles():
    return send_from_directory(BASE_DIR, "style.css")


@app.route("/script.js")
def scripts():
    return send_from_directory(BASE_DIR, "script.js")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "online",
        "application": "VoiceKhata"
    })


@app.route("/api/ledger")
def get_ledger():
    return jsonify({
        **get_summary(),
        "transactions": get_transactions()
    })


@app.route("/api/command", methods=["POST"])
def command():
    try:
        data = request.get_json(silent=True) or {}

        user_command = str(
            data.get("command", "")
        ).strip()

        language_code = str(
            data.get("language", "en-IN")
        ).strip()

        if not user_command:
            return jsonify({
                "error": "Please enter a command."
            }), 400

        if language_code not in [
            "en-IN", "kn-IN", "hi-IN"
        ]:
            language_code = "en-IN"

        reply = process_command(
            user_command,
            language_code=language_code
        )

        return jsonify({
            "reply": reply,
            **get_summary()
        })

    except Exception:
        app.logger.exception(
            "Command processing failed"
        )

        return jsonify({
            "error": "Command processing failed. Please try again."
        }), 500


if __name__ == "__main__":
    print("Starting VoiceKhata dashboard at http://localhost:5000")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )