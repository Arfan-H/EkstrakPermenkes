"""Bangun situs statis kalkulator untuk hosting (GitHub Pages).

web/index.html ditulis tanpa <!doctype>/<head> karena kerangka itu ditambahkan
otomatis oleh claude.ai saat dipublikasikan sebagai artefak. Untuk hosting
biasa, skrip ini membungkusnya menjadi dokumen HTML lengkap dan menyalin data.

Pemakaian: python scripts/bangun_situs.py [folder_output]   (default: site)
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

KERANGKA = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Kalkulator tarif klaim INA-CBG (JKN) berdasarkan Permenkes No. 3 Tahun 2023: tarif dasar CBG, top up Special CMG, sub-akut/kronis, dan selisih naik kelas.">
<style>
:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}
img{max-width:100%}
[hidden]{display:none!important}
</style>
{kepala}
</head>
<body>
{isi}
</body>
</html>
"""


def main():
    out = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else "site")
    src = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
    # pindahkan <title>, <meta>, <link>, <style> pertama ke <head>
    m = re.match(r"\s*((?:<title>.*?</title>|<meta[^>]*>|<link[^>]*>|<style>.*?</style>|\s)+)", src, re.S)
    kepala, isi = (m.group(1).strip(), src[m.end():]) if m else ("", src)
    if "<title>" not in kepala:
        raise SystemExit("web/index.html harus diawali <title>")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "data"))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(KERANGKA.replace("{kepala}", kepala).replace("{isi}", isi.strip()))
    for nama in ("kalkulator.json", "icd.json"):
        shutil.copy(os.path.join(WEB, "data", nama), os.path.join(out, "data", nama))
    open(os.path.join(out, ".nojekyll"), "w").close()
    print(f"situs ditulis ke {out}")


if __name__ == "__main__":
    main()
