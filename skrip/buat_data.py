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

Harapan kelompok baru (data/bahasa, hp, email, nama-berkas) ditulis di bagian `agregat`: per
awalan path, per rule, per tingkat. Nama berkas tidak bisa dicocokkan per berkas karena path di
keluaran PRISM disamarkan (KF-29), jadi nama-berkas dibandingkan sebagai satu folder.

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


DOMAIN_PRIBADI = [
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.id", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "msn.com", "icloud.com", "me.com", "proton.me", "protonmail.com",
]  # fmt: skip
DOMAIN_LAIN = ["pt-abc.co.id", "example.com", "perusahaan.id", "kampus.ac.id", "dinas.go.id"]
NAMA = ["budi", "ani", "siti", "agus", "dewi", "rudi", "wati", "eko", "sri", "andi"]
BENTUK_HP = {  # bentuk -> tingkat dasar menurut KF-12 (tanpa konteks)
    "plus62": "high", "plus62-344": "high", "nol": "medium", "nol-pemisah": "high", "62-polos": "medium",
    "62-pemisah": "high", "344": "medium", "polos": "low", "pemisah-lain": "low",
}  # fmt: skip
HP_PENGECOH = ["8123456", "08123456789012", "081234567890123", "080123456789", "12345678901234"]
EMAIL_PENGECOH_TIDAK_TERDETEKSI = ["a" * 65 + "@gmail.com", "budi@gmail.c", "@gmail.com", "budi@gmail"]


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
        self.agregat = {}  # awalan path -> rule -> tingkat -> jumlah
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

    def catat(self, awalan: str, rule: str, tingkat: str, jumlah: int = 1) -> None:
        sel = self.agregat.setdefault(awalan, {}).setdefault(rule, {"high": 0, "medium": 0, "low": 0})
        sel[tingkat] += jumlah

    def berkas(self, rel: str, teks, harapan=()) -> None:
        """Tulis berkas dan catat harapan agregatnya. harapan: iterasi (rule, tingkat). Kosong = tidak ada temuan."""
        self.tulis(rel, teks)
        self.agregat.setdefault(rel, {})
        for rule, tingkat in harapan:
            self.catat(rel, rule, tingkat)

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

    # --- kelompok tambahan: bahasa, HP, email, nama berkas ---

    def hp(self, bentuk: str) -> str:
        r = self.rng
        n = 11 if bentuk in ("plus62-344", "nol-pemisah", "62-pemisah", "344") else r.randint(9, 12)
        if bentuk == "pemisah-lain":
            n = 11
        h = "8" + str(r.randint(1, 9)) + self.angka_acak(n - 2)
        if bentuk == "plus62":
            return "+62" + h
        if bentuk == "plus62-344":
            return f"+62 {h[:3]}-{h[3:7]}-{h[7:11]}"
        if bentuk == "nol":
            return "0" + h
        if bentuk == "nol-pemisah":
            return f"0{h[:3]}-{h[3:7]}-{h[7:11]}"
        if bentuk == "62-polos":
            return "62" + h
        if bentuk == "62-pemisah":
            return f"62 {h[:3]} {h[3:7]} {h[7:11]}"
        if bentuk == "344":
            return f"{h[:3]}-{h[3:7]}-{h[7:11]}"
        if bentuk == "polos":
            return h
        if bentuk == "pemisah-lain":  # 4-4-3, bukan 3-4-4
            return f"{h[:4]}-{h[4:8]}-{h[8:11]}"
        raise ValueError(bentuk)

    def email(self, domain: str) -> str:
        return f"{self.rng.choice(NAMA)}.{self.rng.choice(NAMA)}@{domain}"

    def tambahan(self) -> None:
        r = self.rng

        # 1. Bahasa: tiap berkas memuat satu NIK, satu HP +62, dan satu email, dengan nama field berbahasa Inggris
        # atau Indonesia di sebelah nilainya. Harapan: ketiganya high (+62 sudah high, kata konteks menaikkan email).
        def tiga():
            return self.nik_high(), "+62" + "8" + str(r.randint(1, 9)) + self.angka_acak(9), self.email("gmail.com")

        bahasa = {
            "pemohon.html": '<!DOCTYPE html>\n<html lang="id">\n<head><meta charset="utf-8"><title>Data Pemohon</title></head>\n<body>\n'
                            '  <!-- halaman contoh -->\n  <p>NIK: {nik}</p>\n  <p>HP: {hp}</p>\n  <p>Email: {email}</p>\n</body>\n</html>\n',
            "pemohon.css": '/* gaya halaman data pemohon */\n.nik::before { content: "NIK {nik}"; }\n'
                           '.hp::before { content: "HP {hp}"; }\n.surel::before { content: "Email {email}"; }\n',
            "pemohon.js": 'const pemohon = {\n  nik: "{nik}",\n  phone: "{hp}",\n  email: "{email}",\n};\nmodule.exports = pemohon;\n',
            "pemohon.ts": 'interface Pemohon { nik: string; phone: string; email: string }\n'
                          'const contoh: Pemohon = { nik: "{nik}", phone: "{hp}", email: "{email}" };\nexport default contoh;\n',
            "Pemohon.java": 'public class Pemohon {\n    static final String NIK = "{nik}";\n    static final String PHONE = "{hp}";\n'
                            '    static final String EMAIL = "{email}";\n}\n',
            "pemohon.go": 'package main\n\nvar pemohon = map[string]string{\n\t"nik":   "{nik}",\n\t"phone": "{hp}",\n\t"email": "{email}",\n}\n',
            "pemohon.php": "<?php\n$pemohon = ['nik' => '{nik}', 'phone' => '{hp}', 'email' => '{email}'];\n",
            "pemohon.xml": '<?xml version="1.0" encoding="UTF-8"?>\n<pemohon>\n  <nik>{nik}</nik>\n  <phone>{hp}</phone>\n  <email>{email}</email>\n</pemohon>\n',
            "pemohon.sh": '#!/bin/sh\nexport PEMOHON_NIK="{nik}"\nexport PEMOHON_PHONE="{hp}"\nexport PEMOHON_EMAIL="{email}"\n',
            "pemohon.toml": '[pemohon]\nnik = "{nik}"\nphone = "{hp}"\nemail = "{email}"\n',
            "pemohon.ini": "[pemohon]\nnik={nik}\nphone={hp}\nemail={email}\n",
            "Dockerfile": "FROM python:3.13-slim\nENV PEMOHON_NIK={nik}\nENV PEMOHON_PHONE={hp}\nLABEL email={email}\n",
            ".env": "PEMOHON_NIK={nik}\nPEMOHON_PHONE={hp}\nPEMOHON_EMAIL={email}\n",
            "Makefile": "NIK ?= {nik}\nPHONE ?= {hp}\nEMAIL ?= {email}\n\nall:\n\t@echo ok\n",
            "min.js": 'var a=1,b=2;function f(x){return x*2}var p={nik:"{nik}",phone:"{hp}",email:"{email}"};console.log(f(a),b,p);\n',
        }
        for nama, templat in bahasa.items():
            nik, hp, email = tiga()
            self.berkas(f"data/bahasa/{nama}", templat.replace("{nik}", nik).replace("{hp}", hp).replace("{email}", email),
                        [("nik", "high"), ("hp", "high"), ("email", "high")])

        # SQL satu baris: nilai email jatuh lebih dari 40 karakter dari kata `email`, jadi konteks tidak menjangkau: medium.
        nik, hp, email = tiga()
        self.berkas("data/bahasa/insert-satu-baris.sql",
                    f"INSERT INTO pemohon (nik, hp, email) VALUES ('{nik}', '{hp}', '{email}');\n",
                    [("nik", "high"), ("hp", "high"), ("email", "medium")])
        # SQL banyak baris: kata kolom ada di baris lain, jadi konteks tidak terbaca. NIK dan HP tetap high dari bukti sendiri.
        nik, hp, email = tiga()
        self.berkas("data/bahasa/insert-banyak-baris.sql",
                    f"INSERT INTO pemohon (nik, hp, email) VALUES\n('{nik}',\n '{hp}',\n '{email}');\n",
                    [("nik", "high"), ("hp", "high"), ("email", "medium")])

        # 2. HP: tiap bentuk, tanpa dan dengan kata konteks, dan pengecoh.
        for bentuk, dasar in BENTUK_HP.items():
            for lokasi, kata in (("tanpa-konteks", None), ("dengan-konteks", "hp")):
                nilai = [self.hp(bentuk) for _ in range(2)]
                akhir = dasar if kata is None else naik(dasar)
                baris = [f"Hubungi {v} untuk informasi lebih lanjut." if kata is None else f"{kata}: {v}" for v in nilai]
                self.berkas(f"data/hp/{lokasi}/{bentuk}.txt", "\n".join(baris) + "\n", [("hp", akhir)] * 2)
        self.berkas("data/hp/pengecoh/pengecoh.txt", "\n".join(f"Nomor {v} bukan telepon." for v in HP_PENGECOH).replace("telepon", "ponsel") + "\n")

        # 3. Email: domain pribadi dan domain lain, tanpa dan dengan kata konteks, dan pengecoh.
        for nama, domain, tanpa, dengan in (
            ("pribadi", DOMAIN_PRIBADI, "medium", "high"),
            ("perusahaan", DOMAIN_LAIN, "low", "low"),  # domain di luar daftar: konteks tidak menaikkan
        ):
            alamat = [self.email(d) for d in domain]
            self.berkas(f"data/email/{nama}-tanpa-konteks.txt", "\n".join(f"Kirim ke {a} segera." for a in alamat) + "\n", [("email", tanpa)] * len(alamat))
            alamat = [self.email(d) for d in domain]
            self.berkas(f"data/email/{nama}-dengan-konteks.txt", "\n".join(f"email: {a}" for a in alamat) + "\n", [("email", dengan)] * len(alamat))
        self.berkas(
            "data/email/pengecoh.txt",
            "\n".join(f"alamat: {a}" for a in EMAIL_PENGECOH_TIDAK_TERDETEKSI) + "\ngit clone git@" + "github.com:user/repo.git\n",
            [("email", "low")],  # hanya alamat SSH yang terdeteksi, sebagai low
        )

        # 4. Nama berkas dan folder. Isi berkas tidak berisi PII, jadi semua temuan berasal dari nama.
        # Path di keluaran PRISM disamarkan, jadi harapannya dibandingkan sebagai satu folder.
        awalan = "data/nama-berkas"
        (AKAR / awalan).mkdir(parents=True, exist_ok=True)
        self.tulis(f"{awalan}/KTP_{self.nik_high()}.jpg", b"\x89PNG\x00\x01")
        self.catat(awalan, "nik", "high")
        nik_folder = self.nik_high()
        self.tulis(f"{awalan}/{nik_folder}/catatan.txt", "halo\n")
        self.catat(awalan, "nik", "high")
        self.tulis(f"{awalan}/ktp_{self.nik_low()}.jpg", b"\x89PNG\x00\x01")  # kata `ktp` menaikkan low jadi medium
        self.catat(awalan, "nik", "medium")
        self.tulis(f"{awalan}/export_" + "2026" + "1125" + "1030" + "4512" + ".csv", "id\n")  # timestamp 16 digit: provinsi 20 tidak ada, low. Disusun dari potongan agar skrip ini tidak ikut terdeteksi
        self.catat(awalan, "nik", "low")
        self.tulis(f"{awalan}/hp_+62{'8' + str(r.randint(1, 9)) + self.angka_acak(9)}.log", "x\n")
        self.catat(awalan, "hp", "high")
        self.tulis(f"{awalan}/{self.email('gmail.com')}_ekspor.txt", "x\n")
        self.catat(awalan, "email", "medium")

        # 5. UTF-16 (BOM): mengandung byte nol, jadi dilewati sebagai biner. Temuan di dalamnya terlewat.
        self.tulis("data/non-utf8/utf16.txt", ("\ufeffnik: " + self.nik_high() + "\n").encode("utf-16"), {})
        self.dilewati.append("data/non-utf8/utf16.txt")

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

        self.tambahan()

        total = {t: sum(h[t] for h in self.harapan.values()) for t in ("high", "medium", "low")}
        (AKAR / "harapan.json").write_text(
            json.dumps(
                {
                    "seed": SEED,
                    "total": total,
                    "dilewati": sorted(self.dilewati),
                    "abaikan_hp_email": ["data/nik/bentuk-lain"],
                    "berkas": dict(sorted(self.harapan.items())),
                    "agregat": dict(sorted(self.agregat.items())),
                },
                indent=2,
            ) + "\n",
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
