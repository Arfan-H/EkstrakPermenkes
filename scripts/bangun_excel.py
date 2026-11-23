"""Tahap 2: normalisasi tabel mentah (hasil ekstrak_raw.py) menjadi Excel.

Sheet: "Top Up", "Tarif INA-CBG", "Gabungan".
Pemakaian: python bangun_excel.py <raw.pkl> <out.xlsx> [laporan.txt]
"""
import pickle
import re
import sys
from collections import Counter, defaultdict

import pandas as pd

KOLOM = ["halaman", "judul", "regional", "jenis_tabel", "jenis_rawat", "no",
         "kode_spesial", "deskripsi_spesial_cmg", "kode_ina_cbg",
         "deskripsi_kode_ina_cbg", "jenis_rs", "kelas_harga", "tarif"]

RS_KHUSUS = {
    "RUMAH SAKIT UMUM PUSAT DR. CIPTO MANGUNKUSUMO": "RSCM",
    "RUMAH SAKIT JANTUNG DAN PEMBULUH DARAH HARAPAN KITA": "RSJP-HK",
    "RUMAH SAKIT ANAK DAN BUNDA HARAPAN KITA": "RSAB-HK",
    "RUMAH SAKIT KANKER DHARMAIS": "RSK DHARMAIS",
    "RUMAH SAKIT PUSAT OTAK NASIONAL": "RSPON",
}
JENIS_RS_VALID = ({f"{k} {s}" for k in "ABCD" for s in ("PEMERINTAH", "SWASTA")}
                  | set(RS_KHUSUS.values()))
RE_KODE_INA = re.compile(r"^[A-Z]-\d-\d{2}-(?:I{1,3}|0)$")
RE_KODE_SPS = re.compile(r"^[A-Z]{2}-\d{2}-I{1,3}$")
RE_ANGKA = re.compile(r"^\d{1,3}(?:\.\d{3})*$")

laporan = []
peringatan = []


def bersih(s):
    if s is None:
        return None
    return " ".join(s.replace("\n", " ").split())


def tarif(s, ctx):
    v = (s or "").replace(" ", "").replace("\n", "")
    if v == "-":
        return "-"
    if not RE_ANGKA.match(v):
        peringatan.append(f"{ctx}: nilai tarif tidak valid {s!r}")
        return v
    return int(v.replace(".", ""))


def judul_dari(lines, halaman):
    """Ambil judul, regional, jenis_tabel, jenis_rawat dari baris di atas tabel."""
    j = {"judul": None, "regional": None, "jenis_tabel": None, "jenis_rawat": None}
    lain = []
    for l in lines:
        l = bersih(l)
        if l == "TARIF INA-CBG":
            j["judul"] = l
        elif re.fullmatch(r"REGIONAL \d", l):
            j["regional"] = l
        elif l == "TOP UP SPESIAL CMG" or l.startswith("RUMAH SAKIT"):
            j["jenis_tabel"] = l
        elif l in ("RAWAT INAP", "RAWAT JALAN"):
            j["jenis_rawat"] = l
        else:
            lain.append(l)
    if not j["judul"] or not j["jenis_tabel"]:
        peringatan.append(f"hal {halaman}: judul tidak lengkap {lines}")
    return j, lain


def jenis_rs_dari_tabel(jenis_tabel):
    m = re.fullmatch(r"RUMAH SAKIT KELAS ([ABCD]) (PEMERINTAH|SWASTA)", jenis_tabel)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return RS_KHUSUS[jenis_tabel]


