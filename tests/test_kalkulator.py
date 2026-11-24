"""Unit test kalkulator INA-CBG. Golden values dicek ke PDF PMK 3/2023."""
import csv
import os
from collections import Counter

import pytest

from inacbg import rules as R
from inacbg.engine import DATA_DIR, INACBGEngine, InputKlaim, KalkulatorError


@pytest.fixture(scope="module")
def eng():
    return INACBGEngine()


def ri(**kw):
    base = dict(provinsi="Jawa Barat", kelas_rs="A", kepemilikan="PEMERINTAH", kelas_rawat=1)
    base.update(kw)
    return InputKlaim(**base)


# ------------------------------------------------------------ golden values
@pytest.mark.parametrize("kode,kelas,expected", [
    ("A-4-10-I", 3, 3_702_300), ("A-4-10-I", 2, 4_313_200), ("A-4-10-I", 1, 4_924_100),
    ("A-4-10-II", 3, 6_323_900), ("A-4-10-II", 2, 7_367_300), ("A-4-10-II", 1, 8_410_800),
    ("A-4-10-III", 3, 8_526_600), ("A-4-10-III", 2, 9_933_500), ("A-4-10-III", 1, 11_340_400),
])
def test_golden_hal92(eng, kode, kelas, expected):
    h = eng.hitung(ri(kode_cbg=kode, kelas_rawat=kelas))
    assert h.tarif_dasar == expected and h.sumber_halaman == 92


def test_golden_pci(eng):
    h = eng.hitung(ri(kode_cbg="I-1-40-I", kelas_rs="B", kepemilikan="SWASTA", icd9=["36.06"]))
    assert h.tarif_dasar == 17_127_100
    assert [(t.kode_spesial, t.nilai) for t in h.topup] == [("YY-02-III", 10_725_900)]
    assert h.total_klaim_inacbg == 27_853_000


@pytest.mark.parametrize("varian,implant", [("Hip Implant", 18_000_000), ("Knee Implant", 13_000_000)])
def test_golden_hip_knee(eng, varian, implant):
    h = eng.hitung(ri(kode_cbg="M-1-04-I", kelas_rs="B", kepemilikan="SWASTA", icd9=["81.51"],
                      kode_spesial=[f"RR-04-III:{varian}"]))
    nilai = {t.kode_spesial: t.nilai for t in h.topup}
    assert h.tarif_dasar == 21_048_500
    assert nilai == {"RR-04-III": implant, "YY-01-II": 5_782_600}
    assert h.total_klaim_inacbg == 21_048_500 + implant + 5_782_600


def test_golden_streptokinase(eng):
    h = eng.hitung(ri(kode_cbg="I-4-10-I", kode_spesial=["DD-01-I"], icd10=["I21.0"]))
    assert [(t.kode_spesial, t.nilai, t.diterima) for t in h.topup] == [("DD-01-I", 4_850_700, True)]


def test_rs_khusus_nasional_tanpa_regional(eng):
    h = eng.hitung(InputKlaim(kode_cbg="A-4-10-I", rs_khusus_nasional="RSCM", kelas_rawat=3))
    assert h.regional == "NASIONAL" and h.tarif_dasar == 5_868_500 and h.sumber_halaman == 652


def test_rawat_jalan(eng):
    h = eng.hitung(InputKlaim(kode_cbg="B-2-10-0", provinsi="DKI Jakarta", kelas_rs="A",
                              kepemilikan="PEMERINTAH"))
    assert h.kelas_rawat is None and h.tarif_dasar == 1_390_000 and h.sumber_halaman == 102


# ------------------------------------------------------------ data
def test_data_lengkap():
    rows = list(csv.DictReader(open(os.path.join(DATA_DIR, "tarif_cbg.csv"), encoding="utf-8")))
    per_kode = Counter(r["kode_cbg"] for r in rows)
    jr = {r["kode_cbg"]: r["jenis_rawat"] for r in csv.DictReader(open(os.path.join(DATA_DIR, "cbg_group.csv")))}
    assert len(per_kode) == 1075
    assert {per_kode[k] for k in per_kode if jr[k] == "RI"} == {135}
    assert {per_kode[k] for k in per_kode if jr[k] == "RJ"} == {45}


def test_tarif_kelas_berurutan(eng):
    grup = {}
    for (kode, reg, kls, milik, nama, kelas), (t, ada, _) in eng.tarif.items():
        if kelas and ada:
            grup.setdefault((kode, reg, kls, milik, nama), {})[kelas] = t
    for g in grup.values():
        if len(g) == 3:
            assert g[1] >= g[2] >= g[3]


def test_pemicu_lampiran_ia_cocok_dengan_topup(eng):
    pasangan = {(k, c) for (k, _), d in eng.trigger.items() for c in d["cbg"]}
    assert pasangan == eng.pasangan_topup and len(pasangan) == 87


# ------------------------------------------------------------ ketersediaan & kriteria
def test_tarif_strip_tidak_tersedia(eng):
    h = eng.hitung(ri(kode_cbg="B-1-01-I", kelas_rs="B", kepemilikan="PEMERINTAH"))
    assert h.tarif_dasar_tersedia is False and h.tarif_dasar is None and h.total_klaim_inacbg is None


def test_contegra_hanya_rs_jantung_nasional(eng):
    h = eng.hitung(ri(kode_cbg="I-1-03-I", kode_spesial=["RR-02-II"]))
    assert h.topup[0].diterima is False
    h = eng.hitung(InputKlaim(kode_cbg="I-1-03-I", rs_khusus_nasional="RSJP-HK", kelas_rawat=1,
                              kode_spesial=["RR-02-II"]))
    assert h.topup[0].diterima is True and h.topup[0].nilai > 0


