import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

# ===============================
# CONFIGURAÇÃO
# ===============================
DB_NAME = "database.db"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "COREAUTH_ADMIN_2024")

app = Flask(__name__)
CORS(app)

# ===============================
# DATABASE
# ===============================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT,
            license_key TEXT,
            expiry_date TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            expiry_date TEXT,
            used INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ===============================
# ROUTES
# ===============================

@app.route("/")
def home():
    return jsonify({"status": "CoreAuth API running"})


# -------- LOGIN --------
@app.route("/api/v1/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({"success": False, "message": "Invalid credentials"})

    return jsonify({
        "success": True,
        "user": {"username": username},
        "info": {"expiry_date": user["expiry_date"]}
    })


# -------- REGISTER --------
@app.route("/api/v1/register", methods=["POST"])
def register():
    data = request.json

    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    license_key = data.get("license_key")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM licenses WHERE license_key=? AND used=0",
        (license_key,)
    )
    lic = cur.fetchone()

    if not lic:
        conn.close()
        return jsonify({"success": False, "message": "Invalid or used license"})

    try:
        cur.execute(
            "INSERT INTO users (username, password, email, license_key, expiry_date) VALUES (?, ?, ?, ?, ?)",
            (username, password, email, license_key, lic["expiry_date"])
        )
        cur.execute(
            "UPDATE licenses SET used=1 WHERE license_key=?",
            (license_key,)
        )
        conn.commit()
    except:
        conn.close()
        return jsonify({"success": False, "message": "Username already exists"})

    conn.close()
    return jsonify({"success": True, "message": "Registered successfully"})


# -------- LICENSE CHECK --------
@app.route("/api/v1/license", methods=["POST"])
def license_check():
    data = request.json
    license_key = data.get("license_key")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM licenses WHERE license_key=?",
        (license_key,)
    )
    lic = cur.fetchone()
    conn.close()

    if not lic:
        return jsonify({"success": False, "message": "Invalid license"})

    return jsonify({
        "success": True,
        "info": {"expiry_date": lic["expiry_date"]}
    })


# -------- ADMIN: CREATE LICENSE --------
@app.route("/admin/create_license", methods=["POST"])
def create_license():
    if request.headers.get("X-ADMIN-KEY") != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    days = int(data.get("days", 30))

    expiry = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
    license_key = f"LIC-{os.urandom(6).hex().upper()}"

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO licenses (license_key, expiry_date) VALUES (?, ?)",
        (license_key, expiry)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "license_key": license_key,
        "expiry_date": expiry
    })


# ===============================
# START (RENDER COMPATÍVEL)
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
