# Spin & Menang — Palekko Chicken / Gacoan DNA / Grass Jelly Drink

Web game roda putar untuk promo jualan. Logika utama (siapa menang,
siapa zonk, stok hadiah harian) dihitung di **backend Python (Flask)**,
bukan di JavaScript — supaya tidak bisa dicurangi dari browser.

## Cara menjalankan (lokal)

```bash
cd spin-game
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

export SECRET_KEY="ganti-dengan-string-acak-yang-panjang"   # Windows: set SECRET_KEY=...
python app.py
```

Buka `http://localhost:5000` di browser.

## Struktur

```
spin-game/
├── app.py              # Semua logika: kredit, undian, stok harian
├── templates/
│   └── index.html      # Tampilan halaman
├── static/
│   ├── style.css
│   └── script.js        # Panggil API Flask & animasikan roda
└── requirements.txt
```

## Cara kerja logikanya

- **Roda** punya 10 slot: 3 slot hadiah (Palekko Chicken, Gacoan DNA,
  Grass Jelly Drink) dan 7 slot zonk.
- Setiap putar, server mengundi 1 slot secara acak dari slot yang
  *masih valid* — hadiah yang stok hariannya sudah habis otomatis
  diperlakukan sebagai zonk pada undian itu (tapi tetap tampil di roda).
- Stok harian tiap hadiah diatur di `PRIZES` dalam `app.py`
  (`daily_limit`), dan otomatis reset tiap pergantian tanggal.
- Kredit putaran dan riwayat disimpan per pengunjung lewat session
  cookie Flask (`session["credit"]`, `session["history"]`).

## Yang WAJIB diganti sebelum dipakai serius (produksi)

1. **Pembayaran masih simulasi.** Tombol "Bayar" langsung menambah
   kredit tanpa transaksi uang asli. Sambungkan `/api/pay` ke payment
   gateway (mis. Midtrans, Xendit, atau QRIS) dan baru tambah kredit
   setelah gateway mengonfirmasi pembayaran (idealnya lewat webhook,
   bukan langsung dari klik tombol di browser).
2. **Penyimpanan di memori.** `session["credit"]`, riwayat, dan stok
   harian (`_stock_state`) disimpan di variabel Python biasa — akan
   hilang saat server restart, dan tidak konsisten kalau dijalankan
   dengan lebih dari satu worker/proses. Untuk produksi, pindahkan ke
   database (SQLite/PostgreSQL) atau Redis.
3. **`SECRET_KEY`.** Wajib diisi dengan string acak & rahasia lewat
   environment variable saat deploy, jangan pakai nilai default di kode.
4. **Deploy.** Untuk produksi jangan pakai `app.run(debug=True)` —
   pakai WSGI server seperti `gunicorn` (`gunicorn app:app`) di
   belakang Nginx, atau platform seperti Railway/Render/PythonAnywhere.
