"""Bangun daftar kode ICD-10 dan ICD-9-CM untuk pencarian nama penyakit/tindakan.

Sumber (lihat sumber/SUMBER.md):
  sumber/icd/icd_10_v2019.xml      ICD-10 WHO versi 2019 (ClaML yang disederhanakan, paket simple_icd_10, CC0)
  sumber/icd/CMS32_DESC_LONG_SG.txt ICD-9-CM volume 3 (prosedur) versi 32, CMS (domain publik pemerintah AS)
  data/manual/istilah_icd.csv       istilah Indonesia/awam -> kode, disusun sendiri

E-Klaim memakai ICD-10 versi 2010. Beberapa kode 2010 dipindah atau dipecah pada pembaruan WHO
2016/2019 (mis. hemoroid I84 -> K64, fibrilasi atrium I48 dipecah, apendisitis K35.9 -> K35.8).
Kode 2010 itu ditambahkan dari KODE_2010 agar tetap bisa dicari.

Keluaran:
  data/processed/icd10.csv, data/processed/icd9cm.csv  (kode, judul, versi)
  web/data/icd.json  {icd10: [[kode, judul, tanda?]], icd9: [[kode, judul]], istilah10/istilah9: {kode: [istilah]}}
                     tanda 1 = kode ICD-10 2010 (tidak ada di 2019), 2 = kode 2019 yang belum ada di 2010

Pemakaian: python scripts/bangun_icd.py
"""
import csv
import json
import os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMBER = os.path.join(ROOT, "sumber", "icd")
OUT = os.path.join(ROOT, "data", "processed")
WEB = os.path.join(ROOT, "web", "data", "icd.json")

# kode ICD-10 versi 2010 yang tidak ada (lagi) sebagai kode akhir di versi 2019
KODE_2010 = {
    "I84.0": "Internal thrombosed haemorrhoids",
    "I84.1": "Internal haemorrhoids with other complications",
    "I84.2": "Internal haemorrhoids without complication",
    "I84.3": "External thrombosed haemorrhoids",
    "I84.4": "External haemorrhoids with other complications",
    "I84.5": "External haemorrhoids without complication",
    "I84.6": "Residual haemorrhoidal skin tags",
    "I84.7": "Unspecified thrombosed haemorrhoids",
    "I84.8": "Unspecified haemorrhoids with other complications",
    "I84.9": "Unspecified haemorrhoids without complication",
    "I48": "Atrial fibrillation and flutter",
    "K35.0": "Acute appendicitis with generalized peritonitis",
    "K35.1": "Acute appendicitis with peritoneal abscess",
    "K35.9": "Acute appendicitis, unspecified",
    "A90": "Dengue fever [classical dengue]",
    "A91": "Dengue haemorrhagic fever",
    "B18.1": "Chronic viral hepatitis B without delta-agent",
    "K58.0": "Irritable bowel syndrome with diarrhoea",
    "K58.9": "Irritable bowel syndrome without diarrhoea",
}
# kode 2019 yang diketahui belum ada di ICD-10 2010 (pengganti kode di atas); ditandai di keluaran
BARU_SETELAH_2010 = ("A97", "K64", "I48.", "K35.2", "K35.3", "K35.8", "K58.1", "K58.2", "K58.3", "K58.8", "B18.1", "U0")


def icd10_2019():
    """Kode akhir (tanpa anak) ICD-10 2019: subkategori, dan kategori tanpa subkategori."""
    root = ET.parse(os.path.join(SUMBER, "icd_10_v2019.xml")).getroot()
    out = {}

    def jalan(el):
        for it in el.findall("item"):
            tipe, kode = it.get("type"), it.findtext("name")
            anak = it.findall("item")
            if tipe in ("category", "subcategory") and not anak:
                out[kode] = " ".join(it.findtext("description").split())
            jalan(it)
    jalan(root)
    return out


def icd9cm():
    out = {}
    with open(os.path.join(SUMBER, "CMS32_DESC_LONG_SG.txt"), encoding="latin-1") as f:
        for baris in f:
            baris = baris.rstrip("\r\n")
            if not baris.strip():
                continue
            kode, judul = baris.split(" ", 1)
            out[kode[:2] + "." + kode[2:]] = " ".join(judul.split())
    return out


def istilah():
    out = {"ICD10": {}, "ICD9CM": {}}
    with open(os.path.join(ROOT, "data", "manual", "istilah_icd.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lst = [x.strip() for x in r["istilah"].split("|") if x.strip()]
            assert r["kode"] not in out[r["tipe"]], f"kode ganda di istilah_icd.csv: {r['kode']}"
            out[r["tipe"]][r["kode"]] = lst
    return out


def main():
    i10 = icd10_2019()
    versi = {k: ("2019 (setelah 2010)" if k.startswith(BARU_SETELAH_2010) else "2010/2019") for k in i10}
    for k, v in KODE_2010.items():
        assert k not in i10, f"{k} sudah ada di 2019"
        i10[k] = v
        versi[k] = "2010"
    i9 = icd9cm()
    ist = istilah()
    salah = [("ICD10", k) for k in ist["ICD10"] if k not in i10] + [("ICD9CM", k) for k in ist["ICD9CM"] if k not in i9]
    if salah:
        raise SystemExit("Kode istilah tidak ditemukan di daftar resmi: " + ", ".join(f"{t} {k}" for t, k in salah))

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "icd10.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kode", "judul", "versi", "istilah"])
        for k in sorted(i10):
            w.writerow([k, i10[k], versi[k], "|".join(ist["ICD10"].get(k, []))])
    with open(os.path.join(OUT, "icd9cm.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kode", "judul", "versi", "istilah"])
        for k in sorted(i9):
            w.writerow([k, i9[k], "32", "|".join(ist["ICD9CM"].get(k, []))])

    tanda = {"2010/2019": 0, "2010": 1, "2019 (setelah 2010)": 2}
    data = {"icd10": [[k, i10[k]] + ([tanda[versi[k]]] if tanda[versi[k]] else []) for k in sorted(i10)], "icd9": [[k, i9[k]] for k in sorted(i9)],
            "istilah10": ist["ICD10"], "istilah9": ist["ICD9CM"]}
    os.makedirs(os.path.dirname(WEB), exist_ok=True)
    with open(WEB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"ICD-10: {len(i10)} kode ({len(KODE_2010)} dari versi 2010), ICD-9-CM: {len(i9)} kode, "
          f"istilah: {len(ist['ICD10'])} diagnosis + {len(ist['ICD9CM'])} prosedur; {WEB}: {os.path.getsize(WEB) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
