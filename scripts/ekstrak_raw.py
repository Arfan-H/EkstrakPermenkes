"""Tahap 1: baca tabel mentah dari setiap halaman PDF (hasil potong, hal. 40-721).

Output: pickle berisi list dict per halaman:
  {halaman, judul_lines, header, rows, hidden}
- halaman     : nomor halaman PDF asli (40-721)
- judul_lines : baris teks di atas tabel (tanpa nomor halaman)
- rows        : isi tabel (None = bagian sel merge, '' = sel kosong)

Pemakaian: python ekstrak_raw.py <pdf_potongan> <out.pkl>
"""
import pickle
import re
import sys
from multiprocessing import Pool

import pdfplumber

LANJUT = "<<LANJUT_HAL_BERIKUTNYA>>"
OFFSET = 39 # halaman 1 PDF potongan = halaman 40 PDF asli
PDF = None


def baca_halaman(idx):
    with pdfplumber.open(PDF) as pdf:
        page = pdf.pages[idx]
        # Banyak halaman menyimpan tiap huruf berulang di posisi yang sama
        # (efek bold); hapus salinan identik saja.
        page = page.dedupe_chars(tolerance=0.05)
        halaman = idx + 1 + OFFSET
        tabs = page.find_tables()
        if not tabs:
            return {"halaman": halaman, "judul_lines": [], "rows": []}
        tab = max(tabs, key=lambda t: (t.bbox[3] - t.bbox[1]) * (t.bbox[2] - t.bbox[0]))
        rows = tab.extract()
        orphan = isi_sel_terbuka(page, tab, rows)
        atas = page.crop((0, 0, page.width, tab.bbox[1])).extract_text() or ""
        lines = [l.strip() for l in atas.split("\n") if l.strip()]
        lines = [l for l in lines if not re.fullmatch(r"-+\s*\d+\s*-+", l)]
        return {"halaman": halaman, "judul_lines": lines, "rows": rows,
                "n_tables": len(tabs), "orphan": orphan}


def isi_sel_terbuka(page, tab, rows):
    """Sel merge paling bawah di halaman tidak punya garis bawah (tabel berlanjut
    ke halaman berikutnya), sehingga pdfplumber tidak membentuk selnya dan
    teksnya hilang. Ambil kata di kolom tsb yang berada di bawah sel terakhir,
    lalu tempatkan di baris pertama di bawah sel tsb."""
    log = []
    trows = tab.rows
    header = trows[0].cells
    for c in range(len(header)):
        if header[c] is None:
            continue
        x0, x1 = header[c][0], header[c][2]
        last = None
        for i in range(1, len(trows)):
            if trows[i].cells[c] is not None:
                last = i
        if last is None:
            continue
        y_bawah = trows[last].cells[c][3]
        if tab.bbox[3] - y_bawah < 1:
            continue
        kata = [w for w in page.crop((x0, y_bawah, x1, tab.bbox[3])).extract_words()
                if w["top"] >= y_bawah - 0.5]
        target = next((i for i in range(last + 1, len(trows))
                       if trows[i].bbox[1] >= y_bawah - 0.5), None)
        if not kata:
            # Sel terbuka tanpa teks: isinya tertulis di halaman berikutnya.
            if c <= 3 and target is not None and rows[target][c] is None:
                rows[target][c] = LANJUT
                log.append((c, target, LANJUT))
            continue
        if target is None or rows[target][c] is not None:
            log.append(("GAGAL", c, [w["text"] for w in kata]))
            continue
        kata.sort(key=lambda w: (round(w["top"]), w["x0"]))
        teks = " ".join(w["text"] for w in kata)
        rows[target][c] = teks
        log.append((c, target, teks))
    return log


def main():
    global PDF
    PDF = sys.argv[1]
    with pdfplumber.open(PDF) as pdf:
        n = len(pdf.pages)
    idxs = list(range(n))
    if len(sys.argv) > 3:  # opsional: subset halaman asli, mis. 40-83
        a, b = map(int, sys.argv[3].split("-"))
        idxs = [i for i in idxs if a <= i + 1 + OFFSET <= b]
    with Pool(4) as pool:
        hasil = []
        for i, r in enumerate(pool.imap(baca_halaman, idxs, chunksize=4)):
            hasil.append(r)
            if i % 50 == 0:
                print(f"  {i}/{len(idxs)} halaman", flush=True)
    with open(sys.argv[2], "wb") as f:
        pickle.dump(hasil, f)
    print("selesai", len(hasil))


if __name__ == "__main__":
    main()
