"""Engine kalkulator tarif INA-CBG (PMK 3/2023).

Pemakaian:
    from inacbg.engine import INACBGEngine, InputKlaim
    eng = INACBGEngine()
    hasil = eng.hitung(InputKlaim(kode_cbg="I-1-40-I", provinsi="Jawa Barat",
                                  kelas_rs="B", kepemilikan="SWASTA", kelas_rawat=1,
                                  icd9=["36.06"]))
"""
import csv
import os
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from . import kriteria as K
from . import rules as R

DISCLAIMER = ("Hasil ini estimasi/simulasi berdasarkan Permenkes No. 3 Tahun 2023. Angka final klaim "
              "ditentukan oleh grouper resmi E-Klaim INA-CBG (Kemenkes) dan verifikasi BPJS Kesehatan.")
RE_CBG = re.compile(r"^[A-Z]-\d-\d{2}-(I|II|III|0)$")
RS_KHUSUS_NASIONAL = {"RSCM", "RSJP-HK", "RSK DHARMAIS", "RSAB-HK", "RSPON"}
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "data", "processed")


class KalkulatorError(ValueError):
    """Input tidak valid / kombinasi tidak ada di tabel."""


@dataclass
class InputKlaim:
    kode_cbg: str
    # lokasi & profil RS
    provinsi: Optional[str] = None
    regional: Optional[int] = None
    kelas_rs: Optional[str] = None            # A/B/C/D
    kepemilikan: Optional[str] = None         # PEMERINTAH/SWASTA
    rs_khusus_nasional: Optional[str] = None  # RSCM/RSJP-HK/RSK DHARMAIS/RSAB-HK/RSPON
    tipe_rs: str = "umum"                     # umum / khusus_jantung / khusus_lain
    sesuai_kekhususan: bool = True            # untuk RS khusus (Pasal 29)
    klinik_utama: bool = False                # Pasal 31
    persen_klinik_utama: Optional[float] = None  # 70-100 untuk RI klinik utama
    # pasien
    kelas_rawat: Optional[int] = None         # hak kelas rawat inap 1/2/3
    icd10: List[str] = field(default_factory=list)
    icd9: List[str] = field(default_factory=list)
    kode_spesial: List[str] = field(default_factory=list)  # mis. "RR-04-III:Knee Implant"
    los: Optional[int] = None
    adl_subakut: Optional[float] = None
    adl_kronis: Optional[float] = None
    kasus_psikiatri_kusta: bool = False       # syarat top up sub akut/kronis (PMK 26/2021 hal. 20)
    hd_reuse: bool = False
    # selisih biaya
    naik_kelas: Optional[str] = None          # "1" atau "VIP"
    rawat_jalan_eksekutif: bool = False
    jenis_peserta: Optional[str] = None       # PBI/PBPU_KELAS_3/BP_KELAS_3/PEMDA/PPU_PHK/lainnya
    biaya_riil: Optional[int] = None


@dataclass
class TopUp:
    kode_spesial: str
    deskripsi: str
    nilai: Optional[int]
    diterima: bool
    sumber: str                  # "dipilih" / "otomatis dari ICD-9-CM"
    alasan: str = ""
    sumber_halaman: Optional[int] = None


