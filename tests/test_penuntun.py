"""Penuntun kode INA-CBG (estimasi). Case group mengikuti Tabel 2 PMK 26/2021."""
import pytest

from inacbg import penuntun as P
from inacbg.engine import INACBGEngine


@pytest.fixture(scope="module")
def eng():
    return INACBGEngine()


@pytest.fixture(scope="module")
def trig(eng):
    return [{"kode_spesial": d["kode_spesial"], "cbg": d["cbg"], "ICD10": d["ICD10"], "ICD9CM": d["ICD9CM"]}
            for d in eng.trigger.values()]


@pytest.mark.parametrize("jr,kat,pros,expected", [
    ("RI", "umum", True, [1]), ("RJ", "umum", True, [2, 3]), ("RI", "umum", False, [4]),
    ("RJ", "umum", False, [5]), ("RI", "kebidanan", False, [6]), ("RJ", "kebidanan", True, [7]),
    ("RI", "neonatal", True, [8]), ("RJ", "neonatal", False, [9]),
])
def test_case_group_tabel2(jr, kat, pros, expected):
    assert P.case_groups(jr, kat, pros) == expected


def test_case_group_cocok_dengan_data(eng):
    """Setiap kode di Lampiran III punya case group yang sesuai jenis rawatnya."""
    for k, r in eng.cbg.items():
        cg = int(r["case_type"])
        assert (cg in (1, 4, 6, 8)) == (r["jenis_rawat"] == "RI"), k


@pytest.mark.parametrize("kw,pertama", [
    (dict(icd10_utama="I21.0", icd9=["36.06"], jenis_rawat="RI"), "I-1-40"),   # PCI, Lampiran I.A
    (dict(icd10_utama="I21.0", jenis_rawat="RI"), "I-4-10"),                    # IMA, DD-01-I
    (dict(icd10_utama="A41.9", jenis_rawat="RI"), "A-4-10"),                    # sepsis, DD-05-II
    (dict(icd10_utama="M17.1", icd9=["81.54"], jenis_rawat="RI"), "M-1-04"),   # TKR, RR-04-III
])
def test_petunjuk_lampiran_ia_paling_atas(eng, trig, kw, pertama):
    h = P.tebak(eng.cbg, trig, **kw)
    assert h["kandidat"][0]["grup"] == pertama and h["kandidat"][0]["lampiran_ia"]


@pytest.mark.parametrize("dx,cmg", [("I63.9", "G"), ("K80.2", "B"), ("H25.9", "H"), ("N40", "V"),
                                    ("N60.1", "L"), ("F10.2", "T"), ("Z51.1", "C"), ("O80", "O"), ("J18.9", "J")])
def test_cmg_pertama_dari_icd10(eng, trig, dx, cmg):
    assert P.tebak(eng.cbg, trig, icd10_utama=dx, jenis_rawat="RI")["cmg"][0]["kode"] == cmg


def test_severity_dan_rawat_jalan(eng, trig):
    h = P.tebak(eng.cbg, trig, icd10_utama="A41.9", jenis_rawat="RI", severity="III")
    assert h["kandidat"][0]["kode_terpilih"] == "A-4-10-III"
    rj = P.tebak(eng.cbg, trig, icd10_utama="J06.9", jenis_rawat="RJ")
    assert all(k["kode_terpilih"].endswith("-0") for k in rj["kandidat"])
    assert {k["cmg"] for k in rj["kandidat"]} == {"Q"}


def test_sebab_luar_ditolak(eng, trig):
    h = P.tebak(eng.cbg, trig, icd10_utama="V89.2", jenis_rawat="RI")
    assert any("sebab luar" in p for p in h["peringatan"])


def test_semua_kandidat_ada_di_lampiran_iii(eng, trig):
    for dx in ["A09", "C50.9", "D48.5", "Q21.0", "R10.4", "T81.4", "Z38.0", "U07.1"]:
        for jr in ("RI", "RJ"):
            h = P.tebak(eng.cbg, trig, icd10_utama=dx, jenis_rawat=jr, maks=10_000)
            for k in h["kandidat"]:
                assert all(c in eng.cbg for c in k["kode"].values())


@pytest.fixture
def tebak(eng, trig):
    def f(dx, jr="RI"):
        kat = "kebidanan" if dx.startswith("O") else "umum"
        return P.tebak(eng.cbg, trig, icd10_utama=dx, jenis_rawat=jr, kategori=kat)
    return f


@pytest.mark.parametrize("dx,jr,kunci", [
    ("D63.0", "RI", "kode asterisk"), ("H28.0", "RJ", "kode asterisk"),
    ("O80.9", "RI", "cara persalinan"), ("O84.0", "RI", "cara persalinan"),
    ("R50.9", "RI", "gejala/tanda"),
])
def test_peringatan_aturan_koding_pmk26(tebak, dx, jr, kunci):
    h = tebak(dx, jr=jr)
    assert any(kunci in p for p in h["peringatan"]), h["peringatan"]


def test_tanpa_peringatan_koding_untuk_kasus_biasa(tebak):
    for dx, jr in (("R50.9", "RJ"), ("I21.0", "RI"), ("O42.9", "RI"), ("E11.3", "RI")):
        h = tebak(dx, jr=jr)
        assert not any("PMK 26/2021 hal." in p for p in h["peringatan"]), (dx, h["peringatan"])
