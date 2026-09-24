"""
Spin & Menang - Palekko Chicken / Gacoan DNA / Grass Jelly Drink
-----------------------------------------------------------------
Backend logika untuk web spin promo dengan database permanen:
- Mendukung PostgreSQL (production/Render) dan SQLite (development lokal)
- Otomatis deteksi backend dari env var DATABASE_URL
- Data kredit & hitungan TIDAK AKAN HILANG saat server restart/sleep
- Autentikasi PIN 6 digit untuk Admin/Kasir (/admin & /api/admin/*)
- Proteksi Brute-force dengan lockout otomatis jika 5x salah PIN
- Token sesi khusus layar pelanggan (Client Session Token)
- Proteksi Anti-Cheat: Threading Lock (Race condition) & Cooldown Spin
- Logika pasti untung:
  * 2K: Setiap kelipatan 10 HANYA Grass Jelly Drink
  * 5K: Setiap kelipatan 15 GRAND PRIZE Palekko Chicken (kelipatan 5 & 10 hadiah reguler)
"""

import json
import os
import random
import threading
import time
import uuid
from datetime import date
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dracin-spin-super-secret-key-2026")

# ===== DATABASE CONFIGURATION =====
# Jika DATABASE_URL di-set (Render production) → pakai PostgreSQL yang persisten
# Jika tidak → pakai SQLite untuk development lokal
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    # Render memakai "postgres://" tapi psycopg2 butuh "postgresql://"
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dracin.db")

# PIN Admin / Kasir (Default: 123456, bisa diatur lewat ENV)
ADMIN_PIN = os.environ.get("ADMIN_PIN", "123456")

# Anti-brute force untuk login PIN admin
_login_attempts = {"count": 0, "locked_until": 0}

# Threading Lock untuk atomic credit deduction & spin race condition protection
_spin_lock = threading.Lock()

# Cooldown per token sesi pelanggan (mencegah spam / concurrent spin request)
_client_cooldowns = {}

# Definisi hadiah. daily_limit=None berarti tidak dibatasi (dipakai untuk "zonk").
PRIZES = {
    "Palekko Chicken": {"name": "Palekko Chicken", "daily_limit": 15},
    "Gacoan DNA": {"name": "Gacoan DNA", "daily_limit": 15},
    "Grass Jelly Drink": {"name": "Grass Jelly Drink", "daily_limit": 20},
}

# 10 slot roda piring saji
SEGMENTS = [
    {"prize_key": None},                 # 0: Zonk
    {"prize_key": "Palekko Chicken"},     # 1: Prize
    {"prize_key": None},                 # 2: Zonk
    {"prize_key": None},                 # 3: Zonk
    {"prize_key": "Gacoan DNA"},          # 4: Prize
    {"prize_key": None},                 # 5: Zonk
    {"prize_key": None},                 # 6: Zonk
    {"prize_key": "Grass Jelly Drink"},   # 7: Prize
    {"prize_key": None},                 # 8: Zonk
    {"prize_key": None},                 # 9: Zonk
]


# ===== DATABASE HELPERS =====

def get_db():
    """Mengembalikan koneksi database (PostgreSQL atau SQLite)."""
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn


def _fetchone(conn, sql, params=()):
    """Fetch satu baris — kompatibel dengan kedua backend."""
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur.fetchone()
    return conn.execute(sql, params).fetchone()


def _fetchall(conn, sql, params=()):
    """Fetch semua baris — kompatibel dengan kedua backend."""
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur.fetchall()
    return conn.execute(sql, params).fetchall()


def _update(conn, sql, params=()):
    """UPDATE/INSERT query — kompatibel dengan kedua backend."""
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
    else:
        conn.execute(sql, params)


def _upsert_setting(conn, key, value, ignore=False):
    """INSERT OR IGNORE / INSERT OR REPLACE yang kompatibel dengan kedua backend."""
    if USE_POSTGRES:
        cur = conn.cursor()
        if ignore:
            cur.execute(
                "INSERT INTO store_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
                (key, value)
            )
        else:
            cur.execute(
                "INSERT INTO store_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value)
            )
    else:
        if ignore:
            conn.execute("INSERT OR IGNORE INTO store_settings (key, value) VALUES (?, ?)", (key, value))
        else:
            conn.execute("INSERT OR REPLACE INTO store_settings (key, value) VALUES (?, ?)", (key, value))


