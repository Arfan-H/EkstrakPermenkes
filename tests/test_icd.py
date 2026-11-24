"""Pencarian ICD-10/ICD-9-CM dari nama penyakit/tindakan (src/inacbg/icd.py) dan port JS-nya."""
import csv
import json
import os
import re
import shutil
import subprocess

import pytest

from inacbg import icd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("q,tipe,kode", [
    ("tifoid", "ICD10", "A01.0"), ("tipes", "ICD10", "A01.0"), ("typhoid", "ICD10", "A01.0"),
    ("DBD", "ICD10", "A91"), ("demam berdarah", "ICD10", "A91"), ("wasir", "ICD10", "I84.9"),
    ("usus buntu", "ICD10", "K35.9"), ("darah tinggi", "ICD10", "I10"), ("kencing manis", "ICD10", "E11.9"),
    ("I21.0", "ICD10", "I21.0"), ("bayi kuning", "ICD10", "P59.9"), ("cuci darah", "ICD9CM", "39.95"),
    ("sunat", "ICD9CM", "64.0"), ("operasi sesar", "ICD9CM", "74.1"), ("36.06", "ICD9CM", "36.06"),
    ("phaco", "ICD9CM", "13.41"),
])
def test_hasil_pertama(q, tipe, kode):
    assert icd.cari(q, tipe, 1)["hasil"][0]["kode"] == kode


def test_kosong_dan_tidak_ditemukan():
    assert icd.cari("", "ICD10")["jumlah"] == 0
    assert icd.cari("xyzabc qwerty", "ICD10")["jumlah"] == 0


def test_semua_kata_harus_cocok_dan_urutan_tingkat():
    r = icd.cari("fracture femur", "ICD10", 100)
    assert r["jumlah"] > 0 and all(h["kode"].startswith("S72") or "femur" in h["judul"].lower() for h in r["hasil"])
    t = [h["tingkat"] for h in icd.cari("stroke", "ICD10", 100)["hasil"]]
    assert t == sorted(t) and t[0] == 0


def test_kode_istilah_ada_di_daftar_resmi():
    """Setiap kode di data/manual/istilah_icd.csv harus ada di daftar ICD (scripts/bangun_icd.py juga mengecek)."""
    with open(os.path.join(ROOT, "data", "manual", "istilah_icd.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            assert icd.indeks(r["tipe"]).judul(r["kode"]) is not None, r


def test_kode_2010_ditandai():
    h = icd.cari("A91", "ICD10", 1)["hasil"][0]
    assert h["kode"] == "A91" and h["tanda"] == 1
    assert icd.cari("A97.1", "ICD10", 1)["hasil"][0]["tanda"] == 2


@pytest.mark.skipif(shutil.which("node") is None, reason="node tidak tersedia")
def test_js_sama_dengan_python(tmp_path):
    qs = ["tifoid", "typhoid", "dbd", "a01", "A01.0", "fracture femur", "stroke", "Kanker  payudara", "maag",
          "guillain", "barré", "bell's", "pasang ring", "36.0", "appendectomy", "sesar", "x", "1", "j0", "o8",
          "luka bakar", "patah tulang", "ISPA", "", "  ", "z51", "hip", "knee replacement", "katarak", "cuci darah"]
    cases = [{"q": q, "tipe": t, "maks": m} for q in qs for t in ("ICD10", "ICD9CM") for m in (5, 1000)]
    ref = [icd.cari(c["q"], c["tipe"], c["maks"]) for c in cases]
    src = open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8").read()
    js = re.search(r'<script id="engine">(.*?)</script>', src, re.S).group(1)
    (tmp_path / "engine.js").write_text(js, encoding="utf-8")
    (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    (tmp_path / "run.js").write_text("""
const E = require('./engine.js'); const fs = require('fs');
const I = E.buatIcd(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')));
const cases = JSON.parse(fs.readFileSync('./cases.json', 'utf8'));
fs.writeFileSync('./out.json', JSON.stringify(cases.map(c => (c.tipe === 'ICD10' ? I.icd10 : I.icd9).cari(c.q, c.maks))));
""", encoding="utf-8")
    subprocess.run(["node", "run.js", os.path.join(ROOT, "web", "data", "icd.json")], cwd=tmp_path, check=True)
    got = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    for c, a, b in zip(cases, ref, got):
        assert a == b, c
