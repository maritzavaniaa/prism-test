"""Mencocokkan keluaran `prism scan` dengan harapan.json. Hanya pustaka standar.

Pakai:
    python3 skrip/periksa_hasil.py <berkas keluaran PRISM> <harapan.json> [awalan-path]

`awalan-path` (misalnya data/bersih) membatasi pembandingan ke berkas di bawah awalan itu.
Keluar dengan kode 0 bila semua cocok, 1 bila ada selisih.
"""

import json
import os
import re
import sys
from collections import defaultdict

BARIS_TEMUAN = re.compile(r"^(.+?):(\d+):(\d+)  (\w+)  (high|medium|low)  [*\d]+$")
TINGKAT = ("high", "medium", "low")


def baca_temuan(path_keluaran: str) -> dict:
    hasil = defaultdict(lambda: dict.fromkeys(TINGKAT, 0))
    with open(path_keluaran, encoding="utf-8") as f:
        for baris in f:
            m = BARIS_TEMUAN.match(baris.rstrip("\n"))
            if m:
                hasil[os.path.normpath(m.group(1))][m.group(5)] += 1
    return hasil


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        return 2
    awalan = os.path.normpath(sys.argv[3]) if len(sys.argv) == 4 else ""
    cocok_awalan = lambda p: p == awalan or p.startswith(awalan + os.sep) if awalan else True  # noqa: E731

    with open(sys.argv[2], encoding="utf-8") as f:
        harapan = {os.path.normpath(p): h for p, h in json.load(f)["berkas"].items() if cocok_awalan(os.path.normpath(p))}
    ditemukan = {p: h for p, h in baca_temuan(sys.argv[1]).items() if cocok_awalan(p)}

    selisih = []
    for path in sorted(set(harapan) | set(ditemukan)):
        diharapkan = harapan.get(path, dict.fromkeys(TINGKAT, 0))
        didapat = ditemukan.get(path, dict.fromkeys(TINGKAT, 0))
        if diharapkan != didapat:
            selisih.append((path, diharapkan, didapat))

    total_h = {t: sum(h[t] for h in harapan.values()) for t in TINGKAT}
    total_d = {t: sum(h[t] for h in ditemukan.values()) for t in TINGKAT}
    print(f"Berkas dibandingkan: {len(harapan)}")
    print(f"Harapan: {total_h}")
    print(f"Didapat: {total_d}")
    if not selisih:
        print("COCOK: semua berkas sesuai harapan.")
        return 0
    print(f"SELISIH di {len(selisih)} berkas:")
    for path, h, d in selisih[:30]:
        print(f"  {path}: harapan {h}, didapat {d}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
