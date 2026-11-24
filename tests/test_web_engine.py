"""Engine JavaScript di web/index.html harus memberi hasil identik dengan engine Python.

Kasus acak dibangkitkan di Python, dijalankan di kedua engine (JS lewat Node),
lalu dibandingkan field per field termasuk teks peringatan.
"""
import json
import os
import random
import re
import shutil
import subprocess

import pytest

from inacbg.engine import INACBGEngine, InputKlaim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "web", "index.html")
DATA = os.path.join(ROOT, "web", "data", "kalkulator.json")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node tidak tersedia")

PROVINSI = ["Jawa Barat", "Bali", "Jambi", "Riau", "Aceh", "DKI Jakarta", "Papua", "Gorontalo"]
ICD9 = ["36.06", "36.07", "81.51", "81.55", "35.92", "39.71", "39.75", "39.74", "43.11", "13.41",
        "23.19", "92.20", "92.27", "11.60", "14.71", "52.6", "32.41", "34.02", "88.92", "92.05",
        "95.12", "31.41", "51.10", "02.93", "76.5", "85.82", "86.60", "99.99"]
ICD10 = ["I21.0", "I23.3", "D56.1", "A41.9", "R57.1", "D66", "T20.3", "T31.4", "E43", "Z51.0", "J18.9"]


def kasus(eng, n, seed=7):
    rnd = random.Random(seed)
    kode_top = sorted({c for (_, c) in eng.pasangan_topup})
    semua = sorted(eng.cbg)
    out = []
    for i in range(n):
        kode = rnd.choice(kode_top) if rnd.random() < 0.6 else rnd.choice(semua)
        jr = eng.cbg[kode]["jenis_rawat"]
        d = {"kode_cbg": kode, "icd10": rnd.sample(ICD10, rnd.randint(0, 2)),
             "icd9": rnd.sample(ICD9, rnd.randint(0, 2))}
        fk = rnd.random()
        if fk < 0.15:
            d["rs_khusus_nasional"] = rnd.choice(["RSCM", "RSJP-HK", "RSK DHARMAIS", "RSAB-HK", "RSPON"])
        elif fk < 0.25:
            d.update(provinsi=rnd.choice(PROVINSI), klinik_utama=True, kepemilikan="SWASTA",
                     persen_klinik_utama=rnd.choice([None, 70, 85, 100]))
        else:
            d.update(provinsi=rnd.choice(PROVINSI), kelas_rs=rnd.choice("ABCD"),
                     kepemilikan=rnd.choice(["PEMERINTAH", "SWASTA"]),
                     tipe_rs=rnd.choice(["umum", "umum", "khusus_jantung", "khusus_lain"]),
                     sesuai_kekhususan=rnd.random() < 0.7)
        if jr == "RI":
            d["kelas_rawat"] = rnd.choice([1, 2, 3])
            if rnd.random() < 0.2:
                d.update(los=rnd.choice([30, 43, 80, 103, 104, 150, 200]), adl_subakut=rnd.choice([10, 12, 30, 60]),
                         adl_kronis=rnd.choice([12, 45]), kasus_psikiatri_kusta=rnd.random() < 0.7)
            if rnd.random() < 0.3:
                d.update(naik_kelas=rnd.choice(["1", "VIP"]),
                         jenis_peserta=rnd.choice([None, None, "PBI", "PEMDA"]),
                         biaya_riil=rnd.choice([None, None, 1_000_000, 50_000_000]))
        else:
            d["rawat_jalan_eksekutif"] = rnd.random() < 0.2
            d["hd_reuse"] = kode == "N-3-15-0" and rnd.random() < 0.5
        sps = sorted({k for (k, c) in eng.pasangan_topup if c == kode})
        pilih = []
        for k in sps:
            if rnd.random() < 0.5:
                pilih.append(k + (":" + rnd.choice(["Hip Implant", "Knee Implant"]) if k == "RR-04-III" else ""))
        if rnd.random() < 0.1:
            pilih.append("YY-02-III")  # mungkin tidak berlaku untuk CBG ini
        d["kode_spesial"] = pilih
        out.append(d)
    return out


def test_js_sama_dengan_python(tmp_path):
    eng = INACBGEngine()
    cases = kasus(eng, 600)
    ref = []
    for d in cases:
        try:
            ref.append({"ok": eng.hitung(InputKlaim(**d)).to_dict()})
        except ValueError as e:
            ref.append({"err": str(e)})
    src = open(HTML, encoding="utf-8").read()
    js = re.search(r'<script id="engine">(.*?)</script>', src, re.S).group(1)
    (tmp_path / "engine.js").write_text(js, encoding="utf-8")
    (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    runner = """
const E = require('./engine.js');
const fs = require('fs');
const eng = E.buat(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')));
const cases = JSON.parse(fs.readFileSync('./cases.json', 'utf8'));
const out = cases.map(c => { try { return {ok: eng.hitung(c)}; } catch (e) { return {err: e.message}; } });
fs.writeFileSync('./out.json', JSON.stringify(out));
"""
    (tmp_path / "run.js").write_text(runner, encoding="utf-8")
    subprocess.run(["node", "run.js", DATA], cwd=tmp_path, check=True)
    got = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))

    kolom = ["kode_cbg", "deskripsi_cbg", "jenis_rawat", "kelompok_tarif", "regional", "kelas_rawat",
             "tarif_dasar", "tarif_dasar_tersedia", "sumber_halaman", "total_klaim_inacbg",
             "rentang_total", "peringatan", "disclaimer"]
    beda = []
    n_ok = 0
    for i, (a, b) in enumerate(zip(ref, got)):
        if ("err" in a) != ("err" in b):
            beda.append((i, cases[i], a, b))
            continue
        if "err" in a:
            continue
        n_ok += 1
        a, b = a["ok"], b["ok"]
        for k in kolom:
            if a[k] != b[k]:
                beda.append((i, k, a[k], b[k]))
        ta = [(t["kode_spesial"], t["deskripsi"], t["nilai"], t["diterima"], t["sumber"], t["alasan"],
               t["sumber_halaman"]) for t in a["topup"]]
        tb = [(t["kode_spesial"], t["deskripsi"], t["nilai"], t["diterima"], t["sumber"], t["alasan"],
               t.get("sumber_halaman")) for t in b["topup"]]
        if ta != tb:
            beda.append((i, "topup", ta, tb))
        if [k["kode_spesial"] for k in a["kandidat_topup"]] != [k["kode_spesial"] for k in b["kandidat_topup"]]:
            beda.append((i, "kandidat", a["kandidat_topup"], b["kandidat_topup"]))
        ska, skb = a["topup_subakut_kronis"], b["topup_subakut_kronis"]
        if (ska is None) != (skb is None) or (ska and any(ska[k] != skb[k] for k in
                                                          ("los_subakut", "los_kronis", "topup_subakut", "topup_kronis"))):
            beda.append((i, "subakut", ska, skb))
        sa, sb = a["selisih_biaya"], b["selisih_biaya"]
        if (sa is None) != (sb is None) or (sa and any(sa.get(k) != sb.get(k) for k in
                                                        ("berlaku", "nilai", "maksimum", "pasti", "dasar"))):
            beda.append((i, "selisih", sa, sb))
    assert n_ok > 400, n_ok
    for x in beda[:6]: print("BEDA", x)
    assert not beda, len(beda)