# ---------------------------------------------------------------- Top Up
def proses_topup(pages):
    rec = []
    carry = None  # nilai kolom 0-3 terakhir dari halaman sebelumnya
    for pg in pages:
        h = pg["halaman"]
        j, lain = judul_dari(pg["judul_lines"], h)
        lain = [l for l in lain if not l.startswith("B. Besaran")]
        rows = pg["rows"]
        header = [bersih(c) for c in rows[0]]
        n = len(header)
        if n not in (9, 10):
            peringatan.append(f"hal {h}: jumlah kolom Top Up tak terduga {n}")
        # Nama jenis RS dari header kolom tarif (ambil 1-2 kata terakhir)
        jenis_rs = []
        for c in rows[0][5:]:
            parts = [p.strip() for p in c.split("\n") if p.strip()]
            nama = " ".join(parts)
            if nama not in JENIS_RS_VALID:
                peringatan.append(f"hal {h}: header jenis RS tak dikenal {nama!r}")
            jenis_rs.append(nama)
        cur = [None, None, None, None]
        first = True
        for r in rows[1:]:
            vals = list(r[:4])
            for i in range(4):
                v = vals[i]
                if v is None:  # bagian dari sel merge -> nilai di atasnya
                    vals[i] = cur[i]
                elif v.strip() == "":
                    if first and carry is not None:
                        vals[i] = carry[i]  # baris lanjutan dari halaman sebelumnya
                    elif i == 3 and cur[3] is not None and first is False:
                        peringatan.append(f"hal {h}: sel kode INA-CBG kosong di tengah tabel")
                        vals[i] = cur[i]
                    else:
                        peringatan.append(f"hal {h}: sel kolom {i} kosong {r}")
                        vals[i] = cur[i]
                else:
                    vals[i] = bersih(v)
                # kode INA-CBG baru tanpa NO baru: tetap ikut NO di atas
            if first and r[0] is not None and r[0].strip() == "" and carry is not None:
                laporan.append(
                    f"hal {h}: baris lanjutan -> NO {vals[0]} {vals[1]} '{vals[2]}' "
                    f"{vals[3]} kelas {bersih(r[4])} (diambil dari hal {h-1}); "
                    f"teks tersembunyi di header: {lain or rows[0][0]!r}")
                # cek silang dengan teks tersembunyi
                hid_no = (rows[0][0] or "").split("\n")[0]
                hid_ina = (rows[0][3] or "").replace("\n", "").replace("KODE INA-", "")
                if hid_no.strip() and hid_no.strip() != vals[0]:
                    peringatan.append(f"hal {h}: NO lanjutan {vals[0]} != teks tersembunyi {hid_no}")
                if hid_ina and sorted(hid_ina) != sorted(vals[3] + "CBG"):
                    peringatan.append(f"hal {h}: kode INA lanjutan {vals[3]} vs tersembunyi {hid_ina!r}")
            first = False
            cur = vals
            kelas = bersih(r[4]) or ""
            if kelas not in ("", "1", "2", "3"):
                peringatan.append(f"hal {h}: kelas rawat tak terduga {kelas!r}")
            if not RE_KODE_SPS.match(vals[1] or ""):
                peringatan.append(f"hal {h}: kode spesial aneh {vals[1]!r}")
            if not RE_KODE_INA.match(vals[3] or ""):
                peringatan.append(f"hal {h}: kode INA-CBG aneh {vals[3]!r}")
            for k, nama in enumerate(jenis_rs):
                rec.append({
                    "halaman": h, **j, "no": int(vals[0]), "kode_spesial": vals[1],
                    "deskripsi_spesial_cmg": vals[2], "kode_ina_cbg": vals[3],
                    "deskripsi_kode_ina_cbg": None, "jenis_rs": nama,
                    "kelas_harga": kelas or None,
                    "tarif": tarif(r[5 + k], f"hal {h} NO {vals[0]}"),
                })
        carry = cur
    return rec


# ---------------------------------------------------------- Tarif utama
def proses_utama(pages):
    rec = []
    for pg in pages:
        h = pg["halaman"]
        j, lain = judul_dari(pg["judul_lines"], h)
        lain = [l for l in lain if not l.startswith("III. BESARAN")]
        if lain:
            peringatan.append(f"hal {h}: teks lain di atas tabel {lain}")
        rows = pg["rows"]
        header = [bersih(c) for c in rows[0]]
        kelas_cols = []
        for c in header[3:]:
            if c == "TARIF INA-CBG":
                kelas_cols.append(None)
            elif re.fullmatch(r"TARIF KELAS [123]", c):
                kelas_cols.append(c.replace("TARIF ", ""))
            else:
                peringatan.append(f"hal {h}: header tarif tak dikenal {c!r}")
                kelas_cols.append(c)
        exp = 3 if j["jenis_rawat"] == "RAWAT INAP" else 1
        if len(kelas_cols) != exp:
            peringatan.append(f"hal {h}: jumlah kolom tarif {len(kelas_cols)} != {exp}")
        jrs = jenis_rs_dari_tabel(j["jenis_tabel"])
        for r in rows[1:]:
            if any(c is None for c in r) or not (r[0] or "").strip().isdigit():
                peringatan.append(f"hal {h}: baris tak terduga {r}")
                continue
            kode = bersih(r[1])
            if not RE_KODE_INA.match(kode):
                peringatan.append(f"hal {h}: kode INA-CBG aneh {kode!r}")
            desk = bersih(r[2])
            if "\n" in (r[2] or ""):
                laporan.append(f"hal {h}: deskripsi multi-baris digabung -> NO {r[0]} {kode} '{desk}'")
            for k, kelas in enumerate(kelas_cols):
                rec.append({
                    "halaman": h, **j, "no": int(r[0]), "kode_spesial": None,
                    "deskripsi_spesial_cmg": None, "kode_ina_cbg": kode,
                    "deskripsi_kode_ina_cbg": desk, "jenis_rs": jrs,
                    "kelas_harga": kelas, "tarif": tarif(r[3 + k], f"hal {h} NO {r[0]}"),
                })
    return rec


