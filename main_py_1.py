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
# ROTAS PÚBLICAS
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
        return jsonify({"success": False, "message": "Usuário não encontrado ou inativo"})

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
        return jsonify({"success": False, "message": "Licença inválida ou já usada"})

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
        return jsonify({"success": False, "message": "Usuário já existe"})

    conn.close()
    return jsonify({"success": True, "message": "Usuário registrado com sucesso"})

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
        return jsonify({"success": False, "message": "Licença inválida"})

    return jsonify({
        "success": True,
        "info": {"expiry_date": lic["expiry_date"]}
    })

# ===============================
# ROTAS ADMIN (KEYAUTH STYLE)
# ===============================

def check_admin():
    return request.headers.get("X-ADMIN-KEY") == ADMIN_KEY

# -------- CREATE LICENSE --------
@app.route("/admin/create_license", methods=["POST"])
def create_license():
    if not check_admin():
        return jsonify({"error": "Acesso não autorizado"}), 401

    days = int(request.json.get("days", 30))
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

# -------- LIST USERS --------
@app.route("/admin/list_users", methods=["GET"])
def list_users():
    if not check_admin():
        return jsonify({"error": "Acesso não autorizado"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, license_key, expiry_date FROM users")
    users = [dict(u) for u in cur.fetchall()]
    conn.close()

    return jsonify({"success": True, "users": users})

# -------- REMOVE USER --------
@app.route("/admin/remove_user", methods=["POST"])
def remove_user():
    if not check_admin():
        return jsonify({"error": "Acesso não autorizado"}), 401

    username = request.json.get("username")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username=?", (username,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        return jsonify({"success": False, "message": "Usuário não encontrado"})

    return jsonify({"success": True, "message": "Usuário removido"})

# -------- UPDATE EXPIRY --------
@app.route("/admin/update_expiry", methods=["POST"])
def update_expiry():
    if not check_admin():
        return jsonify({"error": "Acesso não autorizado"}), 401

    username = request.json.get("username")
    days = int(request.json.get("days", 30))
    new_expiry = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET expiry_date=? WHERE username=?",
        (new_expiry, username)
    )
    updated = cur.rowcount
    conn.commit()
    conn.close()

    if updated == 0:
        return jsonify({"success": False, "message": "Usuário não encontrado"})

    return jsonify({
        "success": True,
        "message": "Data atualizada",
        "expiry_date": new_expiry
    })

# ===============================
# START (RENDER)
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
