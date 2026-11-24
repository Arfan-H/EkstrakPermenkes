"""Ekstrak Lampiran I.A PMK 3/2023 (hal. PDF 31-39): Kriteria Pembayaran
Tambahan (Top Up) pada Special CMG -> pemicu ICD-10 / ICD-9-CM per kode CBG.

- Hal. 31 berupa gambar scan (tanpa lapisan teks) -> ditranskrip manual
  (lihat HAL_31 di bawah), sudah dicocokkan dengan gambar 200 dpi.
- Hal. 32-39 diekstrak dari tabel PDF (pdfplumber). Sel merge yang terpotong
  di batas halaman ditangani dengan isi_sel_terbuka() dari ekstrak_raw.py.

Output (long format, satu baris per kode):
  data/processed/special_cmg_trigger.csv
    kode_spesial, deskripsi_spesial_cmg, sub_kriteria, kode_cbg,
    tipe_kode (ICD10|ICD9CM|-), kode, sumber_halaman

Arti sub_kriteria: satu kode spesial bisa punya beberapa kombinasi
(CBG x ICD-10 x ICD-9-CM), mis. DD-11-II punya 2 (L-1-20-* dan S-4-16-*).
Baris dengan tipe_kode '-' menandai kombinasi yang kolom ICD-nya '-'.

Pemakaian: python scripts/ekstrak_lampiran_ia.py "<PDF asli>" data/processed/special_cmg_trigger.csv
"""
import csv
import os
import re
import sys

import pdfplumber

sys.path.insert(0, os.path.dirname(__file__))
from ekstrak_raw import isi_sel_terbuka  # noqa: E402

# Transkripsi manual hal. 31 (scan). Format sama dengan baris tabel hasil ekstraksi:
# [NO, KODE SPECIAL, DESKRIPSI, KODE GROUP INA-CBG, ICD-10, ICD-9-CM]
HAL_31 = [
    ["1", "DD-01-I", "Streptokinase", "I-4-10-I\nI-4-10-II\nI-4-10-III",
     "I21.0,\nI21.1,\nI21.2,\nI21.3,\nI21.4,\nI21.9,\nI23.3", "-"],
    ["2", "DD-02-II", "Deferiprone", "D-4-13-I\nD-4-13-II\nD-4-13-III", "D56.1", "-"],
    ["3", "DD-03-II", "Deferoksamin", "D-4-13-I\nD-4-13-II\nD-4-13-III", "D56.1", "-"],
    ["4", "DD-04-II", "Deferasirox", "D-4-13-I\nD-4-13-II\nD-4-13-III", "D56.1", "-"],
    ["5", "DD-05-II", "Human Albumin\nfor Septicaemia", "A-4-10-I\nA-4-10-II", "A02.1,\nA20.7,", "-"],
]

RE_CBG = re.compile(r"[A-Z]-\d-\d{2}-(?:III|II|I|0)")
RE_ICD10 = re.compile(r"^[A-Z]\d{2}(?:\.\d{1,2})?$")
RE_ICD9 = re.compile(r"^\d{2}(?:\.\d{1,2})?$")


def bersih(s):
    return " ".join((s or "").split())


def pecah_kode(s, regex, ctx):
    s = (s or "").strip()
    if s in ("", "-"):
        return []
    kode = [k for k in re.split(r"[,\s]+", s) if k]
    for k in kode:
        if not regex.match(k):
            raise ValueError(f"{ctx}: kode tidak valid {k!r} dari {s!r}")
    return kode


def baca_halaman(pdf_path):
    pages = {31: HAL_31}
    with pdfplumber.open(pdf_path) as pdf:
        for h in range(32, 40):
            pg = pdf.pages[h - 1].dedupe_chars(tolerance=0.05)
            tab = pg.find_tables()[0]
            rows = tab.extract()
            isi_sel_terbuka(pg, tab, rows)
            pages[h] = rows[1:]  # buang header
    return pages


def susun(pages):
    """Gabungkan baris antar-halaman menjadi daftar kombinasi."""
    kombinasi = []  # dict: no, kode, desk, cbg[], icd10[], icd9[], hal{tipe: set}
    for h in sorted(pages):
        for idx, r in enumerate(pages[h]):
            no, kode, desk, cbg, d10, d9 = (r + [None] * 6)[:6]
            lanjutan = idx == 0 and (no or "").strip() == "" and no is not None
            if lanjutan:  # baris lanjutan dari halaman sebelumnya
                k = kombinasi[-1]
            elif no is None and kode is None:  # item sama, kombinasi CBG baru
                prev = kombinasi[-1]
                k = {"no": prev["no"], "kode": prev["kode"], "desk": prev["desk"],
                     "cbg": [], "icd10": [], "icd9": [], "hal": set()}
                kombinasi.append(k)
            else:
                k = {"no": bersih(no), "kode": bersih(kode), "desk": bersih(desk),
                     "cbg": [], "icd10": [], "icd9": [], "hal": set()}
                kombinasi.append(k)
            ctx = f"hal {h} item {k['no']}"
            k["cbg"] += RE_CBG.findall(cbg or "")
            k["icd10"] += [(c, h) for c in pecah_kode(d10, RE_ICD10, ctx)]
            k["icd9"] += [(c, h) for c in pecah_kode(d9, RE_ICD9, ctx)]
            k["hal"].add(h)
    return kombinasi


def main():
    pdf_path, out = sys.argv[1], sys.argv[2]
    komb = susun(baca_halaman(pdf_path))
    rows = []
    sub = {}
    for k in komb:
        sub[k["kode"]] = sub.get(k["kode"], 0) + 1
        hal = ",".join(str(x) for x in sorted(k["hal"]))
        for cbg in k["cbg"]:
            if not k["icd10"] and not k["icd9"]:
                rows.append([k["kode"], k["desk"], sub[k["kode"]], cbg, "-", "-", hal])
            for c, h in k["icd10"]:
                rows.append([k["kode"], k["desk"], sub[k["kode"]], cbg, "ICD10", c, h])
            for c, h in k["icd9"]:
                rows.append([k["kode"], k["desk"], sub[k["kode"]], cbg, "ICD9CM", c, h])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kode_spesial", "deskripsi_spesial_cmg", "sub_kriteria", "kode_cbg",
                    "tipe_kode", "kode", "sumber_halaman"])
        w.writerows(rows)
    # ringkasan untuk dicek
    print(f"{len(komb)} kombinasi, {len({k['kode'] for k in komb})} kode spesial, {len(rows)} baris")
    for k in komb:
        print(f"  {k['no']:>2} {k['kode']:<10} {k['desk'][:38]:<38} CBG={','.join(k['cbg'])} "
              f"ICD10={len(k['icd10'])} ICD9={len(k['icd9'])} hal={sorted(k['hal'])}")


if __name__ == "__main__":
    main()
