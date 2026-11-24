"""Ekstrak tabel acuan dari Permenkes 26/2021 (Pedoman INA-CBG).

- Tabel 1 (hal. 11): Casemix Main Groups (CMG)      -> data/processed/cmg.csv
- Tabel 2 (hal. 12): Case Group (digit ke-2 kode)   -> data/processed/case_group.csv
- Tabel 4 (hal. 14-20): Special CMG + pemicu ICD    -> dibandingkan dengan
  data/processed/special_cmg_trigger.csv (Lampiran I.A PMK 3/2023), laporan
  ke output/banding_special_cmg_pmk26_vs_pmk3.txt

Pemakaian: python scripts/ekstrak_pmk26.py "Permenkes Nomor 26 Tahun 2021.pdf"
"""
import csv
import os
import re
import sys
from collections import defaultdict

import pdfplumber

sys.path.insert(0, os.path.dirname(__file__))
from ekstrak_raw import isi_sel_terbuka  # noqa: E402
from ekstrak_lampiran_ia import RE_ICD9, RE_ICD10, RE_CBG, pecah_kode, bersih  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")


def tabel_cmg(pdf):
    """Tabel 1: NO, deskripsi (bisa 2 baris), kode CMG."""
    rows = pdf.pages[10].dedupe_chars(tolerance=0.05).find_tables()[0].extract()
    out = []
    for r in rows[1:]:
        no, desk, kode = (bersih(c) for c in r[:3])
        if not no.isdigit():
            raise ValueError(f"baris Tabel 1 tak terduga: {r}")
        out.append({"no": int(no), "kode_cmg": kode, "deskripsi": desk.replace("Deleiveries", "Deleiveries"),
                    "sumber_halaman": 11})
    return out


def tabel_case_group(pdf):
    teks = pdf.pages[11].extract_text()
    out = []
    for m in re.finditer(r"^\s*(\d)\s+((?:Prosedur|Rawat|Error)[^\n]*)$", teks, re.M):
        out.append({"case_group": int(m.group(1)), "deskripsi": bersih(m.group(2)), "sumber_halaman": 12})
    if [r["case_group"] for r in out] != [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]:
        raise ValueError(f"Tabel 2 tidak lengkap: {out}")
    return out


def tabel_special(pdf):
    """Tabel 4 hal. 14-20, digabung seperti Lampiran I.A (baris lanjutan, sel merge)."""
    komb = []
    for h in range(14, 21):
        pg = pdf.pages[h - 1].dedupe_chars(tolerance=0.05)
        tabs = [t for t in pg.find_tables() if len(t.columns) >= 6]
        if not tabs:
            continue
        tab = tabs[0]
        rows = tab.extract()
        isi_sel_terbuka(pg, tab, rows)
        for idx, r in enumerate(rows):
            if r[0] and "NO" in r[0]:
                continue
            no, kode, desk, cbg, d10, d9 = (r + [None] * 6)[:6]
            if idx <= 1 and (no or "").strip() == "" and no is not None and komb:
                k = komb[-1]
            elif no is None and kode is None and komb:
                p = komb[-1]
                k = {"no": p["no"], "kode": p["kode"], "desk": p["desk"], "cbg": [], "icd10": [], "icd9": [], "hal": set()}
                komb.append(k)
            else:
                k = {"no": bersih(no), "kode": re.sub(r"\s+", "", kode or ""), "desk": bersih(desk),
                     "cbg": [], "icd10": [], "icd9": [], "hal": set()}
                komb.append(k)
            ctx = f"hal {h} item {k['no']}"
            k["cbg"] += RE_CBG.findall(cbg or "")
            k["icd10"] += pecah_kode(d10, RE_ICD10, ctx)
            k["icd9"] += pecah_kode(d9, RE_ICD9, ctx)
            k["hal"].add(h)
    return komb


def per_kode(komb_or_rows, dari_csv=False):
    d = defaultdict(lambda: {"cbg": set(), "icd10": set(), "icd9": set()})
    if dari_csv:
        for r in komb_or_rows:
            x = d[r["kode_spesial"]]
            x["cbg"].add(r["kode_cbg"])
            if r["tipe_kode"] == "ICD10":
                x["icd10"].add(r["kode"])
            elif r["tipe_kode"] == "ICD9CM":
                x["icd9"].add(r["kode"])
    else:
        for k in komb_or_rows:
            x = d[k["kode"]]
            x["cbg"].update(k["cbg"]); x["icd10"].update(k["icd10"]); x["icd9"].update(k["icd9"])
    return d


def main():
    pdf_path = sys.argv[1]
    with pdfplumber.open(pdf_path) as pdf:
        cmg = tabel_cmg(pdf)
        cg = tabel_case_group(pdf)
        sp = tabel_special(pdf)
    with open(os.path.join(OUT, "cmg.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["no", "kode_cmg", "deskripsi", "sumber_halaman"]); w.writeheader(); w.writerows(cmg)
    with open(os.path.join(OUT, "case_group.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["case_group", "deskripsi", "sumber_halaman"]); w.writeheader(); w.writerows(cg)
    print(f"cmg.csv {len(cmg)} baris, case_group.csv {len(cg)} baris, Tabel 4: {len(sp)} kombinasi")

    # bandingkan Tabel 4 PMK 26/2021 dengan Lampiran I.A PMK 3/2023
    a = per_kode(sp)
    with open(os.path.join(OUT, "special_cmg_trigger.csv"), encoding="utf-8") as f:
        b = per_kode(list(csv.DictReader(f)), dari_csv=True)
    lines = ["Perbandingan Special CMG: Tabel 4 Permenkes 26/2021 (hal. 14-20) vs Lampiran I.A Permenkes 3/2023 (hal. 31-39)",
             f"Kode spesial di PMK 26/2021: {len(a)}; di PMK 3/2023: {len(b)}", ""]
    for k in sorted(set(a) | set(b)):
        if k not in a:
            lines.append(f"{k}: hanya di PMK 3/2023"); continue
        if k not in b:
            lines.append(f"{k}: hanya di PMK 26/2021"); continue
        for f in ("cbg", "icd10", "icd9"):
            plus, minus = sorted(b[k][f] - a[k][f]), sorted(a[k][f] - b[k][f])
            if plus or minus:
                lines.append(f"{k} {f}: PMK 3/2023 menambah {plus or '-'}; tidak ada lagi di PMK 3/2023 {minus or '-'}")
    sama = [k for k in sorted(set(a) & set(b)) if all(a[k][f] == b[k][f] for f in ("cbg", "icd10", "icd9"))]
    lines += ["", f"Identik di kedua peraturan ({len(sama)}): {', '.join(sama)}"]
    path = os.path.join(ROOT, "output", "banding_special_cmg_pmk26_vs_pmk3.txt")
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
