"""Pembuat data sintetis untuk prism-test. Hanya pustaka standar.

Pakai (dari akar repo):
    python3 skrip/buat_data.py <folder kode-wilayah PRISM>
Contoh:
    python3 skrip/buat_data.py ../PRISM/src/prism/data/kode-wilayah

Semua nilai REKAAN. Nomor urut (4 digit terakhir) dibuat `0000`. Asumsi ⚠️: SIAK
memulai nomor urut dari 0001, jadi NIK berakhiran 0000 tidak mungkin milik orang nyata.

Keluaran: folder data/ dan harapan.json (jumlah temuan per berkas per tingkat).
Seed tetap, jadi hasilnya sama setiap dijalankan.

Harapan di harapan.json adalah tingkat AKHIR menurut PRISM Langkah 8: bila kunci isian `nik`
berada di baris yang sama, tingkat naik satu (low -> medium -> high). Kunci `ref` tidak
menaikkan. Ambang tidak diterapkan di sini: jalankan PRISM dengan `--min-level low`.

Catatan sirkularitas: kode wilayah diambil dari data PRISM sendiri, jadi NIK `high`
pasti dikenali PRISM. Data ini untuk uji integrasi dan eksplorasi, BUKAN bukti akurasi.
"""

import csv
import json
import random
import shutil
import sys
from pathlib import Path

SEED = 20261125
AKAR = Path(__file__).resolve().parent.parent
DATA = AKAR / "data"
BATAS_BYTE = 1_000_000

FILLER = [
    "Laporan bulanan dibuat otomatis oleh sistem.",
    "Versi aplikasi 2.4.1 dirilis pada 2026-11-25.",
    "Total transaksi hari ini: 1250 dari 1300 permintaan.",
    "Server berjalan normal, waktu respons 120 ms.",
    "Catatan: dokumen ini hanya data uji sintetis.",
    "Alamat IP internal 10.0.0.12 tidak dipublikasikan.",
    "Kode pesanan ORD-20261125-0042 sudah dikirim.",
    "Pengguna diminta memperbarui kata sandi tiap 90 hari.",
    "Cadangan basis data selesai pukul 02:15 dalam 38 detik.",
    "Jumlah baris diproses: 48213, gagal: 0.",
]
EKSTENSI = [".md", ".txt", ".log", ".py", ".json", ".yaml", ".csv"]


def baca_kode(folder: Path, nama: str) -> list:
    with open(folder / nama, encoding="utf-8", newline="") as f:
        return sorted(baris["kode"].strip() for baris in csv.DictReader(f))


def naik(tingkat: str) -> str:
    """Konteks menaikkan satu tingkat (KF-14)."""
    return {"low": "medium", "medium": "high", "high": "high"}[tingkat]