# ------------------------------------------------------------- Validasi
def validasi(top, uta):
    # Tarif utama: tiap blok NO harus berurutan dan daftar kode identik
    blok = defaultdict(list)
    for x in uta:
        blok[(x["regional"], x["jenis_tabel"], x["jenis_rawat"])].append(x)
    acuan = {}
    for key, xs in blok.items():
        per_no = {}
        for x in xs:
            per_no.setdefault(x["no"], (x["kode_ina_cbg"], x["deskripsi_kode_ina_cbg"]))
        nos = sorted(per_no)
        exp_n = 786 if key[2] == "RAWAT INAP" else 289
        if nos != list(range(1, exp_n + 1)):
            peringatan.append(f"blok {key}: NO tidak lengkap ({len(nos)} dari {exp_n})")
        kelas_n = 3 if key[2] == "RAWAT INAP" else 1
        if len(xs) != exp_n * kelas_n:
            peringatan.append(f"blok {key}: jumlah baris {len(xs)} != {exp_n*kelas_n}")
        daftar = [per_no[n][0] for n in nos]
        acuan.setdefault(key[2], daftar)
        if daftar != acuan[key[2]]:
            peringatan.append(f"blok {key}: urutan kode INA-CBG berbeda dari blok pertama")
    laporan.append(f"Tarif utama: {len(blok)} blok, {len(uta)} baris")

    # Top Up: tiap kombinasi (no, kode spesial, deskripsi, kode INA) kelasnya 1,2,3 atau kosong
    blok = defaultdict(list)
    for x in top:
        blok[(x["regional"], x["halaman"] >= 80)].append(x)
    struktur = {}
    for key, xs in blok.items():
        grup = defaultdict(list)
        rs = sorted({x["jenis_rs"] for x in xs})
        for x in xs:
            if x["jenis_rs"] == rs[0]:
                grup[(x["no"], x["kode_spesial"], x["deskripsi_spesial_cmg"], x["kode_ina_cbg"])].append(x["kelas_harga"])
        for g, kl in grup.items():
            if kl not in (["1", "2", "3"], [None]):
                peringatan.append(f"Top Up {key} {g}: urutan kelas rawat {kl}")
        nos = sorted({g[0] for g in grup})
        if nos != list(range(1, 37)):
            peringatan.append(f"Top Up {key}: NO tidak lengkap {nos}")
        struktur[key] = [(g[0], g[1], g[3], tuple(kl)) for g, kl in grup.items()]
    ref = struktur[("REGIONAL 1", False)]
    for key, s in struktur.items():
        if s != ref:
            beda = [(a, b) for a, b in zip(ref, s) if a != b][:5]
            laporan.append(f"Top Up {key}: struktur berbeda dari Regional 1 Pemerintah/Swasta, contoh: {beda} (len {len(s)} vs {len(ref)})")
    laporan.append(f"Top Up: {len(blok)} blok, {len(top)} baris")


def tulis_excel(df_top, df_uta, out):
    df_gab = pd.concat([df_top, df_uta], ignore_index=True)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        for nama, df in (("Top Up", df_top), ("Tarif INA-CBG", df_uta), ("Gabungan", df_gab)):
            df.to_excel(xw, sheet_name=nama, index=False)
            ws = xw.sheets[nama]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            lebar = {"A": 9, "B": 15, "C": 12, "D": 40, "E": 14, "F": 6, "G": 13,
                     "H": 34, "I": 13, "J": 60, "K": 15, "L": 12, "M": 14}
            for col, w in lebar.items():
                ws.column_dimensions[col].width = w
            for cell in ws["M"][1:]:
                if isinstance(cell.value, int):
                    cell.number_format = "#,##0"
                else:
                    cell.alignment = cell.alignment.copy(horizontal="right")


def main():
    pages = pickle.load(open(sys.argv[1], "rb"))
    pages.sort(key=lambda p: p["halaman"])
    top_pages = [p for p in pages if 40 <= p["halaman"] <= 83]
    uta_pages = [p for p in pages if p["halaman"] >= 92]
    top = proses_topup(top_pages)
    uta = proses_utama(uta_pages)
    validasi(top, uta)
    df_top = pd.DataFrame(top, columns=KOLOM)
    df_uta = pd.DataFrame(uta, columns=KOLOM)
    if len(sys.argv) > 3:
        with open(sys.argv[3], "w") as f:
            f.write("== PERINGATAN ==\n" + "\n".join(peringatan) + "\n\n== LAPORAN ==\n" + "\n".join(laporan) + "\n")
    print(f"peringatan: {len(peringatan)}")
    for p in peringatan[:40]:
        print("  !", p)
    tulis_excel(df_top, df_uta, sys.argv[2])
    print("Excel ditulis:", sys.argv[2], len(df_top), len(df_uta))


if __name__ == "__main__":
    main()
