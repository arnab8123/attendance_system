# app.py
import os
import csv
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allow cross-origin requests (useful if front-end is served separately)

# Directory where CSV files will be stored
CSV_DIR = os.path.join(os.getcwd(), "records")
os.makedirs(CSV_DIR, exist_ok=True)

# Helper: convert numeric academic year "1" -> "1st", etc.
ORDINAL = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}

def sanitize_stream(stream: str) -> str:
    # keep alphanumerics and underscores, uppercase
    s = re.sub(r'[^A-Za-z0-9_]', '', stream.replace(' ', '_'))
    return s.upper() if s else "OTHER"

def session_filename_piece(session: str) -> str:
    """
    Convert "2023-2026" -> "2023-26" (i.e. end year last two digits)
    If format unexpected, return session with hyphen replaced to underscore-safe string.
    """
    parts = session.split('-')
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        start = parts[0]
        end = parts[1]
        end_short = end[-2:]
        return f"{start}-{end_short}"
    # fallback: sanitize
    return re.sub(r'[^0-9\-]', '', session)

def make_filename(stream: str, year: str, session: str) -> str:
    s = sanitize_stream(stream)
    ordinal = ORDINAL.get(year, f"{year}th")
    sess_piece = session_filename_piece(session)
    filename = f"{s}_{ordinal}_{sess_piece}.csv"
    # make sure filename safe
    filename = re.sub(r'[^A-Za-z0-9_\-\.]', '', filename)
    return filename

@app.route("/api/profile", methods=["POST"])
def save_profile():
    """
    Expects JSON payload with keys:
    name, email, roll, birthdate, registration, stream, session, year, course
    """
    data = request.get_json() or {}

    # Basic validation
    required = ["name", "email", "roll", "birthdate", "registration", "stream", "session", "year", "course"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"status": "error", "message": f"Missing fields: {', '.join(missing)}"}), 400

    # Validate session format (e.g., "2023-2026")
    session_val = data.get("session")
    # Optional: ensure end > start
    try:
        s_parts = session_val.split('-')
        if len(s_parts) == 2:
            s0 = int(s_parts[0])
            s1 = int(s_parts[1])
            if s1 <= s0:
                return jsonify({"status": "error", "message": "Session end year must be after start year."}), 400
    except Exception:
        # ignore strict check, allow malformed but sanitized filename
        pass

    filename = make_filename(data["stream"], str(data["year"]), session_val)
    path = os.path.join(CSV_DIR, filename)

    # Header / columns we will store
    headers = ["timestamp", "name", "email", "roll", "birthdate", "registration", "stream", "session", "year", "course"]

    # Prepare row
    row = [
        datetime.utcnow().isoformat(),
        data.get("name"),
        data.get("email"),
        data.get("roll"),
        data.get("birthdate"),
        data.get("registration"),
        data.get("stream"),
        data.get("session"),
        data.get("year"),
        data.get("course"),
    ]

    write_header = not os.path.exists(path)
    try:
        with open(path, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            if write_header:
                writer.writerow(headers)
            writer.writerow(row)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Could not write CSV: {e}"}), 500

    return jsonify({"status": "success", "file": filename})

# Optional: list or download CSVs (simple)
@app.route("/records/<path:filename>", methods=["GET"])
def download_record(filename):
    # Security note: this is a simple helper for dev; in production add auth and sanitize paths
    return send_from_directory(CSV_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
