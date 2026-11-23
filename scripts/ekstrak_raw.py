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

OFFSET = 39  # halaman 1 PDF potongan = halaman 40 PDF asli
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
        atas = page.crop((0, 0, page.width, tab.bbox[1])).extract_text() or ""
        lines = [l.strip() for l in atas.split("\n") if l.strip()]
        lines = [l for l in lines if not re.fullmatch(r"-+\s*\d+\s*-+", l)]
        return {"halaman": halaman, "judul_lines": lines, "rows": rows,
                "n_tables": len(tabs)}


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