def test_hip_implant_ditolak_di_kelas_d(eng):
    h = eng.hitung(ri(kode_cbg="M-1-04-I", kelas_rs="D", kode_spesial=["RR-04-III:Hip Implant"]))
    assert h.topup[0].diterima is False


def test_evar_rs_khusus_lain_kelas_a_ditolak(eng):
    h = eng.hitung(ri(kode_cbg="I-1-20-I", tipe_rs="khusus_lain", kode_spesial=["RR-05-III"]))
    assert h.topup[0].diterima is False and "Kelas A Umum" in h.topup[0].alasan
    h = eng.hitung(ri(kode_cbg="I-1-20-I", tipe_rs="umum", kode_spesial=["RR-05-III"]))
    assert h.topup[0].diterima is True


def test_varian_wajib_dipilih(eng):
    with pytest.raises(KalkulatorError, match="varian"):
        eng.hitung(ri(kode_cbg="M-1-04-I", kode_spesial=["RR-04-III"]))


def test_kode_spesial_tidak_berlaku_untuk_cbg(eng):
    h = eng.hitung(ri(kode_cbg="A-4-10-I", kode_spesial=["YY-02-III"]))
    assert h.topup[0].diterima is False


def test_obat_hanya_kandidat_bila_dari_icd(eng):
    h = eng.hitung(ri(kode_cbg="I-4-10-I", icd10=["I21.0"]))
    assert h.topup == [] and [k["kode_spesial"] for k in h.kandidat_topup] == ["DD-01-I"]


def test_hemodialisis_reuse(eng):
    a = eng.hitung(InputKlaim(kode_cbg="N-3-15-0", provinsi="Bali", kelas_rs="C", kepemilikan="SWASTA"))
    b = eng.hitung(InputKlaim(kode_cbg="N-3-15-0", provinsi="Bali", kelas_rs="C", kepemilikan="SWASTA",
                              hd_reuse=True))
    assert b.tarif_dasar == R._bulat(a.tarif_dasar * 0.85)


# ------------------------------------------------------------ aturan hardcode
def test_regional_provinsi():
    assert R.regional_dari_provinsi("Jawa Barat") == 1
    assert R.regional_dari_provinsi("papua barat daya") == 5
    assert R.regional_dari_provinsi("Kepri") == 4
    assert sum(len(v) for v in R.REGIONAL_PROVINSI.values()) == 38
    with pytest.raises(ValueError):
        R.regional_dari_provinsi("Atlantis")


@pytest.mark.parametrize("los,fase", [(42, (42, 0, 0)), (43, (42, 1, 0)), (103, (42, 61, 0)),
                                      (104, (42, 61, 1)), (180, (42, 61, 77))])
def test_los_fase(los, fase):
    assert R.los_fase(los) == fase


def test_topup_subakut_kronis():
    h = R.topup_subakut_kronis(110, adl_subakut=30, adl_kronis=20)
    assert h["topup_subakut"] == round(0.375 * 0.5 * 879_103 * 61)
    assert h["topup_kronis"] == round(0.25 * (20 / 60) * 879_103 * 7)
    with pytest.raises(ValueError):
        R.topup_subakut_kronis(50)


def test_rs_khusus_di_luar_kekhususan_turun_kelas(eng):
    a = eng.hitung(ri(kode_cbg="A-4-10-I", kelas_rs="C"))
    b = eng.hitung(ri(kode_cbg="A-4-10-I", kelas_rs="B", tipe_rs="khusus_lain", sesuai_kekhususan=False))
    assert a.tarif_dasar == b.tarif_dasar


def test_klinik_utama(eng):
    d = eng.hitung(ri(kode_cbg="A-4-10-I", kelas_rs="D", kepemilikan="SWASTA"))
    k = eng.hitung(ri(kode_cbg="A-4-10-I", klinik_utama=True, kepemilikan="SWASTA", persen_klinik_utama=70))
    assert k.tarif_dasar == R._bulat(d.tarif_dasar * 0.7)
    assert k.rentang_total["total"] == [R._bulat(d.tarif_dasar * 0.7), d.tarif_dasar]


def test_selisih_naik_kelas(eng):
    h = eng.hitung(ri(kode_cbg="A-4-10-I", kelas_rawat=2, naik_kelas="1"))
    assert h.selisih_biaya["nilai"] == 4_924_100 - 4_313_200
    assert h.tarif_dasar == 4_313_200  # BPJS membayar sesuai hak kelas
    h = eng.hitung(ri(kode_cbg="A-4-10-I", kelas_rawat=1, naik_kelas="VIP"))
    assert h.selisih_biaya["maksimum"] == R._bulat(0.75 * 4_924_100)
    h = eng.hitung(ri(kode_cbg="A-4-10-I", kelas_rawat=1, naik_kelas="VIP", biaya_riil=4_000_000))
    assert h.selisih_biaya["berlaku"] is False
    h = eng.hitung(ri(kode_cbg="A-4-10-I", kelas_rawat=3, naik_kelas="1", jenis_peserta="PBI"))
    assert h.selisih_biaya["berlaku"] is False


def test_rawat_jalan_eksekutif(eng):
    h = eng.hitung(InputKlaim(kode_cbg="B-2-10-0", provinsi="Bali", kelas_rs="B", kepemilikan="SWASTA",
                              rawat_jalan_eksekutif=True))
    assert h.selisih_biaya["maksimum"] == 400_000


def test_disclaimer_selalu_ada(eng):
    assert "E-Klaim" in eng.hitung(ri(kode_cbg="A-4-10-I")).disclaimer