def _insert_history(conn, spin_type, is_win, prize_key, prize_name):
    """Insert spin history — kompatibel dengan kedua backend."""
    if USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO spin_history (spin_type, is_win, prize_key, prize_name) VALUES (%s, %s, %s, %s)",
            (spin_type, 1 if is_win else 0, prize_key, prize_name)
        )
    else:
        conn.execute(
            "INSERT INTO spin_history (spin_type, is_win, prize_key, prize_name) VALUES (?, ?, ?, ?)",
            (spin_type, 1 if is_win else 0, prize_key, prize_name)
        )


def init_db():
    """Inisialisasi tabel dan nilai default database."""
    conn = get_db()
    try:
        if USE_POSTGRES:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS store_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spin_history (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    spin_type TEXT NOT NULL,
                    is_win INTEGER NOT NULL,
                    prize_key TEXT,
                    prize_name TEXT NOT NULL
                )
            """)
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS store_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spin_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    spin_type TEXT NOT NULL,
                    is_win INTEGER NOT NULL,
                    prize_key TEXT,
                    prize_name TEXT NOT NULL
                )
            """)

        defaults = {
            "credit_2k":     "0",
            "credit_5k":     "0",
            "spin_count_2k": "0",
            "spin_count_5k": "0",
            "stock_date":    date.today().isoformat(),
            "stock_given":   json.dumps({k: 0 for k in PRIZES}),
        }
        for k, v in defaults.items():
            _upsert_setting(conn, k, v, ignore=True)
        conn.commit()
    finally:
        conn.close()


_db_initialized = False

def ensure_db_init():
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
        except Exception as e:
            app.logger.warning(f"Database init warning: {e}")

@app.before_request
def auto_init_db():
    ensure_db_init()


def _reset_stock_if_new_day(conn):
    today = date.today().isoformat()
    row = _fetchone(conn, "SELECT value FROM store_settings WHERE key = 'stock_date'")
    stored_date = row["value"] if row else ""
    if stored_date != today:
        _upsert_setting(conn, "stock_date", today)
        _upsert_setting(conn, "stock_given", json.dumps({k: 0 for k in PRIZES}))


def _stock_left(conn, prize_key):
    _reset_stock_if_new_day(conn)
    limit = PRIZES[prize_key]["daily_limit"]
    if limit is None:
        return None
    row = _fetchone(conn, "SELECT value FROM store_settings WHERE key = 'stock_given'")
    given = json.loads(row["value"]) if row else {}
    return max(0, limit - given.get(prize_key, 0))


def _public_state():
    conn = get_db()
    try:
        _reset_stock_if_new_day(conn)
        rows = _fetchall(conn, "SELECT key, value FROM store_settings")
        settings = {r["key"]: r["value"] for r in rows}
        c2k  = int(settings.get("credit_2k",     0))
        c5k  = int(settings.get("credit_5k",     0))
        sc2k = int(settings.get("spin_count_2k", 0))
        sc5k = int(settings.get("spin_count_5k", 0))

        # 10 riwayat putaran terakhir
        history_rows = _fetchall(
            conn,
            "SELECT is_win, prize_key, prize_name FROM spin_history ORDER BY id DESC LIMIT 10"
        )
        history = [
            {"is_win": bool(r["is_win"]), "prize_key": r["prize_key"], "prize_name": r["prize_name"]}
            for r in history_rows
        ]

        state = {
            "credit_2k": c2k,
            "credit_5k": c5k,
            "history":   history,
            "prizes":    {k: {"name": v["name"]} for k, v in PRIZES.items()},
        }

        # Info progress rahasia hanya untuk admin/kasir yang sedang login
        if session.get("is_admin"):
            state["admin_stats"] = {
                "progress_2k":    f"{sc2k % 10} / 10",
                "progress_5k":    f"{sc5k % 15} / 15",
                "total_spins_2k": sc2k,
                "total_spins_5k": sc5k,
            }
        conn.commit()
        return state
    finally:
        conn.close()


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Akses ditolak. Silakan login sebagai admin/kasir."}), 401
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated_function


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ===== USER ROUTES =====

