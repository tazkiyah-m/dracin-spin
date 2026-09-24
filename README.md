# 🍗 DOCIN - Piring Saji Spin & Menang (Promo Toko)

Aplikasi Web Promo Roda Putar Keberuntungan bertema **Piring Saji Keramik Makanan** dengan desain **Neobrutalism**, sistem autentikasi kasir berbasis PIN, dan proteksi anti-cheat di sisi server Python (Flask).

---

## ✨ Fitur Utama

- **Desain Neobrutalism Unik:** 
  - Visual mesin putar menyerupai piring saji keramik dengan penunjuk garpu makan saji.
  - Ornamen stiker makanan (paha ayam, donat, minuman boba) di latar belakang.
  - Tipografi tegas Google Fonts (*Space Grotesk* & *Outfit*) dengan palet warna Maroon Docin, Hitam, dan Krem.
- **Audio & Efek Real-time:**
  - Musik latar (*Backsound*) Doraemon dengan tombol toggle ON/OFF.
  - Efek suara detukan pasak roda mekanikal yang tersinkronisasi 100% dengan fisika putaran (*cubic-bezier*).
  - Efek perayaan balon & konfeti warna-warni saat menang.
  - Efek dentuman suara ledakan dan retakan layar (*screen shake & glass crack*) saat ZONK.
- **Panel Kasir Terproteksi (`/admin`):**
  - Autentikasi PIN 6 digit (Virtual Numpad ramah sentuhan tablet/POS kasir).
  - Proteksi *anti-brute force* (terkunci 60 detik jika 5x salah PIN berturut-turut).
  - Tombol **Kunci / Keluar** untuk kasir saat meninggalkan meja.
  - Tombol cepat buka kredit putaran (2K dan 5K).
- **Keamanan & Anti-Cheat Pelanggan:**
  - Logika kemenangan dan stok hadiah dihitung 100% di backend Python.
  - *Client Session Token* (`X-Client-Token`) mencegah request liar dari script/curl.
  - *Atomic Threading Lock* untuk mencegah *race condition* atau penggandaan kredit.
  - *Cooldown debounce* 4.2 detik per putaran.

---

## 🛠️ Teknologi yang Digunakan

- **Backend:** Python 3, Flask, Gunicorn
- **Frontend:** Vanilla HTML5, CSS3 (Neobrutalism custom design system), Vanilla JavaScript (Web Audio API, Canvas Confetti)
- **Deployment:** Render.com / PythonAnywhere (Procfile & requirements.txt siap pakai)

---

## 🚀 Cara Menjalankan Secara Lokal

```bash
# 1. Clone repository
git clone https://github.com/username/dracin-spin.git
cd dracin-spin

# 2. Buat virtual environment & install dependensi
python -m venv venv
venv\Scripts\activate      # Di Linux/Mac: source venv/bin/activate
pip install -r requirements.txt

# 3. Jalankan server lokal
python app.py
```

- **Layar Pelanggan:** [http://localhost:5000/](http://localhost:5000/)
- **Panel Kasir:** [http://localhost:5000/admin](http://localhost:5000/admin) *(PIN Default: `123456`)*

---

## ☁️ Deployment ke Render.com

1. Buat Web Service baru di **Render.com**.
2. Sambungkan ke repositori GitHub ini.
3. Pengaturan:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Plan:** Free
