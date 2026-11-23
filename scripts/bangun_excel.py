"""Tahap 2: normalisasi tabel mentah (hasil ekstrak_raw.py) menjadi Excel.

Sheet: "Top Up", "Tarif INA-CBG", "Gabungan".
Pemakaian: python bangun_excel.py <raw.pkl> <out.xlsx> [laporan.txt]
"""
import pickle
import re
import sys
from collections import Counter, defaultdict

import pandas as pd
from openpyxl.styles import Alignment

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
LANJUT = "<<LANJUT_HAL_BERIKUTNYA>>"  # penanda dari ekstrak_raw.py
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
    pecah = []
    for l in lines:
        l = bersih(l)
        # teks tersembunyi kadang menempel di baris judul "TOP UP SPESIAL CMG"
        if l.endswith("TOP UP SPESIAL CMG") and l != "TOP UP SPESIAL CMG":
            pecah += [l[: -len("TOP UP SPESIAL CMG")].strip(), "TOP UP SPESIAL CMG"]
        else:
            pecah.append(l)
    for l in pecah:
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
    """Normalisasi tabel Top Up. Sel merge (None) diisi nilai di atasnya.
    Batas halaman:
      - sel kosong ('') di baris pertama halaman  -> lanjutan item dari halaman sebelumnya
      - penanda LANJUT di bawah halaman           -> isinya tertulis di halaman berikutnya
    """
    logis = []  # baris logis: dict(h, j, jenis_rs, vals, kelas, tarif_raw)
    carry = None
    pending = []  # baris dengan penanda LANJUT yang menunggu halaman berikutnya
    for pg in pages:
        h = pg["halaman"]
        j, lain = judul_dari(pg["judul_lines"], h)
        lain = [l for l in lain if not l.startswith("B. Besaran")]
        rows = pg["rows"]
        jenis_rs = []
        for c in rows[0][5:]:
            nama = " ".join(p.strip() for p in c.split("\n") if p.strip())
            if nama not in JENIS_RS_VALID:
                peringatan.append(f"hal {h}: header jenis RS tak dikenal {nama!r}")
            jenis_rs.append(nama)
        if len(rows[0]) not in (9, 10):
            peringatan.append(f"hal {h}: jumlah kolom Top Up tak terduga {len(rows[0])}")
        cur = [None] * 4
        for idx, r in enumerate(rows[1:]):
            first = idx == 0
            vals = list(r[:4])
            for i in range(4):
                v = vals[i]
                if v is None:
                    vals[i] = cur[i]
                elif v == LANJUT:
                    vals[i] = LANJUT
                elif v.strip() == "":
                    if first and carry is not None:
                        vals[i] = carry[i]
                        if carry[i] == LANJUT:
                            peringatan.append(f"hal {h}: kolom {i} kosong di kedua sisi batas halaman")
                    else:
                        peringatan.append(f"hal {h}: sel kolom {i} kosong {r}")
                        vals[i] = cur[i]
                else:
                    vals[i] = bersih(v)
            if first:
                # selesaikan penanda LANJUT dari halaman sebelumnya
                for row in pending:
                    for i in range(4):
                        if row["vals"][i] == LANJUT:
                            row["vals"][i] = vals[i]
                    laporan.append(
                        f"hal {row['h']}: baris terakhir (kelas {row['kelas']}) isinya tertulis di hal {h} -> "
                        f"NO {row['vals'][0]} {row['vals'][1]} '{row['vals'][2]}' {row['vals'][3]}")
                pending = []
                if r[0] is not None and r[0].strip() == "" and carry is not None:
                    laporan.append(
                        f"hal {h}: baris pertama lanjutan dari hal {h-1} -> NO {vals[0]} {vals[1]} "
                        f"'{vals[2]}' {vals[3]} kelas {bersih(r[4])}")
                    hid = [l for l in lain if re.match(r"^\d+ [A-Z]{2}-\d{2}-I+ ", l)]
                    if hid:
                        hn, hk, hd = hid[0].split(" ", 2)
                        if (hn, hk, hd.replace(" ", "")) != (vals[0], vals[1], vals[2].replace(" ", "")):
                            peringatan.append(f"hal {h}: baris lanjutan {vals[:3]} != teks tersembunyi {hid[0]!r}")
                        else:
                            laporan.append(f"hal {h}:   cocok dengan teks tersembunyi {hid[0]!r}")
                    hid_ina = (rows[0][3] or "").replace("\n", "").replace("KODE INA-", "")
                    if len(hid_ina) > 3:
                        if sorted(hid_ina) != sorted(vals[3] + "CBG"):
                            peringatan.append(f"hal {h}: kode INA lanjutan {vals[3]} vs tersembunyi {hid_ina!r}")
                        else:
                            laporan.append(f"hal {h}:   kode INA {vals[3]} cocok dengan teks tersembunyi {hid_ina!r}")
            cur = vals
            kelas = bersih(r[4]) or ""
            if kelas not in ("", "1", "2", "3"):
                peringatan.append(f"hal {h}: kelas rawat tak terduga {kelas!r}")
            row = {"h": h, "j": j, "jenis_rs": jenis_rs, "vals": list(vals),
                   "kelas": kelas, "tarif_raw": r[5:]}
            logis.append(row)
            if LANJUT in vals:
                pending.append(row)
        carry = cur
    if pending:
        peringatan.append(f"penanda LANJUT tak terselesaikan di akhir: {len(pending)}")

    rec = []
    for row in logis:
        vals, h = row["vals"], row["h"]
        if not RE_KODE_SPS.match(vals[1] or ""):
            peringatan.append(f"hal {h}: kode spesial aneh {vals[1]!r}")
        if not RE_KODE_INA.match(vals[3] or ""):
            peringatan.append(f"hal {h}: kode INA-CBG aneh {vals[3]!r}")
        for k, nama in enumerate(row["jenis_rs"]):
            rec.append({
                "halaman": h, **row["j"], "no": int(vals[0]), "kode_spesial": vals[1],
                "deskripsi_spesial_cmg": vals[2], "kode_ina_cbg": vals[3],
                "deskripsi_kode_ina_cbg": None, "jenis_rs": nama,
                "kelas_harga": row["kelas"] or None,
                "tarif": tarif(row["tarif_raw"][k], f"hal {h} NO {vals[0]}"),
            })
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
    def sektor(rs):
        return "PEMERINTAH" if "PEMERINTAH" in rs else "SWASTA" if "SWASTA" in rs else "RS KHUSUS"
    blok = defaultdict(list)
    for x in top:
        blok[(x["regional"], sektor(x["jenis_rs"]), x["jenis_rs"])].append(x)
    struktur = {}
    for key, xs in blok.items():
        grup = defaultdict(list)
        for x in xs:
            grup[(x["no"], x["kode_spesial"], x["deskripsi_spesial_cmg"], x["kode_ina_cbg"])].append(x["kelas_harga"])
        for g, kl in grup.items():
            if kl not in (["1", "2", "3"], [None]):
                peringatan.append(f"Top Up {key} {g}: urutan kelas rawat {kl}")
        nos = sorted({g[0] for g in grup})
        if nos != list(range(1, 37)):
            peringatan.append(f"Top Up {key}: NO tidak lengkap {nos}")
        struktur[key] = [(g, tuple(kl)) for g, kl in grup.items()]
    ref = next(iter(struktur.values()))
    for key, s_ in struktur.items():
        if s_ != ref:
            beda = [(a, b) for a, b in zip(ref, s_) if a != b][:3]
            laporan.append(f"Top Up {key}: struktur berbeda dari blok pertama, contoh {beda}")
    laporan.append(f"Top Up: {len({k[:2] for k in blok})} blok x jenis RS = {len(blok)} kolom, {len(top)} baris; "
                   f"{len(ref)} kombinasi item/kode INA-CBG per kolom")


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
                    cell.alignment = Alignment(horizontal="right")


def main():
    pages = pickle.load(open(sys.argv[1], "rb"))
    for extra in sys.argv[4:]:  # pickle tambahan menimpa halaman yang sama
        baru = {p["halaman"]: p for p in pickle.load(open(extra, "rb"))}
        pages = [baru.get(p["halaman"], p) for p in pages]
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
