"""Verifikasi independen hasil Excel.

Metode kedua, berbeda dari ekstrak_raw.py (pdfplumber + grid tabel):
- sumber teks: `pdftotext -bbox` (Poppler), posisi tiap kata
- tidak memakai garis/sel tabel sama sekali
  * Top Up: baris = posisi-y angka tarif; label sel merge (NO, kode spesial,
    deskripsi, kode INA-CBG) dipasangkan ke rentang baris yang titik tengahnya
    sama dengan posisi label (label selalu rata-tengah vertikal dalam sel).
  * Tarif utama: baris = kode INA-CBG; deskripsi & tarif = kata terdekat (y).
Lalu setiap baris dibandingkan kolom per kolom dengan Excel.

Pemakaian: python verifikasi.py <pdf_potongan> <hasil.xlsx> <laporan_verifikasi.txt>
"""
import html
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

import pandas as pd

OFFSET = 39
RE_ANGKA = re.compile(r"^(\d{1,3}(?:\.\d{3})*|-)$")
RE_KODE_INA = re.compile(r"^[A-Z]-\d-\d{2}-(?:I{1,3}|0)$")
RE_KODE_SPS = re.compile(r"^[A-Z]{2}-\d{2}-I{1,3}$")
masalah = []
catatan = []


# ------------------------------------------------------------ baca bbox
def baca_bbox(pdf):
    with tempfile.NamedTemporaryFile(suffix=".html") as f:
        subprocess.run(["pdftotext", "-bbox", pdf, f.name], check=True)
        h = open(f.name, encoding="utf-8").read()
    pages = []
    for p in h.split("<page ")[1:]:
        ws = [dict(x0=float(a), y0=float(b), x1=float(c), y1=float(d), t=html.unescape(e))
              for a, b, c, d, e in re.findall(
                  r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', p)]
        pages.append(dedupe(ws))
    return pages


def baca_garis(pdf, idxs):
    """Garis horizontal mentah (edge dari rect/line PDF) per halaman."""
    import pdfplumber
    out = {}
    with pdfplumber.open(pdf) as doc:
        for i in idxs:
            p = doc.pages[i]
            out[i] = [(e["top"], e["x0"], e["x1"]) for e in p.edges
                      if e["orientation"] == "h" and e["x1"] - e["x0"] > 3]
            p.flush_cache()
    return out


def dedupe(ws):
    """Buang salinan/potongan kata yang berada di dalam kotak kata lain yang lebih panjang."""
    ws = sorted(ws, key=lambda w: -(w["x1"] - w["x0"]))
    keep = []
    ember = defaultdict(list)  # indeks per y agar cepat
    for w in ws:
        dup = False
        yk = round(w["y0"])
        for k in ember[yk - 1] + ember[yk] + ember[yk + 1]:
            if (abs(k["y0"] - w["y0"]) < 0.6 and k["x0"] - 0.4 <= w["x0"] and w["x1"] <= k["x1"] + 0.4):
                dup = True
                break
        if not dup:
            keep.append(w)
            ember[yk].append(w)
    return sorted(keep, key=lambda w: (w["y0"], w["x0"]))


def cx(w):
    return (w["x0"] + w["x1"]) / 2


def cy(w):
    return (w["y0"] + w["y1"]) / 2


def baris_teks(ws, tol=1.0):
    """Kelompokkan kata menjadi baris teks (berdasar y0)."""
    lines = []
    for w in sorted(ws, key=lambda w: (w["y0"], w["x0"])):
        if lines and abs(lines[-1][0]["y0"] - w["y0"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in lines]


def judul_halaman(ws, y_batas):
    j = {"judul": None, "regional": None, "jenis_tabel": None, "jenis_rawat": None}
    for l in baris_teks([w for w in ws if w["y1"] <= y_batas]):
        s = " ".join(w["t"] for w in l)
        if s == "TARIF INA-CBG":
            j["judul"] = s
        elif re.fullmatch(r"REGIONAL \d", s):
            j["regional"] = s
        elif s == "TOP UP SPESIAL CMG" or s.startswith("RUMAH SAKIT"):
            j["jenis_tabel"] = s
        elif s in ("RAWAT INAP", "RAWAT JALAN"):
            j["jenis_rawat"] = s
        elif s.endswith("TOP UP SPESIAL CMG"):
            j["jenis_tabel"] = "TOP UP SPESIAL CMG"
    return j


# ---------------------------------------------------------------- Top Up
def kolom_topup(ws, h):
    """Cari pusat-x tiap kolom dari kata header (berdasar urutan, bukan posisi tetap)."""
    no = [w for w in ws if w["t"] == "NO" and 90 < w["y0"] < 260]
    if not no:
        raise ValueError(f"hal {h}: header NO tidak ketemu")
    no = no[0]
    hdr = [w for w in ws if no["y0"] - 8 <= w["y0"] <= no["y0"] + 5]
    def cari(t, kondisi=lambda w: True):
        c = [w for w in hdr if w["t"] == t and kondisi(w)]
        if not c:
            raise ValueError(f"hal {h}: header {t} tidak ketemu")
        return c[0]
    desk = cari("DESKRIPSI")
    sps = cari("SPESIAL", lambda w: w["x1"] < desk["x0"])
    ina = cari("INA-")
    kelas = cari("KELAS")
    rawat = cari("RAWAT")
    y_hdr = max(w["y1"] for w in hdr if w["x1"] < kelas["x1"] + 2 and not RE_ANGKA.match(w["t"])
                and not RE_KODE_INA.match(w["t"]))
    namaw = [w for w in hdr if w["x0"] > rawat["x1"] and not RE_ANGKA.match(w["t"])]
    cols = []
    for w in sorted(namaw, key=cx):
        if cols and abs(cx(w) - cols[-1]["x"]) < 15:
            cols[-1]["w"].append(w)
        else:
            cols.append({"x": cx(w), "w": [w]})
    tarif_cols = []
    for c in cols:
        nama = " ".join(w["t"] for w in sorted(c["w"], key=lambda w: w["y0"]))
        tarif_cols.append((sum(cx(w) for w in c["w"]) / len(c["w"]), nama))
        y_hdr = max(y_hdr, max(w["y1"] for w in c["w"]))
    pos = {"no": cx(no), "sps": cx(sps), "desk": cx(desk) + 15, "ina": cx(ina) - 5, "kelas": cx(kelas)}
    return pos, tarif_cols, y_hdr


def proses_topup_halaman(ws, h, garis):
    pos, tarif_cols, y_hdr = kolom_topup(ws, h)
    j = judul_halaman(ws, y_hdr - 20)
    centers = sorted([(v, k) for k, v in pos.items()] + [(x, ("T", i)) for i, (x, _) in enumerate(tarif_cols)])
    def kolom(w):
        return min(centers, key=lambda c: abs(c[0] - cx(w)))[1]
    body = [w for w in ws if w["y0"] > y_hdr + 0.5 and "jdih" not in w["t"]]
    # baris data = kata tarif
    trow = defaultdict(dict)
    for w in body:
        k = kolom(w)
        if isinstance(k, tuple):
            if not RE_ANGKA.match(w["t"]):
                if "kemkes" not in w["t"]:
                    masalah.append(f"hal {h}: token tarif aneh {w['t']!r}")
                continue
            trow[round(w["y0"], 0)][k[1]] = w
    ys = sorted(trow)
    rows = []
    for y in ys:
        ww = list(trow[y].values())
        rows.append({"t": min(w["y0"] for w in ww), "b": max(w["y1"] for w in ww),
                     "tarif": [trow[y].get(i, {}).get("t") for i in range(len(tarif_cols))],
                     "kelas": ""})
    y_akhir = max(r["b"] for r in rows)
    y_awal = min(r["t"] for r in rows)
    # kata di luar rentang baris data ter-clip (tak terlihat di halaman)
    body = [w for w in body if w["y1"] <= y_akhir + 1.0 and w["y0"] >= y_awal - 1.0]
    for r in rows:
        if None in r["tarif"]:
            masalah.append(f"hal {h}: baris y={r['t']:.1f} ada kolom tarif kosong {r['tarif']}")
    # kelas
    for w in body:
        if kolom(w) == "kelas":
            r = min(rows, key=lambda r: abs((r["t"] + r["b"]) / 2 - cy(w)))
            if abs((r["t"] + r["b"]) / 2 - cy(w)) > 2.5 or r["kelas"]:
                masalah.append(f"hal {h}: kata kelas {w['t']!r} tidak pas ke satu baris")
            r["kelas"] = w["t"]
    # label per kolom: kata dikelompokkan jadi frasa (per baris teks), lalu frasa -> kolom
    frasa = []
    for l in baris_teks([w for w in body if not isinstance(kolom(w), tuple) and kolom(w) != "kelas"]):
        cur = [l[0]]
        for w in l[1:]:
            if w["x0"] - cur[-1]["x1"] < 4.5:
                cur.append(w)
            else:
                frasa.append(cur)
                cur = [w]
        frasa.append(cur)
    labels = {k: [] for k in ("no", "sps", "desk", "ina")}
    for fr in frasa:
        x = (fr[0]["x0"] + fr[-1]["x1"]) / 2
        k = min(((abs(pos[k] - x), k) for k in labels))[1]
        labels[k].append({"teks": " ".join(w["t"] for w in fr), "y0": fr[0]["y0"], "y1": fr[0]["y1"]})
    for k in labels:
        labels[k].sort(key=lambda d: d["y0"])
    n = len(rows)

    def awal_kolom(x):
        """Baris yang diawali garis horizontal pada kolom berpusat x."""
        ys = [y for y, x0, x1 in garis if x0 - 0.5 <= x <= x1 + 0.5]
        hasil = [0]
        for i in range(1, n):
            lo, hi = rows[i - 1]["b"] - 0.5, rows[i]["t"] + 0.5
            if any(lo <= y <= hi for y in ys):
                hasil.append(i)
        return hasil

    seg = {}
    for k, nm in (("ina", "kode INA-CBG"), ("no", "no"), ("sps", "sps"), ("desk", "desk")):
        x = pos[k] if k != "desk" else pos[k] - 15
        seg[k] = segmentasi(rows, labels[k], awal_kolom(x), h, nm)
    # cek silang: grup kelas rawat (1,2,3) harus sama dengan sel kode INA-CBG dari garis
    awal_ina = {s_ for s_, e_, _ in seg["ina"]}
    for i in range(1, n):
        if rows[i]["kelas"] == "1" and i not in awal_ina:
            masalah.append(f"hal {h}: baris kelas 1 di y={rows[i]['t']:.1f} tidak diawali garis kode INA-CBG")
    out = []
    for i, r in enumerate(rows):
        v = {}
        for k in ("no", "sps", "desk", "ina"):
            v[k] = next(lbl for s, e, lbl in seg[k] if s <= i <= e)
        out.append({"h": h, "j": j, "v": v, "kelas": r["kelas"], "tarif": r["tarif"],
                    "jenis_rs": [nm for _, nm in tarif_cols]})
    return out


def segmentasi(rows, lines, awal, h, nama):
    """Bagi baris data menjadi sel berurutan. Tiap sel memuat satu label
    (1-3 baris teks berurutan) yang posisinya di tengah vertikal sel.
    Sel tanpa label hanya boleh paling atas (<ATAS>) / paling bawah (<BAWAH>).
    Sel terpotong batas halaman (pertama/terakhir) cukup memuat labelnya."""
    import functools
    n = len(rows)
    awal = sorted(set(awal))
    akhir_ok = set(a - 1 for a in awal if a > 0) | {n - 1}
    L = len(lines)

    def blok(i, k):
        if i + k > L:
            return None
        for j in range(i + 1, i + k):
            if lines[j]["y0"] - lines[j - 1]["y1"] > 3.0:
                return None
        return ((lines[i]["y0"] + lines[i + k - 1]["y1"]) / 2,
                " ".join(lines[j]["teks"] for j in range(i, i + k)))

    @functools.lru_cache(maxsize=None)
    def f(i, mulai):
        """biaya minimum & segmentasi untuk lines[i:] mulai baris `mulai`."""
        if i == L:
            if mulai >= n:
                return (0.0, ())
            return (10.0, ((mulai, n - 1, "<BAWAH>"),))
        best = (float("inf"), None)
        starts = [mulai] if mulai > 0 or i > 0 else awal  # baris atas boleh tanpa label
        for s in starts:
            if s >= n or s not in awal and s != mulai:
                continue
            pre = ((0, s - 1, "<ATAS>"),) if (i == 0 and s > 0) else ()
            biaya_pre = 10.0 if pre else 0.0
            for k in (1, 2, 3):
                bk = blok(i, k)
                if bk is None:
                    continue
                y, teks = bk
                for e in range(s, n):
                    if e not in akhir_ok or rows[e]["b"] < y - 1:
                        continue
                    if rows[s]["t"] > y + 1:
                        break
                    err = abs((rows[s]["t"] + rows[e]["b"]) / 2 - y)
                    if err >= 2.5:
                        tengah = (rows[s]["t"] + rows[e]["b"]) / 2
                        dalam = rows[s]["t"] - 1 <= y <= rows[e]["b"] + 1
                        if dalam and e == n - 1 and y > tengah:
                            err = 3.0  # sel berlanjut ke hal. berikutnya
                        elif dalam and s == 0 and y < tengah:
                            err = 3.0  # sel lanjutan dari hal. sebelumnya
                        else:
                            continue
                    sub = f(i + k, e + 1)
                    if sub[1] is None:
                        continue
                    c = biaya_pre + err + (k - 1) * 3.0 + sub[0]
                    if c < best[0] - 1e-9:
                        best = (c, pre + ((s, e, teks),) + sub[1])
        return best

    cost, segs = f(0, 0)
    if segs is None:
        masalah.append(f"hal {h}: segmentasi {nama} gagal ({L} label, {n} baris)")
        return [(0, n - 1, "<GAGAL>")]
    return list(segs)


def topup_semua(pages, garis):
    semua = []
    for idx in range(0, 44):
        h = idx + 1 + OFFSET
        semua.append(proses_topup_halaman(pages[idx], h, garis[idx]))
    # selesaikan <ATAS>/<BAWAH>
    for pi, rows in enumerate(semua):
        for r in rows:
            for k in r["v"]:
                if r["v"][k] == "<ATAS>":
                    r["v"][k] = semua[pi - 1][-1]["v"][k]
                    catatan.append(f"hal {r['h']}: {k} baris atas diambil dari hal {r['h']-1}: {r['v'][k]}")
        for r in rows:
            for k in r["v"]:
                if r["v"][k] == "<BAWAH>":
                    r["v"][k] = semua[pi + 1][0]["v"][k]
                    catatan.append(f"hal {r['h']}: {k} baris bawah diambil dari hal {r['h']+1}: {r['v'][k]}")
    rec = []
    for rows in semua:
        for r in rows:
            for k, nm in enumerate(r["jenis_rs"]):
                t = r["tarif"][k]
                rec.append({"halaman": r["h"], **r["j"], "no": int(r["v"]["no"]) if str(r["v"]["no"]).isdigit() else r["v"]["no"],
                            "kode_spesial": r["v"]["sps"], "deskripsi_spesial_cmg": r["v"]["desk"],
                            "kode_ina_cbg": r["v"]["ina"], "deskripsi_kode_ina_cbg": None,
                            "jenis_rs": nm, "kelas_harga": r["kelas"] or None,
                            "tarif": t if t == "-" else int(t.replace(".", ""))})
    return rec


# ---------------------------------------------------------- Tarif utama
def utama_semua(pages):
    rec = []
    for idx in range(92 - 40, len(pages)):
        h = idx + 1 + OFFSET
        ws = pages[idx]
        nohdr = [w for w in ws if w["t"] == "NO" and 90 < w["y0"] < 200 and w["x0"] < 80]
        if not nohdr:
            masalah.append(f"hal {h}: header NO tidak ketemu")
            continue
        y_no = nohdr[0]["y0"]
        band = [w for w in ws if y_no - 8 <= w["y0"] <= y_no + 7]
        hdr_tarif = [w for w in band if w["t"] == "TARIF"]
        kode_hdr = [w for w in band if w["t"] == "INA-CBG" and cx(w) < 120]
        if not hdr_tarif or not kode_hdr:
            masalah.append(f"hal {h}: header tarif utama tidak ketemu")
            continue
        y_hdr = max(w["y0"] for w in band) + 2
        j = judul_halaman(ws, hdr_tarif[0]["y0"] - 1)
        tcols = sorted(cx(w) for w in hdr_tarif)
        nama_kelas = []
        for w in sorted(hdr_tarif, key=cx):
            bawah = [v for v in band if abs(cx(v) - cx(w)) < 20 and 0 < v["y0"] - w["y0"] < 12]
            s = " ".join(v["t"] for v in sorted(bawah, key=lambda v: v["x0"]))
            nama_kelas.append(None if s == "INA-CBG" else s)
        body = [w for w in ws if w["y0"] > y_hdr and "jdih" not in w["t"]]
        ttd = [w for w in body if w["t"] == "MENTERI"]
        if ttd:  # blok tanda tangan di halaman terakhir
            body = [w for w in body if w["y0"] < ttd[0]["y0"] - 1]
        kode_x = cx(kode_hdr[0])
        anchors = [w for w in body if RE_KODE_INA.match(w["t"]) and abs(cx(w) - kode_x) < 25]
        x_desk0 = max(w["x1"] for w in anchors) + 1 if anchors else 0
        x_tarif0 = tcols[0] - 30
        rows = []
        for a in anchors:
            no = [w for w in body if w["x1"] < a["x0"] and abs(cy(w) - cy(a)) < 2]
            rows.append({"a": a, "no": " ".join(w["t"] for w in no), "desk": [], "tarif": [None] * len(tcols)})
        for w in body:
            if w in anchors or any(w is x for r in rows for x in []):
                continue
            if w["x1"] < x_desk0 - 1:
                continue  # kolom NO / kode
            r = min(rows, key=lambda r: abs(cy(r["a"]) - cy(w)))
            if abs(cy(r["a"]) - cy(w)) > 9:
                masalah.append(f"hal {h}: kata yatim {w['t']!r} y={w['y0']:.1f}")
                continue
            if cx(w) >= x_tarif0 and RE_ANGKA.match(w["t"]):
                k = min(range(len(tcols)), key=lambda i: abs(tcols[i] - w["x1"] + 15))
                k = min(range(len(tcols)), key=lambda i: abs(tcols[i] - cx(w)))
                if r["tarif"][k] is not None:
                    masalah.append(f"hal {h}: dua tarif di sel yang sama NO {r['no']}")
                r["tarif"][k] = w["t"]
            else:
                r["desk"].append(w)
        for r in rows:
            desk = " ".join(w["t"] for l in baris_teks(r["desk"]) for w in l)
            if not r["no"].isdigit():
                masalah.append(f"hal {h}: NO tidak terbaca untuk {r['a']['t']}")
                continue
            jrs = None
            for k, nk in enumerate(nama_kelas):
                t = r["tarif"][k]
                if t is None:
                    masalah.append(f"hal {h}: tarif kosong NO {r['no']} kolom {nk}")
                    continue
                rec.append({"halaman": h, **j, "no": int(r["no"]), "kode_spesial": None,
                            "deskripsi_spesial_cmg": None, "kode_ina_cbg": r["a"]["t"],
                            "deskripsi_kode_ina_cbg": desk, "jenis_rs": jrs,
                            "kelas_harga": nk.replace("TARIF ", "") if nk else None,
                            "tarif": t if t == "-" else int(t.replace(".", ""))})
    return rec


# ------------------------------------------------------------ bandingkan
KUNCI_BANDING = ["halaman", "judul", "regional", "jenis_tabel", "jenis_rawat", "no",
                 "kode_spesial", "deskripsi_spesial_cmg", "kode_ina_cbg",
                 "deskripsi_kode_ina_cbg", "jenis_rs", "kelas_harga", "tarif"]


def norm(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        return " ".join(v.split())
    return v


def bandingkan(nama, ref, df, kolom):
    beda = 0
    if len(ref) != len(df):
        masalah.append(f"{nama}: jumlah baris verifikasi {len(ref)} != Excel {len(df)}")
    xs = df[kolom].to_dict("records")
    per_kolom = defaultdict(int)
    for i, (a, b) in enumerate(zip(ref, xs)):
        for k in kolom:
            va, vb = norm(a[k]), norm(b[k])
            if k == "kelas_harga" and vb is not None:
                vb = str(vb)
            if va != vb:
                per_kolom[k] += 1
                beda += 1
                if per_kolom[k] <= 15:
                    masalah.append(f"{nama} baris Excel {i+2} (hal {b['halaman']} NO {b['no']}): "
                                   f"kolom {k}: Excel={vb!r} vs PDF={va!r}")
    catatan.append(f"{nama}: {len(xs)} baris x {len(kolom)} kolom dibandingkan, "
                   f"sel beda = {beda} {dict(per_kolom)}")
    return beda


def main():
    pdf, xlsx, out = sys.argv[1:4]
    import os, pickle
    cache = os.environ.get("BBOX_CACHE")
    pages = pickle.load(open(cache, "rb")) if cache else baca_bbox(pdf)
    gcache = os.environ.get("GARIS_CACHE")
    if gcache and os.path.exists(gcache):
        garis = pickle.load(open(gcache, "rb"))
    else:
        garis = baca_garis(pdf, range(44))
        if gcache:
            pickle.dump(garis, open(gcache, "wb"))
    top = topup_semua(pages, garis)
    uta = utama_semua(pages)
    df_top = pd.read_excel(xlsx, sheet_name="Top Up", dtype={"kelas_harga": str})
    df_uta = pd.read_excel(xlsx, sheet_name="Tarif INA-CBG", dtype={"kelas_harga": str})
    df_gab = pd.read_excel(xlsx, sheet_name="Gabungan", dtype={"kelas_harga": str})
    bandingkan("Top Up", top, df_top, KUNCI_BANDING)
    kol_uta = [k for k in KUNCI_BANDING if k != "jenis_rs"]
    bandingkan("Tarif INA-CBG", uta, df_uta, kol_uta)
    # jenis_rs tarif utama: cek konsisten dengan jenis_tabel
    peta = {"RUMAH SAKIT UMUM PUSAT DR. CIPTO MANGUNKUSUMO": "RSCM",
            "RUMAH SAKIT JANTUNG DAN PEMBULUH DARAH HARAPAN KITA": "RSJP-HK",
            "RUMAH SAKIT ANAK DAN BUNDA HARAPAN KITA": "RSAB-HK",
            "RUMAH SAKIT KANKER DHARMAIS": "RSK DHARMAIS",
            "RUMAH SAKIT PUSAT OTAK NASIONAL": "RSPON"}
    for jt, jr in df_uta[["jenis_tabel", "jenis_rs"]].drop_duplicates().itertuples(index=False):
        m = re.fullmatch(r"RUMAH SAKIT KELAS ([ABCD]) (PEMERINTAH|SWASTA)", jt)
        harus = f"{m.group(1)} {m.group(2)}" if m else peta.get(jt)
        if harus != jr:
            masalah.append(f"jenis_rs salah untuk {jt}: {jr} (harusnya {harus})")
    # sheet Gabungan = Top Up + Tarif INA-CBG
    gab2 = pd.concat([df_top, df_uta], ignore_index=True)
    if not gab2.fillna("<NA>").astype(str).equals(df_gab.fillna("<NA>").astype(str)):
        masalah.append("sheet Gabungan tidak sama dengan Top Up + Tarif INA-CBG")
    else:
        catatan.append(f"Gabungan: {len(df_gab)} baris = Top Up + Tarif INA-CBG (identik)")
    with open(out, "w") as f:
        f.write(f"== MASALAH ({len(masalah)}) ==\n" + "\n".join(masalah) +
                "\n\n== CATATAN ==\n" + "\n".join(catatan) + "\n")
    print(f"masalah: {len(masalah)}")
    for m in masalah[:60]:
        print("  !", m)
    for c in catatan:
        if "dibandingkan" in c or "Gabungan" in c:
            print("  ", c)


if __name__ == "__main__":
    main()