@app.route("/")
def index():
    if "client_token" not in session:
        session["client_token"] = uuid.uuid4().hex
    return render_template("user/index.html", client_token=session["client_token"])


@app.route("/api/state")
def api_state():
    return jsonify(_public_state())


@app.route("/api/spin", methods=["POST"])
def api_spin():
    # 1. Validasi Token Sesi Pelanggan
    client_token = session.get("client_token")
    req_token = request.headers.get("X-Client-Token") or (request.get_json(silent=True) or {}).get("client_token")
    if not client_token or req_token != client_token:
        return jsonify({"error": "Akses ditolak: sesi tidak valid atau kadaluarsa."}), 403

    # 2. Validasi Tipe Spin
    data = request.get_json(silent=True) or {}
    spin_type = data.get("type")
    if spin_type not in ("2k", "5k"):
        return jsonify({"error": "Tipe putaran tidak valid."}), 400

    # 3. Anti-Spam / Cooldown Check (Pencegah double click / request flooding)
    now = time.time()
    last_spin = _client_cooldowns.get(client_token, 0)
    if now - last_spin < 4.2:
        return jsonify({"error": "Piring masih berputar. Harap tunggu hingga berhenti."}), 429

    # 4. Atomic Execution dengan Threading Lock & Transaksi DB
    with _spin_lock:
        if time.time() - _client_cooldowns.get(client_token, 0) < 4.2:
            return jsonify({"error": "Piring sedang berputar."}), 429

        conn = get_db()
        try:
            _reset_stock_if_new_day(conn)
            credit_key = f"credit_{spin_type}"
            count_key  = f"spin_count_{spin_type}"

            cur_credit = int(_fetchone(conn, "SELECT value FROM store_settings WHERE key = ?", (credit_key,))["value"])
            if cur_credit < 1:
                return jsonify({"error": f"Kredit {spin_type.upper()} tidak cukup."}), 402

            cur_count = int(_fetchone(conn, "SELECT value FROM store_settings WHERE key = ?", (count_key,))["value"]) + 1

            # Potong kredit & update hitungan putaran permanen di DB
            _update(conn, "UPDATE store_settings SET value = ? WHERE key = ?", (str(cur_credit - 1), credit_key))
            _update(conn, "UPDATE store_settings SET value = ? WHERE key = ?", (str(cur_count), count_key))

            _client_cooldowns[client_token] = time.time()

            # ===== ATURAN HADIAH & SIKLUS KEUNTUNGAN TOKO =====
            if spin_type == "2k":
                # 2K: Sebanyak apapun hanya Grass Jelly Drink di putaran ke-10
                is_winning_turn   = (cur_count % 10 == 0)
                target_prize_pool = ["Grass Jelly Drink"]
            else:
                # 5K: Menang setiap kelipatan 5
                is_winning_turn = (cur_count % 5 == 0)
                if cur_count % 15 == 0:
                    # Putaran ke-15: Grand Prize Palekko Chicken!
                    target_prize_pool = ["Palekko Chicken"]
                else:
                    # Putaran ke-5 dan ke-10: Hadiah reguler
                    target_prize_pool = ["Grass Jelly Drink", "Gacoan DNA"]

            zonk_indices = [i for i, seg in enumerate(SEGMENTS) if seg["prize_key"] is None]

            available_prize_keys = [
                pk for pk in target_prize_pool
                if _stock_left(conn, pk) > 0
            ]

            if is_winning_turn and available_prize_keys:
                chosen_prize_key = random.choice(available_prize_keys)
                matching_indices = [i for i, seg in enumerate(SEGMENTS) if seg["prize_key"] == chosen_prize_key]
                chosen_index     = random.choice(matching_indices)

                # Update stok terpakai
                row_given = _fetchone(conn, "SELECT value FROM store_settings WHERE key = 'stock_given'")
                given = json.loads(row_given["value"]) if row_given else {}
                given[chosen_prize_key] = given.get(chosen_prize_key, 0) + 1
                _update(conn, "UPDATE store_settings SET value = ? WHERE key = 'stock_given'", (json.dumps(given),))

                result = {
                    "is_win":     True,
                    "prize_key":  chosen_prize_key,
                    "prize_name": PRIZES[chosen_prize_key]["name"],
                }
            else:
                # 100% ZONK
                chosen_index = random.choice(zonk_indices)
                result = {"is_win": False, "prize_key": None, "prize_name": "Zonk"}

            _insert_history(conn, spin_type, result["is_win"], result["prize_key"], result["prize_name"])
            conn.commit()
        finally:
            conn.close()

        return jsonify({
            "segment_index": chosen_index,
            **result,
            "state": _public_state(),
        })


