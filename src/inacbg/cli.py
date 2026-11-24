"""CLI kalkulator tarif INA-CBG.

Contoh:
  python -m inacbg hitung --kode I-1-40-I --provinsi "Jawa Barat" --kelas-rs B \
      --kepemilikan swasta --kelas-rawat 1 --icd9 36.06
  python -m inacbg cari jantung
  python -m inacbg provinsi
"""
import argparse
import json
import sys

from . import rules as R
from .engine import INACBGEngine, InputKlaim, KalkulatorError


def rp(v):
    return "-" if v is None else "Rp" + f"{int(v):,}".replace(",", ".")


def _daftar(s):
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


def cetak(h):
    d = h.to_dict()
    print(f"\nKode CBG      : {d['kode_cbg']}  {d['deskripsi_cbg']}")
    print(f"Jenis rawat   : {d['jenis_rawat']}" + (f", hak kelas {d['kelas_rawat']}" if d["kelas_rawat"] else ""))
    reg = "nasional" if d["regional"] == "NASIONAL" else f"regional {d['regional']}"
    print(f"Kelompok tarif: {d['kelompok_tarif']} ({reg})")
    if not d["tarif_dasar_tersedia"]:
        print("\nTarif dasar   : TIDAK TERSEDIA di kelompok RS ini")
    else:
        print(f"\nTarif dasar CBG         : {rp(d['tarif_dasar']):>16}   (PDF hal. {d['sumber_halaman']})")
        for t in d["topup"]:
            ket = f"(PDF hal. {t['sumber_halaman']}, {t['sumber']})" if t["diterima"] else f"DITOLAK: {t['alasan']}"
            print(f"Top up {t['kode_spesial']:<10}       : {rp(t['nilai']) if t['diterima'] else '-':>16}   "
                  f"{t['deskripsi']} {ket}")
        sk = d["topup_subakut_kronis"]
        if sk:
            print(f"Top up sub akut         : {rp(sk['topup_subakut']):>16}   ({sk['los_subakut']} hari)")
            if sk["los_kronis"]:
                print(f"Top up kronis           : {rp(sk['topup_kronis']):>16}   ({sk['los_kronis']} hari)")
        print(f"{'':24}  {'-' * 16}")
        print(f"TOTAL KLAIM INA-CBG     : {rp(d['total_klaim_inacbg']):>16}")
        if d["rentang_total"]:
            lo, hi = d["rentang_total"]["total"]
            print(f"  rentang klinik utama {d['rentang_total']['persen'][0]}%-{d['rentang_total']['persen'][1]}%: "
                  f"{rp(lo)} - {rp(hi)}")
    if d["kandidat_topup"]:
        print("\nKandidat top up (pemicu ICD cocok, perlu konfirmasi pemakaian obat/alat):")
        for k in d["kandidat_topup"]:
            print(f"  - {k['kode_spesial']} {k['deskripsi']} ({k['jenis']})")
    s = d["selisih_biaya"]
    if s:
        print("\nSelisih biaya naik kelas:")
        if not s["berlaku"]:
            print(f"  tidak berlaku - {s['dasar']}")
        else:
            if s.get("nilai") is not None:
                print(f"  sebesar {rp(s['nilai'])}")
            else:
                if s.get("pasti") is not None:
                    print(f"  minimal {rp(s['pasti'])},", end="")
                print(f"  paling banyak {rp(s['maksimum'])}")
            print(f"  dasar: {s['dasar']}")
    if d["peringatan"]:
        print("\nPeringatan / catatan:")
        for p in dict.fromkeys(d["peringatan"]):
            print(f"  - {p}")
    print(f"\nDisclaimer: {d['disclaimer']}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="inacbg", description="Kalkulator tarif INA-CBG (PMK 3/2023)")
    sub = ap.add_subparsers(dest="perintah", required=True)

    h = sub.add_parser("hitung", help="hitung tarif klaim")
    h.add_argument("--kode", required=True, help="kode CBG, mis. I-1-40-I")
    h.add_argument("--provinsi")
    h.add_argument("--regional", type=int, choices=range(1, 6))
    h.add_argument("--kelas-rs", choices=list("ABCDabcd"))
    h.add_argument("--kepemilikan", choices=["pemerintah", "swasta", "PEMERINTAH", "SWASTA"])
    h.add_argument("--rs-khusus-nasional", choices=["RSCM", "RSJP-HK", "RSK DHARMAIS", "RSAB-HK", "RSPON"])
    h.add_argument("--tipe-rs", default="umum", choices=["umum", "khusus_jantung", "khusus_lain"])
    h.add_argument("--di-luar-kekhususan", action="store_true", help="RS khusus melayani di luar kekhususannya")
    h.add_argument("--klinik-utama", action="store_true")
    h.add_argument("--persen-klinik-utama", type=float)
    h.add_argument("--kelas-rawat", type=int, choices=[1, 2, 3], help="hak kelas rawat inap")
    h.add_argument("--icd10", help="daftar dipisah koma")
    h.add_argument("--icd9", help="daftar dipisah koma")
    h.add_argument("--kode-spesial", help="daftar dipisah koma, mis. RR-04-III:Knee Implant,YY-01-II")
    h.add_argument("--los", type=int)
    h.add_argument("--adl-subakut", type=float)
    h.add_argument("--adl-kronis", type=float)
    h.add_argument("--psikiatri-kusta", action="store_true", help="kasus psikiatri atau kusta (syarat top up sub akut/kronis)")
    h.add_argument("--hd-reuse", action="store_true")
    h.add_argument("--naik-kelas", choices=["1", "VIP", "vip"])
    h.add_argument("--rawat-jalan-eksekutif", action="store_true")
    h.add_argument("--jenis-peserta", choices=["PBI", "PBPU_KELAS_3", "BP_KELAS_3", "PEMDA", "PPU_PHK", "LAINNYA"])
    h.add_argument("--biaya-riil", type=int)
    h.add_argument("--json", action="store_true", help="keluaran JSON")

    t = sub.add_parser("tebak", help="penuntun kode CBG dari diagnosis dan prosedur (ESTIMASI)")
    t.add_argument("--icd10", help="diagnosis utama, mis. I21.0")
    t.add_argument("--icd9", help="prosedur, dipisah koma, mis. 36.06")
    t.add_argument("--rawat", choices=["RI", "RJ", "ri", "rj"], default="RI")
    t.add_argument("--kategori", choices=["umum", "kebidanan", "neonatal"], default="umum")
    t.add_argument("--tanpa-prosedur", action="store_true", help="abaikan prosedur untuk case group")
    t.add_argument("--severity", choices=["I", "II", "III"])
    t.add_argument("--json", action="store_true")

    c = sub.add_parser("cari", help="cari kode CBG berdasarkan kata kunci")
    c.add_argument("kata")
    sub.add_parser("provinsi", help="daftar provinsi per regional")

    a = ap.parse_args(argv)
    if a.perintah == "provinsi":
        for r, ps in R.REGIONAL_PROVINSI.items():
            print(f"Regional {r}: {', '.join(ps)}")
        return 0
    eng = INACBGEngine()
    if a.perintah == "tebak":
        from . import penuntun as P
        trig = [{"kode_spesial": d["kode_spesial"], "cbg": d["cbg"], "ICD10": d["ICD10"], "ICD9CM": d["ICD9CM"]}
                for d in eng.trigger.values()]
        h = P.tebak(eng.cbg, trig, icd10_utama=a.icd10, icd9=_daftar(a.icd9), jenis_rawat=a.rawat.upper(),
                    kategori=a.kategori, ada_prosedur=False if a.tanpa_prosedur else None, severity=a.severity)
        if a.json:
            print(json.dumps(h, ensure_ascii=False, indent=2))
            return 0
        print("\nCase group : " + ", ".join(f"{c['kode']} {c['deskripsi']}" for c in h["case_group"]))
        print("CMG        : " + "; ".join(f"{c['kode']} ({c['alasan']})" for c in h["cmg"][:5])
              + (" ..." if len(h["cmg"]) > 5 else ""))
        print(f"\nKandidat ({h['jumlah_kandidat']}):")
        for k in h["kandidat"][:25]:
            kode = k["kode_terpilih"] or k["grup"] + "-?"
            tanda = f"  [Lampiran I.A: {', '.join(k['lampiran_ia'])}]" if k["lampiran_ia"] else ""
            print(f"  {kode:<12} {k['deskripsi']}{tanda}")
        for p in h["peringatan"]:
            print(f"\n- {p}")
        print(f"\n{h['disclaimer']}\n")
        return 0
    if a.perintah == "cari":
        for r in eng.cari_cbg(a.kata):
            print(f"{r['kode_cbg']:<12} {r['jenis_rawat']}  {r['deskripsi']}")
        return 0
    inp = InputKlaim(
        kode_cbg=a.kode, provinsi=a.provinsi, regional=a.regional, kelas_rs=a.kelas_rs,
        kepemilikan=a.kepemilikan, rs_khusus_nasional=a.rs_khusus_nasional, tipe_rs=a.tipe_rs,
        sesuai_kekhususan=not a.di_luar_kekhususan, klinik_utama=a.klinik_utama,
        persen_klinik_utama=a.persen_klinik_utama, kelas_rawat=a.kelas_rawat,
        icd10=_daftar(a.icd10), icd9=_daftar(a.icd9), kode_spesial=_daftar(a.kode_spesial),
        los=a.los, adl_subakut=a.adl_subakut, adl_kronis=a.adl_kronis, kasus_psikiatri_kusta=a.psikiatri_kusta, hd_reuse=a.hd_reuse,
        naik_kelas=a.naik_kelas, rawat_jalan_eksekutif=a.rawat_jalan_eksekutif,
        jenis_peserta=a.jenis_peserta, biaya_riil=a.biaya_riil)
    try:
        hasil = eng.hitung(inp)
    except (KalkulatorError, ValueError) as e:
        print(f"Kesalahan: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(hasil.to_dict(), ensure_ascii=False, indent=2))
    else:
        cetak(hasil)
    return 0


if __name__ == "__main__":
    sys.exit(main())
