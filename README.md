# IDX TERMINAL PRO V2 FIXED
Perbaikan utama: Legacy/PRO Schema Adapter. Data lama `all_stocks` tetap langsung dirender, lalu UI otomatis membuat field PRO fallback sampai engine Python menghasilkan schema lengkap.

## Deploy
Upload semua isi folder ke GitHub repository. Aktifkan GitHub Pages dari branch utama. Jangan upload folder pembungkus ZIP saja jika ingin root Pages langsung bekerja.

## Jika cache lama
Tutup PWA, buka ulang, atau hapus site data sekali. Service worker V2 membersihkan cache versi sebelumnya.


## V3 Emiten Manager
Daftar master emiten sekarang ada di `emiten.json`. Tambah ticker baru dengan object `{ "ticker": "XXXX", "sector": "...", "active": true }`. GitHub Actions membaca file ini. Update akan DITOLAK jika jumlah hasil sukses kurang dari 70% database, sehingga data.json lama tidak tertimpa.
