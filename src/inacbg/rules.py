"""Aturan bisnis dari batang tubuh PMK 3/2023 (nomor halaman = halaman PDF)."""
import math

SUMBER = "Permenkes No. 3 Tahun 2023"

# Pasal 28 ayat (2), hal. 18-19
REGIONAL_PROVINSI = {
    1: ["DI Yogyakarta", "Jawa Barat", "Jawa Tengah", "Jawa Timur", "DKI Jakarta"],
    2: ["Nusa Tenggara Barat", "Bengkulu", "Sulawesi Tengah", "Kalimantan Barat", "Lampung",
        "Banten", "Sumatera Barat", "Bali", "Sumatera Utara"],
    3: ["Sulawesi Tenggara", "Jambi", "Sulawesi Barat", "Gorontalo"],
    4: ["Kalimantan Selatan", "Riau", "Kalimantan Tengah", "Kalimantan Timur", "Kalimantan Utara",
        "Kepulauan Riau", "Sumatera Selatan"],
    5: ["Sulawesi Selatan", "Papua Barat", "Papua Selatan", "Papua Tengah", "Papua Pegunungan",
        "Papua", "Papua Barat Daya", "Aceh", "Kepulauan Bangka Belitung", "Sulawesi Utara",
        "Nusa Tenggara Timur", "Maluku", "Maluku Utara"],
}
_ALIAS = {"diy": "di yogyakarta", "yogyakarta": "di yogyakarta", "daerah istimewa yogyakarta": "di yogyakarta",
          "jakarta": "dki jakarta", "dki": "dki jakarta", "ntb": "nusa tenggara barat",
          "ntt": "nusa tenggara timur", "babel": "kepulauan bangka belitung",
          "bangka belitung": "kepulauan bangka belitung", "kepri": "kepulauan riau",
          "sumut": "sumatera utara", "sumbar": "sumatera barat", "sumsel": "sumatera selatan",
          "jabar": "jawa barat", "jateng": "jawa tengah", "jatim": "jawa timur",
          "kalbar": "kalimantan barat", "kalsel": "kalimantan selatan", "kalteng": "kalimantan tengah",
          "kaltim": "kalimantan timur", "kaltara": "kalimantan utara", "sulsel": "sulawesi selatan",
          "sulteng": "sulawesi tengah", "sultra": "sulawesi tenggara", "sulbar": "sulawesi barat",
          "sulut": "sulawesi utara", "nad": "aceh", "nanggroe aceh darussalam": "aceh"}
_PROV = {p.lower(): r for r, ps in REGIONAL_PROVINSI.items() for p in ps}


def regional_dari_provinsi(provinsi):
    k = " ".join(provinsi.lower().replace("provinsi", "").split())
    k = _ALIAS.get(k, k)
    if k not in _PROV:
        raise ValueError(f"Provinsi tidak dikenal: {provinsi!r}. Pilihan: "
                         + ", ".join(sorted(p for ps in REGIONAL_PROVINSI.values() for p in ps)))
    return _PROV[k]


# Pasal 29, hal. 19: RS khusus di luar kekhususan -> satu tingkat lebih rendah
TURUN_SATU_TINGKAT = {"A": "B", "B": "C", "C": "D", "D": "D"}

# Pasal 31, hal. 19: klinik utama / setara
KLINIK_UTAMA_KELAS_RS = "D"
KLINIK_UTAMA_PERSEN_RI = (70, 100)

# Hal. 84: kasus sub-akut & kronis
UNIT_COST = 879_103
LOS_AKUT_MAKS = 42
LOS_SUBAKUT_MAKS = 103
LOS_KRONIS_MAKS = 180
FAKTOR_SUBAKUT = 0.375
FAKTOR_KRONIS = 0.25


def los_fase(los):
    """Pecah LOS menjadi hari fase akut, sub-akut, dan kronis (hal. 84).

    Fase sub akut: LOS - (LOS-103) - 42; bila (LOS-103) <= 0 -> LOS - 42.
    Fase kronis  : LOS - 103; bila <= 0 -> 0.
    """
    los = int(los)
    akut = min(los, LOS_AKUT_MAKS)
    subakut = max(0, min(los, LOS_SUBAKUT_MAKS) - LOS_AKUT_MAKS)
    kronis = max(0, los - LOS_SUBAKUT_MAKS)
    return akut, subakut, kronis


