"""ETL: workbook hasil ekstraksi -> tabel bersih di data/processed/.

Langkah normalisasi (lihat CLAUDE.md):
1. tarif "-" -> kosong + tersedia=False (bukan 0)
2. kelas_rawat -> 1/2/3, kosong untuk rawat jalan
3. regional kosong (RS khusus nasional) -> "NASIONAL"
4. Top Up dilengkapi jenis_rawat & deskripsi CBG dari tabel tarif
5. jenis_rs -> kelas_rs + kepemilikan + nama_rs_khusus
6. kode CBG diurai -> cmg, case_type, nomor_cbg, severity
7. kode spesial diurai -> jenis_spesial, nomor, level

Pemakaian: python -m inacbg.etl [workbook.xlsx] [folder_output]
"""
import os
import re
import sys

import pandas as pd

RE_CBG = re.compile(r"^([A-Z])-(\d)-(\d{2})-(I|II|III|0)$")
RE_SPS = re.compile(r"^(DD|RR|YY|II)-(\d{2})-(I|II|III)$")
RS_KHUSUS_NASIONAL = ["RSCM", "RSJP-HK", "RSK DHARMAIS", "RSAB-HK", "RSPON"]
JENIS_SPESIAL = {"DD": "special drug", "RR": "special prosthesis",
                 "YY": "special procedure", "II": "special investigation"}

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_XLSX = os.path.join(ROOT, "output", "Tarif_INA-CBG_Permenkes_3_2023.xlsx")
DEFAULT_OUT = os.path.join(ROOT, "data", "processed")


def pecah_jenis_rs(jrs):
    if jrs in RS_KHUSUS_NASIONAL:
        return "KHUSUS_NASIONAL", None, jrs
    kelas, milik = jrs.split(" ")
    return kelas, milik, None


def normalisasi(df, sumber):
    out = pd.DataFrame()
    out["kode_cbg"] = df["kode_ina_cbg"]
    parts = df["jenis_rs"].map(pecah_jenis_rs)
    out["kelas_rs"] = parts.map(lambda p: p[0])
    out["kepemilikan"] = parts.map(lambda p: p[1])
    out["nama_rs_khusus"] = parts.map(lambda p: p[2])
    reg = df["regional"].str.replace("REGIONAL ", "", regex=False)
    # RS khusus nasional: tarifnya nasional. (Di halaman Top Up RS khusus,
    # PDF menulis "REGIONAL 1"; disimpan di regional_pdf.)
    out["regional"] = reg.where(out["kelas_rs"] != "KHUSUS_NASIONAL", "NASIONAL")
    out["regional_pdf"] = df["regional"]
    kelas = df["kelas_harga"].astype("string").str.extract(r"(\d)")[0]
    out["kelas_rawat"] = pd.to_numeric(kelas, errors="coerce").astype("Int64")
    t = df["tarif"].astype(str)
    out["tersedia"] = t != "-"
    out["tarif"] = pd.to_numeric(t.where(t != "-"), errors="coerce").astype("Int64")
    out["sumber_halaman"] = df["halaman"].astype(int)
    if sumber == "topup":
        out.insert(0, "kode_spesial", df["kode_spesial"])
        out.insert(1, "deskripsi_spesial", df["deskripsi_spesial_cmg"])
    return out


def bangun(xlsx=DEFAULT_XLSX, out_dir=DEFAULT_OUT):
    tarif = pd.read_excel(xlsx, sheet_name="Tarif INA-CBG", dtype={"kelas_harga": str})
    topup = pd.read_excel(xlsx, sheet_name="Top Up", dtype={"kelas_harga": str})

    # cbg_group
    g = tarif.drop_duplicates("kode_ina_cbg")[["kode_ina_cbg", "deskripsi_kode_ina_cbg", "jenis_rawat"]]
    m = g["kode_ina_cbg"].str.extract(RE_CBG)
    if m.isna().any().any():
        raise ValueError("ada kode CBG yang tidak lolos regex")
    cbg = pd.DataFrame({
        "kode_cbg": g["kode_ina_cbg"], "deskripsi": g["deskripsi_kode_ina_cbg"],
        "cmg": m[0], "case_type": m[1].astype(int), "nomor_cbg": m[2], "severity": m[3],
        "jenis_rawat": g["jenis_rawat"].map({"RAWAT INAP": "RI", "RAWAT JALAN": "RJ"}),
    }).sort_values("kode_cbg")

    tc = normalisasi(tarif, "cbg")
    tt = normalisasi(topup, "topup")

    # special_cmg
    s = topup.drop_duplicates(["kode_spesial", "deskripsi_spesial_cmg"])[["kode_spesial", "deskripsi_spesial_cmg"]]
    varian = s.groupby("kode_spesial")["deskripsi_spesial_cmg"].apply(list)
    ms = varian.index.to_series().str.extract(RE_SPS)
    if ms.isna().any().any():
        raise ValueError("ada kode spesial yang tidak lolos regex")
    sp = pd.DataFrame({
        "kode_spesial": varian.index,
        "deskripsi": [" / ".join(v) for v in varian],
        "varian": ["|".join(v) if len(v) > 1 else "" for v in varian],
        "jenis_spesial": ms[0].map(JENIS_SPESIAL).values,
        "prefix": ms[0].values, "nomor": ms[1].values, "level": ms[2].values,
    })

    os.makedirs(out_dir, exist_ok=True)
    cbg.to_csv(os.path.join(out_dir, "cbg_group.csv"), index=False)
    tc.to_csv(os.path.join(out_dir, "tarif_cbg.csv"), index=False)
    tt.to_csv(os.path.join(out_dir, "tarif_topup.csv"), index=False)
    sp.to_csv(os.path.join(out_dir, "special_cmg.csv"), index=False)
    print(f"cbg_group {len(cbg)} | tarif_cbg {len(tc)} | tarif_topup {len(tt)} | special_cmg {len(sp)}")
    return cbg, tc, tt, sp


if __name__ == "__main__":
    bangun(*sys.argv[1:3])
