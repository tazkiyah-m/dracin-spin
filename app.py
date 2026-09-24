"""
Spin & Menang - Palekko Chicken / Gacoan DNA / Grass Jelly Drink
-----------------------------------------------------------------
Backend logika untuk web spin promo dengan sistem keamanan lengkap:
- Autentikasi PIN 6 digit untuk Admin/Kasir (/admin & /api/admin/*)
- Proteksi Brute-force dengan lockout otomatis jika 5x salah PIN
- Token sesi khusus layar pelanggan (Client Session Token)
- Proteksi Anti-Cheat: Threading Lock (Race condition) & Cooldown Spin
- Validasi ketat input tipe spin
"""

import os
import random
import time
import threading
import uuid
from datetime import date
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dracin-spin-super-secret-key-2026")

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

# 10 slot roda: mayoritas zonk, 3 slot untuk masing-masing hadiah.
SEGMENTS = [
    {"prize_key": None},
    {"prize_key": "Palekko Chicken"},
    {"prize_key": None},
    {"prize_key": None},
    {"prize_key": "Gacoan DNA"},
    {"prize_key": None},
    {"prize_key": None},
    {"prize_key": "Grass Jelly Drink"},
    {"prize_key": None},
    {"prize_key": None},
]

# Penyimpanan stok harian di memori. Direset otomatis saat tanggal berubah.
_stock_state = {"date": date.today().isoformat(), "given": {k: 0 for k in PRIZES}}


def _reset_stock_if_new_day():
    today = date.today().isoformat()
    if _stock_state["date"] != today:
        _stock_state["date"] = today
        _stock_state["given"] = {k: 0 for k in PRIZES}


def _stock_left(prize_key):
    _reset_stock_if_new_day()
    limit = PRIZES[prize_key]["daily_limit"]
    if limit is None:
        return None
    return max(0, limit - _stock_state["given"][prize_key])


# Global state untuk toko (asumsi 1 layar pelanggan utama di toko)
store_state = {
    "credit_2k": 0,
    "credit_5k": 0,
    "history": []
}


def _public_state():
    _reset_stock_if_new_day()
    stock = {k: _stock_left(k) for k in PRIZES}
    return {
        "credit_2k": store_state["credit_2k"],
        "credit_5k": store_state["credit_5k"],
        "history": store_state["history"][-10:][::-1],
        "prizes": {
            k: {"name": v["name"], "stock_left": stock[k]}
            for k, v in PRIZES.items()
        },
    }


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

    # 4. Atomic Execution dengan Threading Lock (Cegah Race Condition)
    with _spin_lock:
        # Re-check cooldown di dalam lock
        if time.time() - _client_cooldowns.get(client_token, 0) < 4.2:
            return jsonify({"error": "Piring sedang berputar."}), 429

        _reset_stock_if_new_day()

        if spin_type == "2k" and store_state["credit_2k"] < 1:
            return jsonify({"error": "Kredit 2K tidak cukup."}), 402
        elif spin_type == "5k" and store_state["credit_5k"] < 1:
            return jsonify({"error": "Kredit 5K tidak cukup."}), 402

        # Potong kredit secara atomic
        if spin_type == "2k":
            store_state["credit_2k"] -= 1
        else:
            store_state["credit_5k"] -= 1

        _client_cooldowns[client_token] = time.time()

        # Hitung peluang menang
        weights = []
        for i, seg in enumerate(SEGMENTS):
            key = seg["prize_key"]
            if key is None:
                weight = 10 if spin_type == "2k" else 2
            else:
                if _stock_left(key) > 0:
                    weight = 1 if spin_type == "2k" else 5
                else:
                    weight = 0
            weights.append(weight)

        chosen_index = random.choices(range(len(SEGMENTS)), weights=weights, k=1)[0]
        chosen = SEGMENTS[chosen_index]
        prize_key = chosen["prize_key"]

        if prize_key is not None:
            _stock_state["given"][prize_key] += 1
            result = {"is_win": True, "prize_key": prize_key, "prize_name": PRIZES[prize_key]["name"]}
        else:
            result = {"is_win": False, "prize_key": None, "prize_name": "Zonk"}

        store_state["history"].append(result)

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

    with _spin_lock:
        if spin_type == "2k":
            store_state["credit_2k"] += 1
        else:
            store_state["credit_5k"] += 1

    return jsonify({"status": "success", "state": _public_state()})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
    # clean state reload
