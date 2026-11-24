"""Bangun data ringkas untuk kalkulator HTML (web/) dari data/processed/.

web/data/kalkulator.json berisi:
  grup     : urutan kelompok tarif [regional, jenis_rs] (8 jenis RS x 5 regional + 5 RS khusus nasional)
  cbg      : {kode: [deskripsi, jenis_rawat, tarif[], halaman]}
             tarif[] = per grup (x kelas 1,2,3 untuk RI), dalam RATUSAN rupiah; null = "-"
             halaman = [halaman awal blok per grup, string digit offset per grup]
  topup    : [{k, d, c, t[], h[]}]  (k kode spesial, d varian deskripsi, c CBG; h halaman per nilai t)
  special  : {kode: [deskripsi, jenis]}
  trigger  : [{k, cbg[], icd10[], icd9[], hal[]}]

Pemakaian: python scripts/bangun_data_web.py
"""
import csv
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "web", "data", "kalkulator.json")

JENIS_RS = ["A PEMERINTAH", "A SWASTA", "B PEMERINTAH", "B SWASTA",
            "C PEMERINTAH", "C SWASTA", "D PEMERINTAH", "D SWASTA"]
NASIONAL = ["RSCM", "RSJP-HK", "RSK DHARMAIS", "RSAB-HK", "RSPON"]
GRUP = [[str(r), j] for r in range(1, 6) for j in JENIS_RS] + [["NASIONAL", n] for n in NASIONAL]
IDX = {tuple(g): i for i, g in enumerate(GRUP)}


def baca(nama):
    with open(os.path.join(P, nama), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def grup_key(r):
    if r["kelas_rs"] == "KHUSUS_NASIONAL":
        return IDX[("NASIONAL", r["nama_rs_khusus"])]
    return IDX[(r["regional"], f"{r['kelas_rs']} {r['kepemilikan']}")]


def ratus(v):
    if v in ("", None):
        return None
    n = int(v)
    assert n % 100 == 0
    return n // 100


def main():
    cbg = {r["kode_cbg"]: r for r in baca("cbg_group.csv")}
    nkelas = {k: (3 if r["jenis_rawat"] == "RI" else 1) for k, r in cbg.items()}
    tarif = {k: [None] * (len(GRUP) * nkelas[k]) for k in cbg}
    hal = {k: [None] * len(GRUP) for k in cbg}
    for r in baca("tarif_cbg.csv"):
        k = r["kode_cbg"]
        g = grup_key(r)
        kel = int(r["kelas_rawat"]) if r["kelas_rawat"] else 1
        tarif[k][g * nkelas[k] + (kel - 1)] = ratus(r["tarif"])
        hal[k][g] = int(r["sumber_halaman"])
    # halaman awal per (grup, jenis rawat) + offset satu digit per kode
    awal = defaultdict(lambda: 10 ** 9)
    for k in cbg:
        for g, h in enumerate(hal[k]):
            awal[(g, cbg[k]["jenis_rawat"])] = min(awal[(g, cbg[k]["jenis_rawat"])], h)
    awal_ri = [awal[(g, "RI")] for g in range(len(GRUP))]
    awal_rj = [awal[(g, "RJ")] for g in range(len(GRUP))]
    out_cbg = {}
    for k, r in cbg.items():
        base = awal_ri if r["jenis_rawat"] == "RI" else awal_rj
        off = "".join(str(hal[k][g] - base[g]) for g in range(len(GRUP)))
        assert all(c.isdigit() for c in off) and len(off) == len(GRUP)
        out_cbg[k] = [r["deskripsi"], r["jenis_rawat"], tarif[k], off]

    tp = {}
    for r in baca("tarif_topup.csv"):
        key = (r["kode_spesial"], r["deskripsi_spesial"], r["kode_cbg"])
        n = nkelas[r["kode_cbg"]]
        e = tp.setdefault(key, {"k": key[0], "d": key[1], "c": key[2],
                                "t": [None] * (len(GRUP) * n), "h": [None] * (len(GRUP) * n)})
        g = grup_key(r)
        kel = int(r["kelas_rawat"]) if r["kelas_rawat"] else 1
        e["t"][g * n + (kel - 1)] = ratus(r["tarif"])
        e["h"][g * n + (kel - 1)] = int(r["sumber_halaman"])  # satu grup bisa terbelah 2 halaman

    sp = {r["kode_spesial"]: [r["deskripsi"], r["jenis_spesial"]] for r in baca("special_cmg.csv")}
    trig = {}
    for r in baca("special_cmg_trigger.csv"):
        key = (r["kode_spesial"], r["sub_kriteria"])
        d = trig.setdefault(key, {"k": key[0], "cbg": [], "icd10": [], "icd9": [], "hal": set()})
        if r["kode_cbg"] not in d["cbg"]:
            d["cbg"].append(r["kode_cbg"])
        lst = {"ICD10": d["icd10"], "ICD9CM": d["icd9"]}.get(r["tipe_kode"])
        if lst is not None and r["kode"] not in lst:
            lst.append(r["kode"])
        d["hal"].update(int(x) for x in r["sumber_halaman"].split(","))
    for d in trig.values():
        d["hal"] = sorted(d["hal"])

    data = {"grup": GRUP, "halaman_awal": {"RI": awal_ri, "RJ": awal_rj}, "cbg": out_cbg,
            "topup": list(tp.values()), "special": sp, "trigger": list(trig.values())}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{OUT}: {os.path.getsize(OUT) / 1024:.0f} KB, {len(out_cbg)} CBG, {len(tp)} top up, {len(trig)} pemicu")


if __name__ == "__main__":
    main()
