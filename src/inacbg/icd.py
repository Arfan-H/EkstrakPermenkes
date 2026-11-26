"""Cari kode ICD-10 (diagnosis) dan ICD-9-CM (prosedur) dari nama penyakit/tindakan atau kode.

Data: data/processed/icd10.csv dan icd9cm.csv (dibuat scripts/bangun_icd.py) berisi judul resmi
berbahasa Inggris (ICD-10 WHO 2019 + kode 2010 yang berubah; ICD-9-CM CMS v32) dan istilah
Indonesia/awam dari data/manual/istilah_icd.csv (disusun sendiri, bukan terjemahan resmi).

Aturan pencarian (sama persis dengan port JS di web/index.html):
- teks dinormalkan: huruf kecil, tanpa diakritik, selain a-z 0-9 dan titik menjadi spasi;
- setiap kata kueri harus menjadi awalan dari salah satu kata di kode, istilah, atau judul;
- urutan: (0) kueri sama persis dengan kode atau salah satu istilah, (1) semua kata cocok di
  kode/istilah, (2) cocok lewat judul resmi; di dalam tingkat yang sama urut kode.
"""
import csv
import os
import re
import unicodedata

from .penuntun import KATEGORI_ASTERISK

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.path.join(ROOT, "data", "processed")

_DIAKRITIK = re.compile(r"[\u0300-\u036f]")
_BUKAN = re.compile(r"[^a-z0-9.]+")
TANDA = {"2010/2019": 0, "2010": 1, "2019 (setelah 2010)": 2, "karakter ke-5 WHO": 3}
CATATAN_TANDA = {1: "kode ICD-10 2010 (dipakai E-Klaim), tidak ada lagi di versi 2019",
                 2: "kode baru di ICD-10 WHO setelah 2010, mungkin belum diterima E-Klaim",
                 3: "subdivisi karakter ke-5 WHO (dipakai di contoh PMK 26/2021 hal. 31)"}


def norm(s):
    s = _DIAKRITIK.sub("", unicodedata.normalize("NFD", s)).lower()
    return " ".join(_BUKAN.sub(" ", s).split())


class IndeksICD:
    def __init__(self, baris):
        """baris: [(kode, judul, [istilah], tanda)] urut kode."""
        self.entri = []
        for kode, judul, istilah, tanda in baris:
            wk = norm(" ".join([kode] + istilah)).split(" ")
            wj = norm(judul).split(" ")
            self.entri.append({"kode": kode, "judul": judul, "istilah": istilah, "tanda": tanda,
                               "asterisk": kode[:3] in KATEGORI_ASTERISK and not kode[0].isdigit(),
                               "wk": wk, "semua": wk + wj,
                               "persis": {norm(kode)} | {norm(i) for i in istilah}})

    def cari(self, q, maks=30):
        nq = norm(q)
        if not nq:
            return {"hasil": [], "jumlah": 0}
        toks = nq.split(" ")
        hasil = []
        for e in self.entri:
            if not all(any(w.startswith(t) for w in e["semua"]) for t in toks):
                continue
            if nq in e["persis"]:
                tingkat = 0
            elif all(any(w.startswith(t) for w in e["wk"]) for t in toks):
                tingkat = 1
            else:
                tingkat = 2
            hasil.append((tingkat, e))
        hasil.sort(key=lambda x: x[0])  # stabil: urutan kode tetap di dalam tingkat
        return {"hasil": [{"kode": e["kode"], "judul": e["judul"], "istilah": e["istilah"], "tanda": e["tanda"],
                           "asterisk": e["asterisk"], "tingkat": t} for t, e in hasil[:maks]], "jumlah": len(hasil)}

    def judul(self, kode):
        for e in self.entri:
            if e["kode"] == kode:
                return e
        return None


def _muat(nama):
    with open(os.path.join(P, nama), encoding="utf-8") as f:
        return [(r["kode"], r["judul"], [x for x in r["istilah"].split("|") if x], TANDA.get(r["versi"], 0))
                for r in csv.DictReader(f)]


_CACHE = {}


def indeks(tipe="ICD10"):
    if tipe not in _CACHE:
        _CACHE[tipe] = IndeksICD(_muat("icd10.csv" if tipe == "ICD10" else "icd9cm.csv"))
    return _CACHE[tipe]


def cari(q, tipe="ICD10", maks=30):
    return indeks(tipe).cari(q, maks)