def topup_subakut_kronis(los, adl_subakut=None, adl_kronis=None):
    """Top up fase sub akut dan kronis (hal. 84).

    Top up sub akut = 0,375 x RIW sub akut x UC x LOS sub akut
    Top up kronis   = 0,25  x RIW kronis  x UC x LOS kronis
    RIW = skor ADL : 60. Hasil dibulatkan ke rupiah terdekat.
    """
    _, hs, hk = los_fase(los)
    hasil = {"los_subakut": hs, "los_kronis": hk, "topup_subakut": 0, "topup_kronis": 0,
             "riw_subakut": None, "riw_kronis": None}
    if hs:
        if adl_subakut is None:
            raise ValueError("LOS > 42 hari: isi skor ADL fase sub akut (adl_subakut)")
        riw = _riw(adl_subakut)
        hasil["riw_subakut"] = riw
        hasil["topup_subakut"] = _bulat(FAKTOR_SUBAKUT * riw * UNIT_COST * hs)
    if hk:
        if adl_kronis is None:
            raise ValueError("LOS > 103 hari: isi skor ADL fase kronis (adl_kronis)")
        riw = _riw(adl_kronis)
        hasil["riw_kronis"] = riw
        hasil["topup_kronis"] = _bulat(FAKTOR_KRONIS * riw * UNIT_COST * hk)
    return hasil


def _riw(adl):
    adl = float(adl)
    if not 0 < adl <= 60:
        raise ValueError(f"Skor ADL harus di antara 0 dan 60, didapat {adl}")
    return adl / 60


def _bulat(x):
    return int(math.floor(x + 0.5))


# Pasal 48, hal. 25-27: selisih biaya naik kelas
SELISIH_RJ_EKSEKUTIF_MAKS = 400_000
PERSEN_VIP_MAKS = 75
PESERTA_DIKECUALIKAN = {
    "PBI": "peserta Penerima Bantuan Iuran Jaminan Kesehatan",
    "PBPU_KELAS_3": "peserta Pekerja Bukan Penerima Upah kelas 3",
    "BP_KELAS_3": "peserta Bukan Pekerja kelas 3",
    "PEMDA": "peserta yang didaftarkan oleh Pemerintah Daerah",
    "PPU_PHK": "peserta Pekerja Penerima Upah yang mengalami PHK dan anggota keluarganya",
}


def selisih_naik_kelas(hak_kelas, naik_ke, tarif_kelas, biaya_riil=None):
    """Selisih biaya rawat inap (Pasal 48 ayat 3 huruf B-D dan ayat 4, hal. 26).

    tarif_kelas: {1: tarif INA-CBG kelas 1, 2: ..., 3: ...}
    naik_ke    : 1 atau "VIP" (kelas di atas kelas 1)
    Mengembalikan dict: nilai (pasti), maksimum (batas atas), dasar, berlaku, catatan.
    """
    naik_ke = "VIP" if str(naik_ke).upper() in ("VIP", "DI ATAS KELAS 1", "0") else int(naik_ke)
    k1, k2 = tarif_kelas.get(1), tarif_kelas.get(2)
    if hak_kelas == 2 and naik_ke == 1:
        v = k1 - k2
        return {"berlaku": True, "nilai": v, "maksimum": v,
                "dasar": "Pasal 48 ayat (3) huruf B: tarif kelas 1 - tarif kelas 2 (hal. 26)"}
    if naik_ke == "VIP" and hak_kelas in (1, 2):
        tarif_hak = tarif_kelas[hak_kelas]
        if biaya_riil is not None and biaya_riil <= tarif_hak:
            return {"berlaku": False, "nilai": 0, "maksimum": 0,
                    "dasar": "Pasal 48 ayat (4): biaya rawat inap tidak melebihi tarif INA-CBG "
                             "sesuai hak peserta, ketentuan selisih tidak berlaku (hal. 26)"}
        vip = _bulat(PERSEN_VIP_MAKS / 100 * k1)
        if hak_kelas == 1:
            return {"berlaku": True, "nilai": None, "maksimum": vip,
                    "dasar": "Pasal 48 ayat (3) huruf C: paling banyak 75% x tarif kelas 1 (hal. 26)"}
        return {"berlaku": True, "nilai": None, "maksimum": (k1 - k2) + vip, "pasti": k1 - k2,
                "dasar": "Pasal 48 ayat (3) huruf D: (tarif kelas 1 - kelas 2) + paling banyak "
                         "75% x tarif kelas 1 (hal. 26)"}
    return {"berlaku": False, "nilai": None, "maksimum": None,
            "dasar": f"Naik dari hak kelas {hak_kelas} ke {naik_ke} tidak diatur dalam "
                     "Pasal 48 ayat (3) (hal. 26)"}