@dataclass
class HasilKlaim:
    kode_cbg: str
    deskripsi_cbg: str
    jenis_rawat: str
    kelompok_tarif: str
    regional: str
    kelas_rawat: Optional[int]
    tarif_dasar: Optional[int]
    tarif_dasar_tersedia: bool
    sumber_halaman: Optional[int]
    topup: List[TopUp] = field(default_factory=list)
    kandidat_topup: List[dict] = field(default_factory=list)
    topup_subakut_kronis: Optional[dict] = None
    total_klaim_inacbg: Optional[int] = None
    rentang_total: Optional[dict] = None
    selisih_biaya: Optional[dict] = None
    peringatan: List[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER

    def to_dict(self):
        return asdict(self)


class TariffEngine(ABC):
    """Antarmuka engine tarif; INA-CBG sekarang, iDRG bisa ditambahkan nanti."""

    @abstractmethod
    def hitung(self, inp: InputKlaim) -> HasilKlaim:
        ...


def _baca_csv(nama, data_dir):
    with open(os.path.join(data_dir, nama), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _int(v):
    return int(v) if v not in (None, "") else None


def _none(v):
    return v if v not in (None, "") else None


class INACBGEngine(TariffEngine):
    def __init__(self, data_dir=DATA_DIR):
        self.cbg = {r["kode_cbg"]: r for r in _baca_csv("cbg_group.csv", data_dir)}
        self.special = {r["kode_spesial"]: r for r in _baca_csv("special_cmg.csv", data_dir)}
        self.tarif = {}
        for r in _baca_csv("tarif_cbg.csv", data_dir):
            key = (r["kode_cbg"], r["regional"], r["kelas_rs"], _none(r["kepemilikan"]),
                   _none(r["nama_rs_khusus"]), _int(r["kelas_rawat"]))
            self.tarif[key] = (_int(r["tarif"]), r["tersedia"] == "True", int(r["sumber_halaman"]))
        self.topup = {}
        for r in _baca_csv("tarif_topup.csv", data_dir):
            key = (r["kode_spesial"], r["kode_cbg"], r["regional"], r["kelas_rs"], _none(r["kepemilikan"]),
                   _none(r["nama_rs_khusus"]), _int(r["kelas_rawat"]))
            self.topup.setdefault(key, []).append(
                (r["deskripsi_spesial"], _int(r["tarif"]), r["tersedia"] == "True", int(r["sumber_halaman"])))
        self.pasangan_topup = {(k[0], k[1]) for k in self.topup}
        # pemicu Lampiran I.A
        self.trigger = {}
        for r in _baca_csv("special_cmg_trigger.csv", data_dir):
            kk = (r["kode_spesial"], int(r["sub_kriteria"]))
            d = self.trigger.setdefault(kk, {"kode_spesial": r["kode_spesial"], "cbg": set(),
                                             "ICD10": set(), "ICD9CM": set(), "halaman": set()})
            d["cbg"].add(r["kode_cbg"])
            if r["tipe_kode"] in ("ICD10", "ICD9CM"):
                d[r["tipe_kode"]].add(r["kode"])
            d["halaman"].update(int(x) for x in str(r["sumber_halaman"]).split(","))

    # ---------------------------------------------------------- utilitas
    def cari_cbg(self, kata):
        kata = kata.upper()
        return [r for r in self.cbg.values() if kata in r["kode_cbg"] or kata in r["deskripsi"].upper()]

    def _profil_rs(self, inp, peringatan):
        if inp.rs_khusus_nasional:
            nama = inp.rs_khusus_nasional.upper()
            if nama not in RS_KHUSUS_NASIONAL:
                raise KalkulatorError(f"RS khusus nasional harus salah satu dari {sorted(RS_KHUSUS_NASIONAL)}")
            if not inp.sesuai_kekhususan:
                peringatan.append("PMK 3/2023 tidak mengatur kelompok tarif yang lebih rendah untuk RS "
                                  "kelompok (a); tarif kelompok RS khusus nasional tetap dipakai.")
            return {"kelas_rs": "KHUSUS_NASIONAL", "kepemilikan": None, "nama_rs_khusus": nama,
                    "regional": "NASIONAL", "tipe_rs": inp.tipe_rs,
                    "label": f"RS khusus nasional {nama}"}
        regional = inp.regional
        if inp.provinsi:
            r_prov = R.regional_dari_provinsi(inp.provinsi)
            if regional is not None and int(regional) != r_prov:
                raise KalkulatorError(f"Provinsi {inp.provinsi} termasuk regional {r_prov}, bukan {regional}")
            regional = r_prov
        if regional is None:
            raise KalkulatorError("Isi provinsi atau regional (1-5)")
        if int(regional) not in R.REGIONAL_PROVINSI:
            raise KalkulatorError("Regional harus 1-5")
        milik = (inp.kepemilikan or "").upper()
        if inp.klinik_utama:
            milik = milik or "SWASTA"
            kelas = R.KLINIK_UTAMA_KELAS_RS
            label = f"Klinik utama (kelompok RS kelas D {milik})"
        else:
            kelas = (inp.kelas_rs or "").upper()
            if kelas not in ("A", "B", "C", "D"):
                raise KalkulatorError("Isi kelas RS (A/B/C/D) atau rs_khusus_nasional")
            label = f"RS kelas {kelas} {milik}"
            if inp.tipe_rs.startswith("khusus") and not inp.sesuai_kekhususan:
                baru = R.TURUN_SATU_TINGKAT[kelas]
                if baru == kelas:
                    peringatan.append("RS khusus kelas D di luar kekhususan: tidak ada kelompok tarif "
                                      "yang lebih rendah, tetap memakai kelas D (Pasal 29, hal. 19).")
                else:
                    peringatan.append(f"Pelayanan RS khusus di luar kekhususan: tarif turun satu tingkat "
                                      f"dari kelas {kelas} ke kelas {baru} (Pasal 29 ayat 2, hal. 19).")
                label = f"RS khusus kelas {kelas} {milik}, di luar kekhususan -> tarif kelas {baru}"
                kelas = baru
        if milik not in ("PEMERINTAH", "SWASTA"):
            raise KalkulatorError("Isi kepemilikan: PEMERINTAH atau SWASTA")
        return {"kelas_rs": kelas, "kepemilikan": milik, "nama_rs_khusus": None,
                "regional": str(int(regional)), "tipe_rs": inp.tipe_rs, "label": label}

    def _tarif(self, kode, rs, kelas_rawat):
        return self.tarif.get((kode, rs["regional"], rs["kelas_rs"], rs["kepemilikan"],
                               rs["nama_rs_khusus"], kelas_rawat))

    def _topup_tarif(self, kode_sps, kode, rs, kelas_rawat):
        return self.topup.get((kode_sps, kode, rs["regional"], rs["kelas_rs"], rs["kepemilikan"],
                               rs["nama_rs_khusus"], kelas_rawat), [])

    def _cocok_pemicu(self, kode_sps, kode_cbg, icd10, icd9):
        """True/False bila ICD diisi; None bila tidak bisa dinilai (ICD kosong)."""
        komb = [d for (k, _), d in self.trigger.items() if k == kode_sps and kode_cbg in d["cbg"]]
        if not komb:
            return False, None
        if not icd10 and not icd9:
            return None, komb[0]
        for d in komb:
            ok10 = not d["ICD10"] or bool(d["ICD10"] & icd10)
            ok9 = not d["ICD9CM"] or bool(d["ICD9CM"] & icd9)
            if ok10 and ok9:
                return True, d
        return False, komb[0]

    # --------------------------------------------------------------- inti
    def hitung(self, inp: InputKlaim) -> HasilKlaim:
        peringatan = []
        kode = inp.kode_cbg.strip().upper()
        if not RE_CBG.match(kode):
            raise KalkulatorError(f"Format kode CBG tidak valid: {inp.kode_cbg!r} (contoh: I-1-40-I)")
        if kode not in self.cbg:
            raise KalkulatorError(f"Kode CBG {kode} tidak ada di Lampiran III PMK 3/2023")
        cbg = self.cbg[kode]
        jr = cbg["jenis_rawat"]
        rs = self._profil_rs(inp, peringatan)

        kelas = None
        if jr == "RI":
            if inp.kelas_rawat not in (1, 2, 3):
                raise KalkulatorError("Kode CBG rawat inap: isi kelas_rawat (hak kelas peserta) 1/2/3")
            kelas = int(inp.kelas_rawat)
        elif inp.kelas_rawat is not None:
            peringatan.append("Kode CBG rawat jalan: kelas rawat diabaikan (rawat jalan satu tarif).")

        t = self._tarif(kode, rs, kelas)
        if t is None:
            raise KalkulatorError("Kombinasi tarif tidak ditemukan di tabel")
        tarif, tersedia, hal = t
        hasil = HasilKlaim(kode_cbg=kode, deskripsi_cbg=cbg["deskripsi"],
                           jenis_rawat="RAWAT INAP" if jr == "RI" else "RAWAT JALAN",
                           kelompok_tarif=rs["label"], regional=rs["regional"], kelas_rawat=kelas,
                           tarif_dasar=tarif, tarif_dasar_tersedia=tersedia, sumber_halaman=hal,
                           peringatan=peringatan)
        if not tersedia:
            peringatan.append(f"Layanan {kode} tidak tersedia/tidak dijamin untuk {rs['label']} "
                              f"(tarif '-' di PDF hal. {hal}).")
            return hasil

        # penyesuaian tarif dasar
        rentang = None
        if kode in K.KRITERIA_CBG["HEMODIALISIS"]["kode_cbg"] and inp.hd_reuse:
            persen = K.KRITERIA_CBG["HEMODIALISIS"]["persen_reuse"]
            tarif = R._bulat(tarif * persen / 100)
            peringatan.append(f"Hemodialisis re-use: tarif dibayar {persen}% dari tarif (Lampiran II, hal. 91).")
        elif inp.hd_reuse:
            peringatan.append("hd_reuse hanya berlaku untuk hemodialisis (N-3-15-0); diabaikan.")
        if inp.klinik_utama and jr == "RI":
            lo, hi = R.KLINIK_UTAMA_PERSEN_RI
            persen = inp.persen_klinik_utama if inp.persen_klinik_utama is not None else hi
            if not lo <= persen <= hi:
                raise KalkulatorError(f"persen_klinik_utama harus {lo}-{hi}")
            rentang = {"persen": [lo, hi], "tarif_dasar": [R._bulat(tarif * lo / 100), tarif]}
            tarif = R._bulat(tarif * persen / 100)
            peringatan.append(f"Klinik utama rawat inap: {persen}% dari tarif RS kelas D (rentang "
                              f"{lo}%-{hi}% sesuai kesepakatan BPJS Kesehatan dan asosiasi; Pasal 31, hal. 19).")
        hasil.tarif_dasar = tarif

        # top up special CMG
        icd10 = {c.strip().upper() for c in inp.icd10 if c.strip()}
        icd9 = {c.strip() for c in inp.icd9 if c.strip()}
        dipilih = {}
        for item in inp.kode_spesial:
            k_, _, var = item.partition(":")
            dipilih[k_.strip().upper()] = var.strip() or None
        sumber_auto = {}
        for (ksp, _), d in self.trigger.items():
            if kode not in d["cbg"] or ksp in dipilih:
                continue
            ok, _ = self._cocok_pemicu(ksp, kode, icd10, icd9)
            if not ok:
                continue
            prefix = ksp[:2]
            if prefix in ("YY", "II"):
                sumber_auto[ksp] = None
            elif ksp not in {k["kode_spesial"] for k in hasil.kandidat_topup}:
                hasil.kandidat_topup.append({
                    "kode_spesial": ksp, "deskripsi": self.special[ksp]["deskripsi"],
                    "jenis": self.special[ksp]["jenis_spesial"],
                    "keterangan": "Pemicu ICD cocok; tambahkan lewat kode_spesial bila "
                                  "obat/alat ini benar diberikan (Lampiran I.A)."})
        for ksp, var in list(dipilih.items()) + list(sumber_auto.items()):
            asal = "dipilih" if ksp in dipilih else "otomatis dari ICD"
            hasil.topup.append(self._nilai_topup(ksp, var, kode, jr, rs, kelas, icd10, icd9, asal, peringatan))

        # sub akut & kronis: hanya kasus psikiatri dan kusta (Permenkes 26/2021 hal. 20 sampai 21)
        if inp.los is not None and int(inp.los) > R.LOS_AKUT_MAKS:
            if jr != "RI":
                raise KalkulatorError("Kasus sub akut/kronis hanya untuk rawat inap")
            if not inp.kasus_psikiatri_kusta:
                peringatan.append("Top up sub akut dan kronis hanya untuk kasus psikiatri dan kusta "
                                  "(Permenkes 26/2021 hal. 20); lama rawat tidak menambah tarif.")
            else:
                sk = R.topup_subakut_kronis(inp.los, inp.adl_subakut, inp.adl_kronis)
                sk["dasar"] = ("Perhitungan tarif special groups kasus sub-akut dan kronis (PMK 3/2023 hal. 84); "
                               "skor ADL dari WHODAS 2.0 (PMK 26/2021 hal. 21)")
                hasil.topup_subakut_kronis = sk
                if int(inp.los) > R.LOS_KRONIS_MAKS:
                    peringatan.append(f"LOS {inp.los} hari: perawatan lebih dari {R.LOS_KRONIS_MAKS} hari "
                                      "diklaim sebagai satu episode dengan fase kronis (PMK 26/2021 hal. 21).")

        total = hasil.tarif_dasar + sum(t.nilai for t in hasil.topup if t.diterima)
        if hasil.topup_subakut_kronis:
            total += hasil.topup_subakut_kronis["topup_subakut"] + hasil.topup_subakut_kronis["topup_kronis"]
        hasil.total_klaim_inacbg = total
        if rentang:
            selisih_naik = total - hasil.tarif_dasar
            hasil.rentang_total = {"persen": rentang["persen"],
                                   "total": [rentang["tarif_dasar"][0] + selisih_naik,
                                             rentang["tarif_dasar"][1] + selisih_naik]}

        # selisih biaya
        if inp.naik_kelas or inp.rawat_jalan_eksekutif:
            hasil.selisih_biaya = self._selisih(inp, kode, jr, rs, kelas, peringatan)

        for nama, kr in K.KRITERIA_CBG.items():
            if kode in kr["kode_cbg"]:
                peringatan.extend(f"{nama.title()}: {c} (Lampiran II, hal. {kr['halaman']})." for c in kr["catatan"])
        return hasil

    def _nilai_topup(self, ksp, var, kode, jr, rs, kelas, icd10, icd9, asal, peringatan):
        if ksp not in self.special:
            raise KalkulatorError(f"Kode special CMG {ksp} tidak dikenal")
        sp = self.special[ksp]
        if (ksp, kode) not in self.pasangan_topup:
            return TopUp(ksp, sp["deskripsi"], None, False, asal,
                         f"{ksp} tidak berlaku untuk CBG {kode} (Lampiran I.B)")
        baris = self._topup_tarif(ksp, kode, rs, kelas if jr == "RI" else None)
        varian = [b[0] for b in baris]
        if len(varian) > 1:
            if var is None:
                raise KalkulatorError(f"{ksp} punya beberapa varian, pilih salah satu: "
                                      + ", ".join(f"'{ksp}:{v}'" for v in varian))
            cocok = [b for b in baris if b[0].lower() == var.lower()]
            if not cocok:
                raise KalkulatorError(f"Varian {var!r} tidak ada untuk {ksp}; pilihan: {varian}")
            baris = cocok
        desk, nilai, tersedia, hal = baris[0]
        tu = TopUp(ksp, desk, nilai, True, asal, sumber_halaman=hal)
        if not tersedia:
            tu.diterima, tu.nilai = False, None
            tu.alasan = f"tidak dijamin untuk {rs['label']} (tarif '-' di PDF hal. {hal})"
            return tu
        kr = K.KRITERIA.get(ksp)
        if kr:
            if kr.get("syarat_rs") and not kr["syarat_rs"](rs):
                tu.diterima, tu.nilai = False, None
                tu.alasan = f"kriteria RS tidak terpenuhi: {kr['syarat_rs_teks']} (Lampiran II, hal. {kr['halaman']})"
                return tu
            if kr.get("jenis_rawat") and kr["jenis_rawat"] != jr:
                tu.diterima, tu.nilai = False, None
                tu.alasan = (f"hanya untuk {'rawat inap' if kr['jenis_rawat'] == 'RI' else 'rawat jalan'} "
                             f"(Lampiran II, hal. {kr['halaman']})")
                return tu
            peringatan.extend(f"{ksp} {kr['layanan']}: pastikan {c} (Lampiran II, hal. {kr['halaman']})."
                              for c in kr["catatan"])
        if asal == "dipilih":
            ok, d = self._cocok_pemicu(ksp, kode, icd10, icd9)
            if ok is None:
                syarat = []
                if d and d["ICD10"]:
                    syarat.append("ICD-10 " + ", ".join(sorted(d["ICD10"])[:6]) + ("..." if len(d["ICD10"]) > 6 else ""))
                if d and d["ICD9CM"]:
                    syarat.append("ICD-9-CM " + ", ".join(sorted(d["ICD9CM"])[:6]) + ("..." if len(d["ICD9CM"]) > 6 else ""))
                peringatan.append(f"{ksp}: ICD belum diisi, pemicu tidak dicek. Syarat Lampiran I.A: "
                                  + "; ".join(syarat) + ".")
            elif ok is False:
                peringatan.append(f"{ksp}: ICD yang diisi tidak cocok dengan pemicu Lampiran I.A "
                                  f"(hal. {', '.join(map(str, sorted(d['halaman'])))}); top up berisiko ditolak.")
        return tu

    def _selisih(self, inp, kode, jr, rs, kelas, peringatan):
        jp = (inp.jenis_peserta or "").upper()
        if jp in R.PESERTA_DIKECUALIKAN:
            return {"berlaku": False, "nilai": None, "maksimum": None,
                    "dasar": f"Tidak boleh naik kelas dengan selisih biaya: {R.PESERTA_DIKECUALIKAN[jp]} "
                             "(Pasal 48 ayat 8, hal. 26-27)"}
        if inp.rawat_jalan_eksekutif:
            if jr != "RJ":
                peringatan.append("Rawat jalan eksekutif dipilih untuk CBG rawat inap; diabaikan.")
            else:
                return {"berlaku": True, "nilai": None, "maksimum": R.SELISIH_RJ_EKSEKUTIF_MAKS,
                        "dasar": "Pasal 48 ayat (3) huruf A: rawat jalan eksekutif paling banyak Rp400.000 (hal. 26)"}
        if jr != "RI":
            return {"berlaku": False, "nilai": None, "maksimum": None,
                    "dasar": "Naik kelas hanya berlaku untuk rawat inap"}
        tk = {}
        for k in (1, 2, 3):
            t = self._tarif(kode, rs, k)
            if not t or not t[1]:
                return {"berlaku": False, "nilai": None, "maksimum": None,
                        "dasar": f"Tarif kelas {k} tidak tersedia, selisih tidak bisa dihitung"}
            tk[k] = t[0]
        s = R.selisih_naik_kelas(kelas, inp.naik_kelas, tk, inp.biaya_riil)
        s["tarif_kelas"] = tk
        return s
