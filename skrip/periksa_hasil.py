"""Mencocokkan keluaran `prism scan` dengan harapan.json. Hanya pustaka standar.

Pakai:
    python3 skrip/periksa_hasil.py <berkas keluaran PRISM> <harapan.json> [awalan-path]

`awalan-path` (misalnya data/bersih) membatasi pembandingan ke berkas di bawah awalan itu.
Keluar dengan kode 0 bila semua cocok, 1 bila ada selisih.

Tiga bagian pembandingan:
1. `berkas`: harapan rule `nik` per berkas (kelompok lama, di luar `agregat`).
2. `agregat`: harapan per awalan path, per rule, per tingkat (data/bahasa, hp, email, nama-berkas).
   Awalan bisa berupa folder atau satu berkas. Nama berkas dibandingkan sebagai satu folder karena
   path di keluaran PRISM disamarkan (KF-29).
3. Penjaga: rule `hp` dan `email` tidak boleh muncul di luar `agregat`, kecuali di awalan yang tercatat
   di `abaikan_hp_email` (NIK berpemisah memicu kandidat HP palsu, batasan PRISM Langkah 7).
"""

import json
import os
import re
import sys
from collections import defaultdict

BARIS_TEMUAN = re.compile(r"^(.+?):(\d+):(\d+)  (\w+)  (high|medium|low)  \S+$")
TINGKAT = ("high", "medium", "low")
RULES = ("nik", "hp", "email")


def baca_temuan(path_keluaran: str) -> list:
    """Daftar (path, rule, tingkat) dari baris temuan di keluaran PRISM."""
    hasil = []
    with open(path_keluaran, encoding="utf-8") as f:
        for baris in f:
            m = BARIS_TEMUAN.match(baris.rstrip("\n"))
            if m:
                hasil.append((os.path.normpath(m.group(1)), m.group(4), m.group(5)))
    return hasil


def di_bawah(path: str, awalan: str) -> bool:
    return path == awalan or path.startswith(awalan + os.sep)


def nol() -> dict:
    return dict.fromkeys(TINGKAT, 0)


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        return 2
    awalan_arg = os.path.normpath(sys.argv[3]) if len(sys.argv) == 4 else ""
    dalam_cakupan = lambda p: di_bawah(p, awalan_arg) if awalan_arg else True  # noqa: E731

    with open(sys.argv[2], encoding="utf-8") as f:
        data = json.load(f)
    agregat = {os.path.normpath(a): r for a, r in data.get("agregat", {}).items() if dalam_cakupan(os.path.normpath(a))}
    abaikan = [os.path.normpath(a) for a in data.get("abaikan_hp_email", [])]
    harapan_berkas = {
        os.path.normpath(p): h for p, h in data["berkas"].items()
        if dalam_cakupan(os.path.normpath(p)) and not any(di_bawah(os.path.normpath(p), a) for a in agregat)
    }  # fmt: skip
    temuan = [t for t in baca_temuan(sys.argv[1]) if dalam_cakupan(t[0])]

    selisih = []

    # 1. rule nik per berkas, di luar agregat
    didapat = defaultdict(nol)
    for path, rule, tingkat in temuan:
        if rule == "nik" and not any(di_bawah(path, a) for a in agregat):
            didapat[path][tingkat] += 1
    for path in sorted(set(harapan_berkas) | set(didapat)):
        h, d = harapan_berkas.get(path, nol()), didapat.get(path, nol())
        if h != d:
            selisih.append(f"{path} (nik): harapan {h}, didapat {d}")

    # 2. agregat per awalan dan rule
    for awalan in sorted(agregat):
        for rule in RULES:
            h = {**nol(), **agregat[awalan].get(rule, {})}
            d = nol()
            for path, r, tingkat in temuan:
                if r == rule and di_bawah(path, awalan):
                    d[tingkat] += 1
            if h != d:
                selisih.append(f"{awalan} ({rule}): harapan {h}, didapat {d}")

    # 3. penjaga hp dan email di luar agregat
    for path, rule, tingkat in temuan:
        if rule in ("hp", "email") and not any(di_bawah(path, a) for a in list(agregat) + abaikan):
            selisih.append(f"{path} ({rule} {tingkat}): tidak diharapkan")

    total_nik_h = sum(sum(h.values()) for h in harapan_berkas.values())
    total_agregat = sum(sum(sum(t.values()) for t in r.values()) for r in agregat.values())
    print(f"Berkas nik dibandingkan: {len(harapan_berkas)} (harapan {total_nik_h} temuan)")
    print(f"Awalan agregat dibandingkan: {len(agregat)} (harapan {total_agregat} temuan)")
    print(f"Temuan di keluaran: {len(temuan)}")
    if not selisih:
        print("COCOK: semua sesuai harapan.")
        return 0
    print(f"SELISIH sebanyak {len(selisih)}:")
    for baris in selisih[:40]:
        print(f"  {baris}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