# ===== ADMIN ROUTES & AUTH =====

@app.route("/admin/login")
def admin_login_page():
    if session.get("is_admin"):
        return redirect("/admin")
    return render_template("admin/login.html")


@app.route("/admin")
@admin_required
def admin_page():
    return render_template("admin/admin.html")


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    now = time.time()
    if _login_attempts["locked_until"] > now:
        remaining = int(_login_attempts["locked_until"] - now)
        return jsonify({"error": f"Akses terkunci sementara ({remaining} detik) karena salah PIN."}), 429

    data = request.get_json(silent=True) or {}
    pin = str(data.get("pin", "")).strip()

    if pin == ADMIN_PIN:
        _login_attempts["count"] = 0
        _login_attempts["locked_until"] = 0
        session["is_admin"] = True
        return jsonify({"status": "success", "message": "Login kasir berhasil."})
    else:
        _login_attempts["count"] += 1
        if _login_attempts["count"] >= 5:
            _login_attempts["locked_until"] = now + 60
            _login_attempts["count"] = 0
            return jsonify({"error": "PIN salah 5 kali! Akses terkunci selama 60 detik."}), 429
        sisa = 5 - _login_attempts["count"]
        return jsonify({"error": f"PIN salah. Sisa kesempatan: {sisa}x"}), 401


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.pop("is_admin", None)
    return jsonify({"status": "success", "message": "Kasir berhasil logout."})


@app.route("/api/admin/add", methods=["POST"])
@admin_required
def admin_add():
    data = request.get_json(silent=True) or {}
    spin_type = data.get("type", "5k")
    if spin_type not in ("2k", "5k"):
        return jsonify({"error": "Tipe kredit tidak valid."}), 400

    key = f"credit_{spin_type}"
    with _spin_lock:
        conn = get_db()
        try:
            cur_credit = int(_fetchone(conn, "SELECT value FROM store_settings WHERE key = ?", (key,))["value"])
            _update(conn, "UPDATE store_settings SET value = ? WHERE key = ?", (str(cur_credit + 1), key))
            conn.commit()
        finally:
            conn.close()

    return jsonify({"status": "success", "state": _public_state()})


@app.route("/api/health")
def api_health():
    db_ok = False
    err = None
    try:
        conn = get_db()
        _fetchone(conn, "SELECT 1")
        conn.close()
        db_ok = True
    except Exception as e:
        err = str(e)
    return jsonify({
        "status": "ok" if db_ok else "db_error",
        "use_postgres": USE_POSTGRES,
        "database_url_configured": bool(DATABASE_URL),
        "db_ok": db_ok,
        "error": err
    })


@app.errorhandler(500)
def handle_500(e):
    import traceback
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Server Error</title></head>
    <body style="font-family:sans-serif;padding:30px;background:#111;color:#eee;">
        <h2 style="color:#ff6b6b;">Application Error (500)</h2>
        <p><b>Detail:</b> {e}</p>
        <pre style="background:#222;padding:15px;border-radius:6px;overflow:auto;">{traceback.format_exc()}</pre>
    </body>
    </html>
    """, 500


handler = app

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
