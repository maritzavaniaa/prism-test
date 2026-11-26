# prism-test

Repo percobaan untuk menjalankan [PRISM](https://github.com/maritzavaniaa/PRISM) di GitHub Actions
pada repo lain. **Semua isi `data/` adalah data rekaan.** Tidak ada data pribadi nyata.

## Tujuan

Menguji **integrasi**: apakah PRISM berjalan di runner, job merah dan hijau sesuai exit code,
dan berapa lama pindai pada repo yang cukup besar.

Ini **bukan** evaluasi akurasi. Kode wilayah NIK sintetis diambil dari data PRISM sendiri
(sirkular), jadi NIK `high` pasti dikenali. Jangan menyetel aturan PRISM berdasarkan repo ini
lalu memakainya lagi sebagai data uji.

## Isi

| Folder | Isi | Hasil yang diharapkan |
|---|---|---|
| `data/bersih/` | 60 berkas tanpa NIK. Sebagian memuat angka 15 dan 17 digit (bukan NIK) | 0 temuan |
| `data/nik/high/` | NIK sintetis dengan wilayah dan tanggal sah | `high` |
| `data/nik/medium/` | Provinsi sah, kecamatan tidak terdaftar | `medium` |
| `data/nik/low/` | Tanggal tidak sah atau provinsi tidak terdaftar | `low` |
| `data/nik/bentuk-lain/` | NIK dengan pemisah (`-`, spasi, `.`) | 0 temuan (batasan yang diterima) |
| `data/campuran/` | Campuran `high`, `medium`, `low` | sesuai `harapan.json` |
| `data/besar/` | `tepat-1mb.txt` (1.000.000 byte) dan `lebih-1mb.txt` (1 byte lebih besar) | yang pertama dipindai, yang kedua **dilewati** (temuan di dalamnya terlewat) |
| `data/biner/` | `foto.png` dan `data.dat` (ada byte nol) | dilewati |
| `data/non-utf8/` | Berkas Latin-1 | tetap terbaca, 1 temuan |

`harapan.json` mencatat jumlah temuan per berkas per tingkat. `skrip/periksa_hasil.py` membandingkannya
dengan keluaran PRISM.

## Workflow

`.github/workflows/prism-percobaan.yml` punya tiga job:

| Job | Harapan | Arti |
|---|---|---|
| `pindai-semua` | **Merah** | Ada temuan, PRISM keluar dengan kode 1. Langkah pencocokan harapan harus hijau |
| `pindai-bersih` | Hijau | Folder bersih, kode 0 |
| `kode-keluar` | Hijau | Memastikan kode 0, 1, dan 2 muncul sesuai rancangan |

PRISM diambil dari cabang `main` repo PRISM, jadi perubahan di PRISM harus sudah di-push ke `main`
sebelum job ini mencerminkannya.

## Membuat ulang data

Seed tetap, hasilnya selalu sama:

```bash
python3 skrip/buat_data.py <folder PRISM>/src/prism/data/kode-wilayah
```

Nomor urut NIK sintetis dibuat `0000`. Asumsi (belum diverifikasi): nomor urut asli dimulai dari `0001`,
sehingga NIK berakhiran `0000` tidak mungkin milik orang nyata.

## Menjalankan lokal

```bash
git clone https://github.com/maritzavaniaa/PRISM.git ../PRISM
PYTHONPATH=../PRISM/src python3 -m prism scan . --min-level low | tee hasil.txt
python3 skrip/periksa_hasil.py hasil.txt harapan.json
```

## Catatan

- Rule HP dan email sudah ada di PRISM (Langkah 7), tetapi repo ini belum punya data untuk keduanya.
  `skrip/periksa_hasil.py` sementara hanya mencocokkan rule `nik`. Temuan `hp` di `data/nik/bentuk-lain/`
  adalah kandidat palsu dari NIK berpemisah (batasan yang diterima di PRISM), bukan kesalahan data.
- `harapan.json` berisi tingkat akhir setelah konteks (Langkah 8): kunci `nik` di baris yang sama menaikkan satu tingkat,
  kunci `ref` tidak. Job `pindai-semua` memakai `--min-level low` supaya semua tingkat ikut dicocokkan.
  Pada ambang bawaan (`medium`), temuan `low` tidak dilaporkan.