class Pembuat:
    def __init__(self, folder_wilayah: Path):
        self.rng = random.Random(SEED)
        self.provinsi = baca_kode(folder_wilayah, "provinsi.csv")
        self.kecamatan = baca_kode(folder_wilayah, "kecamatan.csv")
        self.set_kecamatan = set(self.kecamatan)
        self.harapan = {}  # path relatif -> {"high": n, "medium": n, "low": n}
        self.dilewati = []

    # --- pembuat nilai ---

    def _tanggal(self, hari=None, bulan=None) -> str:
        r = self.rng
        perempuan = r.random() < 0.5
        hari = hari if hari is not None else r.randint(1, 28) + (40 if perempuan else 0)
        bulan = bulan if bulan is not None else r.randint(1, 12)
        return f"{hari:02d}{bulan:02d}{r.randint(0, 99):02d}"

    def nik_high(self) -> str:
        return self.rng.choice(self.kecamatan) + self._tanggal() + "0000"

    def nik_medium(self) -> str:
        r = self.rng
        prov = r.choice(self.provinsi)
        while True:
            kec = prov + f"{r.randint(0, 9999):04d}"
            if kec not in self.set_kecamatan:
                return kec + self._tanggal() + "0000"

    def nik_low(self) -> str:
        r = self.rng
        jenis = r.choice(["bulan13", "hari32", "hari00", "provinsi"])
        kec = r.choice(self.kecamatan)
        if jenis == "bulan13":
            return kec + self._tanggal(bulan=r.randint(13, 99)) + "0000"
        if jenis == "hari32":
            return kec + self._tanggal(hari=r.randint(32, 40)) + "0000"
        if jenis == "hari00":
            return kec + self._tanggal(hari=0) + "0000"
        prov_salah = r.choice([p for p in ("00", "10", "20", "41", "99") if p not in self.provinsi])
        return prov_salah + kec[2:] + self._tanggal() + "0000"

    def angka_acak(self, panjang: int) -> str:
        return "".join(self.rng.choice("0123456789") for _ in range(panjang))

    def dengan_pemisah(self, nik: str) -> str:
        pemisah = self.rng.choice(["-", " ", "."])
        return pemisah.join(nik[i : i + 4] for i in range(0, 16, 4))

    # --- isi berkas menurut ekstensi ---

    def _filler(self, n: int) -> list:
        return [self.rng.choice(FILLER) for _ in range(n)]

    def isi(self, ext: str, nilai: list, kunci: str) -> str:
        fil = self._filler(self.rng.randint(3, 10))
        if ext == ".md":
            baris = ["# Catatan", ""] + [f"- {x}" for x in fil[:2]]
            for v in nilai:
                baris.append(f"- Pemohon dengan NIK {v} terdaftar." if kunci == "nik" else f"- Nomor {kunci} {v} tercatat.")
            return "\n".join(baris + [f"- {x}" for x in fil[2:]]) + "\n"
        if ext == ".txt":
            baris = fil[:2] + [f"{kunci}: {v}" for v in nilai] + fil[2:]
            return "\n".join(baris) + "\n"
        if ext == ".log":
            baris = [f"2026-11-25 10:{i % 60:02d}:00 INFO {x}" for i, x in enumerate(fil)]
            baris += [f"2026-11-25 11:{i % 60:02d}:00 INFO login {kunci}={v}" for i, v in enumerate(nilai)]
            return "\n".join(baris) + "\n"
        if ext == ".py":
            baris = [f"# {x}" for x in fil[:2]] + ["DATA = ["] + [f'    {{"{kunci}": "{v}"}},' for v in nilai] + ["]"]
            return "\n".join(baris + [f"# {x}" for x in fil[2:]]) + "\n"
        if ext == ".json":
            return json.dumps({"catatan": fil, "pengguna": [{kunci: v} for v in nilai]}, indent=2) + "\n"
        if ext == ".yaml":
            baris = ["pengguna:"] + [f'  - {kunci}: "{v}"' for v in nilai] + ["catatan:"] + [f"  - {x}" for x in fil]
            return "\n".join(baris) + "\n"
        if ext == ".csv":
            baris = [f"id,nama,{kunci},kota"] + [f"{i},Nama Contoh,{v},Kota Contoh" for i, v in enumerate(nilai, 1)]
            baris += [f"{900 + i},Nama Lain,-,Kota Lain" for i in range(len(fil))]
            return "\n".join(baris) + "\n"
        raise ValueError(ext)

    # --- penulisan ---

    def tulis(self, rel: str, teks, harapan=None) -> None:
        path = AKAR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(teks, bytes):
            path.write_bytes(teks)
        else:
            path.write_text(teks, encoding="utf-8")
        if harapan is not None:
            self.harapan[rel] = {"high": 0, "medium": 0, "low": 0, **harapan}

    def kelompok(self, folder, prefix, jumlah, pilih_nilai, kunci_nik="nik"):
        """Buat `jumlah` berkas. pilih_nilai() -> (daftar nilai, harapan, kunci)."""
        for i in range(jumlah):
            ext = EKSTENSI[i % len(EKSTENSI)]
            nilai, harapan, kunci = pilih_nilai()
            self.tulis(f"{folder}/{prefix}-{i + 1:03d}{ext}", self.isi(ext, nilai, kunci), harapan)

    def berkas_besar(self, rel: str, ukuran: int, nik: str, harapan) -> None:
        akhir = f"nik: {nik}\n"
        isi = ("x" * 79 + "\n") * ((ukuran - len(akhir)) // 80)
        sisa = ukuran - len(isi) - len(akhir)
        if sisa:
            isi += "x" * (sisa - 1) + "\n"
        data = (isi + akhir).encode("ascii")
        assert len(data) == ukuran, (len(data), ukuran)
        self.tulis(rel, data, harapan)

    def buat(self) -> None:
        r = self.rng

        def bersih():
            nilai = []
            if r.random() < 0.4:  # angka 15 dan 17 digit: bukan NIK, jangan dilaporkan
                nilai = [self.angka_acak(r.choice([15, 17])) for _ in range(r.randint(1, 3))]
            return nilai, {}, "seri"

        def high():
            return [self.nik_high() for _ in range(r.randint(1, 5))], None, "nik" if r.random() < 0.5 else "ref"

        def medium():
            return [self.nik_medium() for _ in range(r.randint(1, 3))], None, "nik" if r.random() < 0.5 else "ref"

        def low():
            return [self.nik_low() for _ in range(r.randint(1, 3))], None, "nik" if r.random() < 0.5 else "ref"

        def bentuk_lain():
            return [self.dengan_pemisah(self.nik_high()) for _ in range(r.randint(1, 3))], {}, "nik"

        def campuran():
            nilai, h = [], {"high": 0, "medium": 0, "low": 0}
            for _ in range(r.randint(3, 8)):
                jenis = r.choice(["high", "high", "medium", "low"])
                nilai.append(getattr(self, f"nik_{jenis}")())
                h[naik(jenis)] += 1  # kunci selalu `nik`, jadi konteks menaikkan
            r.shuffle(nilai)
            return nilai, h, "nik"

        def dengan_harapan(fungsi, tingkat):
            def bungkus():
                nilai, h, kunci = fungsi()
                akhir = naik(tingkat) if kunci == "nik" else tingkat
                return nilai, {akhir: len(nilai)}, kunci
            return bungkus

        self.kelompok("data/bersih", "bersih", 60, bersih)
        self.kelompok("data/nik/high", "high", 30, dengan_harapan(high, "high"))
        self.kelompok("data/nik/medium", "medium", 15, dengan_harapan(medium, "medium"))
        self.kelompok("data/nik/low", "low", 15, dengan_harapan(low, "low"))
        self.kelompok("data/nik/bentuk-lain", "berpemisah", 10, bentuk_lain)
        self.kelompok("data/campuran", "campuran", 20, campuran)

        # Batas 1 MB: tepat 1.000.000 byte dipindai, 1 byte lebih dilewati (temuan di dalamnya terlewat).
        self.berkas_besar("data/besar/tepat-1mb.txt", BATAS_BYTE, self.nik_high(), {"high": 1})
        self.berkas_besar("data/besar/lebih-1mb.txt", BATAS_BYTE + 1, self.nik_high(), {})
        self.dilewati.append("data/besar/lebih-1mb.txt")

        # Berkas biner: dilewati walau berisi teks mirip NIK.
        self.tulis("data/biner/foto.png", f"bukan gambar sungguhan nik: {self.nik_high()}\n", {})
        self.tulis("data/biner/data.dat", b"\x00\x01" + f"nik: {self.nik_high()}\n".encode(), {})
        self.dilewati += ["data/biner/foto.png", "data/biner/data.dat"]

        # Bukan UTF-8 (Latin-1): tetap terbaca dengan karakter pengganti, NIK tetap terdeteksi.
        self.tulis(
            "data/non-utf8/latin1.txt",
            b"Nama: Jos\xe9 \xc1lvarez\nnik: " + self.nik_high().encode() + b"\n",
            {"high": 1},
        )

        total = {t: sum(h[t] for h in self.harapan.values()) for t in ("high", "medium", "low")}
        (AKAR / "harapan.json").write_text(
            json.dumps({"seed": SEED, "total": total, "dilewati": sorted(self.dilewati), "berkas": dict(sorted(self.harapan.items()))}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{len(self.harapan)} berkas dibuat. Harapan total: {total}. Dilewati: {len(self.dilewati)}")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    if DATA.exists():
        shutil.rmtree(DATA)
    Pembuat(Path(sys.argv[1])).buat()
    return 0


if __name__ == "__main__":
    sys.exit(main())
