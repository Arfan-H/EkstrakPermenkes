"""Penuntun kode INA-CBG (ESTIMASI, bukan grouper resmi).

Grouper resmi E-Klaim memakai tabel yang tidak dipublikasikan. Modul ini hanya
menyempitkan pilihan kode CBG dari jawaban pengguna:

1. Case group (digit ke-2) dari Tabel 2 Permenkes 26/2021 hal. 12: rawat inap
   atau jalan, kategori (umum, kebidanan, neonatal), dan ada tidaknya prosedur.
2. CMG (huruf pertama) DITEBAK dari bab/blok ICD-10 diagnosis utama dan bab
   ICD-9-CM prosedur. Tabel pemetaannya (ICD10_KE_CMG, ICD9_KE_CMG) DISUSUN
   untuk proyek ini dari struktur bab ICD dan isi grup di Lampiran III PMK
   3/2023; ini BUKAN tabel resmi Kemenkes.
3. Petunjuk kuat: diagnosis/prosedur yang tercantum di Lampiran I.A PMK 3/2023
   bersama kode CBG tertentu.
4. Severity (digit ke-4) dipilih pengguna sesuai definisi PMK 26/2021 hal. 12.
"""
import re

DISCLAIMER_PENUNTUN = (
    "ESTIMASI. Penuntun ini menyempitkan pilihan kode dari struktur kode resmi (PMK 26/2021) dan "
    "pemetaan bab ICD yang disusun sendiri. Kode final ditentukan oleh grouper E-Klaim INA-CBG (Kemenkes).")

SEMUA = "*"  # CMG mengikuti organ; semua CMG dipertimbangkan

# (dari, sampai, CMG kandidat berurutan, catatan). Kunci = huruf + 2 digit ICD-10.
# Bila beberapa baris cocok, yang rentangnya paling sempit dipakai.
ICD10_KE_CMG = [
    ("A00", "B99", "A", "Bab I penyakit infeksi dan parasit"),
    ("A00", "A09", "A|K", "infeksi usus"),
    ("A15", "A19", "A|J", "tuberkulosis"),
    ("B15", "B19", "B|A", "hepatitis virus"),
    ("C00", "D48", "C|*", "Bab II neoplasma"),
    ("C00", "C14", "U|C", "neoplasma ganas bibir, mulut, faring"),
    ("C15", "C26", "K|B|C", "neoplasma ganas organ pencernaan"),
    ("C30", "C39", "J|C", "neoplasma ganas organ pernapasan"),
    ("C40", "C41", "M|C", "neoplasma ganas tulang"),
    ("C43", "C44", "L|C", "neoplasma ganas kulit"),
    ("C45", "C49", "M|J|C", "neoplasma ganas jaringan lunak dan mesotel"),
    ("C50", "C50", "L|C", "neoplasma ganas payudara"),
    ("C51", "C58", "W|C", "neoplasma ganas organ genital perempuan"),
    ("C60", "C63", "V|C", "neoplasma ganas organ genital laki-laki"),
    ("C64", "C68", "N|C", "neoplasma ganas saluran kemih"),
    ("C69", "C72", "G|H|C", "neoplasma ganas mata, otak, saraf pusat"),
    ("C73", "C75", "E|C", "neoplasma ganas kelenjar endokrin"),
    ("C81", "C96", "C|D", "neoplasma ganas jaringan limfoid dan hematopoietik"),
    ("D10", "D48", "*|C", "neoplasma jinak, in situ, perilaku tak tentu: CMG mengikuti organ"),
    ("D50", "D89", "D", "Bab III darah dan imun"),
    ("E00", "E90", "E", "Bab IV endokrin, nutrisi, metabolik"),
    ("F00", "F99", "F", "Bab V gangguan mental dan perilaku"),
    ("F00", "F09", "F|G", "gangguan mental organik"),
    ("F10", "F19", "T|Q", "gangguan akibat zat psikoaktif"),
    ("G00", "G99", "G", "Bab VI sistem saraf"),
    ("H00", "H59", "H", "Bab VII mata dan adneksa"),
    ("H60", "H95", "U", "Bab VIII telinga"),
    ("I00", "I99", "I", "Bab IX sistem sirkulasi"),
    ("I60", "I69", "G|I", "penyakit serebrovaskular"),
    ("J00", "J99", "J", "Bab X sistem pernapasan"),
    ("J00", "J06", "U|J", "infeksi saluran napas atas akut"),
    ("J30", "J39", "U|J", "penyakit saluran napas atas lainnya"),
    ("K00", "K93", "K", "Bab XI sistem pencernaan"),
    ("K00", "K14", "U|Q", "rongga mulut, gigi, kelenjar ludah"),
    ("K70", "K77", "B", "penyakit hati"),
    ("K80", "K87", "B", "kandung empedu, saluran empedu, pankreas"),
    ("L00", "L99", "L", "Bab XII kulit"),
    ("M00", "M99", "M", "Bab XIII muskuloskeletal"),
    ("N00", "N99", "N", "Bab XIV sistem genitourinaria"),
    ("N40", "N51", "V", "organ genital laki-laki"),
    ("N60", "N64", "L", "payudara"),
    ("N70", "N98", "W", "organ genital perempuan"),
    ("O00", "O99", "O", "Bab XV kehamilan, persalinan, nifas"),
    ("O00", "O08", "O|W|Q", "kehamilan dengan hasil abortif"),
    ("P00", "P96", "P", "Bab XVI kondisi perinatal"),
    ("Q00", "Q99", "*", "Bab XVII kelainan kongenital: CMG mengikuti organ"),
    ("Q00", "Q07", "G|P", "kelainan kongenital sistem saraf"),
    ("Q10", "Q18", "H|U", "kelainan kongenital mata, telinga, wajah, leher"),
    ("Q20", "Q28", "I|P", "kelainan kongenital sistem sirkulasi"),
    ("Q30", "Q34", "J|U", "kelainan kongenital sistem pernapasan"),
    ("Q35", "Q37", "U", "celah bibir dan langit-langit"),
    ("Q38", "Q45", "K|U", "kelainan kongenital sistem pencernaan"),
    ("Q50", "Q56", "W|V", "kelainan kongenital organ genital"),
    ("Q60", "Q64", "N", "kelainan kongenital saluran kemih"),
    ("Q65", "Q79", "M", "kelainan kongenital muskuloskeletal"),
    ("R00", "R99", "Z|*", "Bab XVIII gejala dan tanda"),
    ("R00", "R09", "I|J|Z", "gejala sirkulasi dan pernapasan"),
    ("R10", "R19", "K|Z", "gejala pencernaan"),
    ("R20", "R23", "L|Z", "gejala kulit"),
    ("R25", "R29", "G|M|Z", "gejala saraf dan muskuloskeletal"),
    ("R30", "R39", "N|Z", "gejala saluran kemih"),
    ("R40", "R46", "G|F|Z", "gejala kesadaran, kognisi, emosi"),
    ("R50", "R69", "A|Z", "gejala umum (termasuk demam)"),
    ("S00", "T98", "S", "Bab XIX cedera, keracunan"),
    ("T20", "T32", "S|L", "luka bakar"),
    ("T80", "T88", "S|*", "komplikasi tindakan medis: CMG bisa mengikuti organ"),
    ("U00", "U85", "A|J", "kode tujuan khusus (termasuk COVID-19)"),
    ("V01", "Y98", "", "Bab XX sebab luar: tidak dipakai sebagai diagnosis utama"),
    ("Z00", "Z99", "Z", "Bab XXI faktor status kesehatan"),
    ("Z30", "Z39", "O|W|Q", "layanan terkait reproduksi dan kehamilan"),
    ("Z38", "Z38", "P", "bayi lahir hidup"),
]
# Kode lebih spesifik dari kunci 3 karakter (awalan kode lengkap).
ICD10_AWALAN = [
    ("Z51.0", "C|Z", "radioterapi"),
    ("Z51.1", "C|Z", "kemoterapi"),
]

# ICD-9-CM: (dari, sampai, CMG, catatan) berdasarkan 2 digit pertama; awalan khusus di bawahnya.
ICD9_KE_CMG = [
    (0, 0, "*", "prosedur dan intervensi lain"),
    (1, 5, "G", "operasi sistem saraf"),
    (6, 7, "E", "operasi sistem endokrin"),
    (8, 16, "H", "operasi mata"),
    (18, 20, "U", "operasi telinga"),
    (21, 29, "U", "operasi hidung, mulut, faring"),
    (30, 34, "J", "operasi sistem pernapasan"),
    (35, 39, "I", "operasi sistem kardiovaskular"),
    (40, 41, "D", "operasi sistem hemik dan limfatik"),
    (42, 54, "K", "operasi sistem pencernaan"),
    (50, 52, "B", "operasi hati, saluran empedu, pankreas"),
    (55, 59, "N", "operasi saluran kemih"),
    (60, 64, "V", "operasi organ genital laki-laki"),
    (65, 71, "W", "operasi organ genital perempuan"),
    (72, 75, "O", "prosedur obstetri"),
    (76, 84, "M", "operasi muskuloskeletal"),
    (85, 86, "L", "operasi integumen dan payudara"),
    (87, 99, "Z|*", "prosedur diagnostik dan terapeutik lain"),
]
ICD9_AWALAN = [
    ("39.95", "N", "hemodialisis"),
    ("92.2", "C", "radioterapi"),
    ("92.3", "C", "radiosurgery"),
    ("99.25", "C", "kemoterapi"),
]

# Tabel 2 Permenkes 26/2021 hal. 12
CASE_GROUP = {1: "Prosedur Rawat Inap", 2: "Prosedur Besar Rawat Jalan", 3: "Prosedur Signifikan Rawat Jalan",
              4: "Rawat Inap Bukan Prosedur", 5: "Rawat Jalan Bukan Prosedur", 6: "Rawat Inap Kebidanan",
              7: "Rawat Jalan Kebidanan", 8: "Rawat Inap Neonatal", 9: "Rawat Jalan Neonatal"}
# Definisi severity, Permenkes 26/2021 hal. 12
SEVERITY = {"I": "Ringan: tanpa komplikasi maupun komorbiditas",
            "II": "Sedang: dengan komplikasi dan komorbiditas ringan (mild)",
            "III": "Berat: dengan komplikasi dan komorbiditas mayor (major)"}

RE_ICD10 = re.compile(r"^([A-Z])(\d{2})(?:\.(\d{1,2}))?$")
RE_ICD9 = re.compile(r"^(\d{2})(?:\.(\d{1,2}))?$")


def case_groups(jenis_rawat, kategori="umum", ada_prosedur=False):
    """Case group yang mungkin (Tabel 2 PMK 26/2021). jenis_rawat 'RI' / 'RJ'."""
    ri = jenis_rawat == "RI"
    if kategori == "neonatal":
        return [8] if ri else [9]
    if kategori == "kebidanan":
        if ri:
            return [6]
        return [7] if ada_prosedur else [5]
    if ri:
        return [1] if ada_prosedur else [4]
    return [2, 3] if ada_prosedur else [5]


def _baris_icd10(kode):
    kode = kode.strip().upper()
    m = RE_ICD10.match(kode)
    if not m:
        return None, kode
    for awal, cmg, cat in ICD10_AWALAN:
        if kode.startswith(awal):
            return (awal, awal, cmg, cat), kode
    kunci = m.group(1) + m.group(2)
    cocok = [b for b in ICD10_KE_CMG if b[0] <= kunci <= b[1]]
    if not cocok:
        return None, kode
    lebar = lambda b: (ord(b[1][0]) - ord(b[0][0])) * 100 + int(b[1][1:]) - int(b[0][1:])
    return min(cocok, key=lebar), kode


def _baris_icd9(kode):
    kode = kode.strip()
    m = RE_ICD9.match(kode)
    if not m:
        return None
    for awal, cmg, cat in ICD9_AWALAN:
        if kode.startswith(awal):
            return (awal, awal, cmg, cat)
    n = int(m.group(1))
    cocok = [b for b in ICD9_KE_CMG if b[0] <= n <= b[1]]
    return min(cocok, key=lambda b: b[1] - b[0]) if cocok else None


def tebak(cbg, trigger, icd10_utama=None, icd9=(), jenis_rawat="RI", kategori="umum",
          ada_prosedur=None, severity=None, maks=60):
    """Kandidat kode CBG.

    cbg     : {kode_cbg: {"deskripsi", "jenis_rawat", "cmg", "case_type", ...}} (cbg_group.csv)
    trigger : daftar kombinasi Lampiran I.A [{"kode_spesial", "cbg": set, "ICD10": set, "ICD9CM": set}]
    """
    icd9 = [k.strip() for k in icd9 if k and k.strip()]
    if ada_prosedur is None:
        ada_prosedur = bool(icd9)
    jr = "RI" if jenis_rawat == "RI" else "RJ"
    groups = case_groups(jr, kategori, ada_prosedur)
    alasan_cmg, urut, peringatan = {}, [], []

    def tambah(cmgs, alasan):
        for c in cmgs.split("|"):
            if c and c not in alasan_cmg:
                alasan_cmg[c] = alasan
                urut.append(c)

    dx = (icd10_utama or "").strip().upper()
    if kategori == "neonatal":
        tambah("P", "kategori neonatal")
    elif kategori == "kebidanan" and groups != [5]:
        tambah("O", "kategori kebidanan")
    if dx:
        b, dx = _baris_icd10(dx)
        if b is None:
            peringatan.append(f"Kode ICD-10 {dx!r} tidak dikenali; format yang benar mis. I21.0 atau K35.")
        elif b[2] == "":
            peringatan.append(f"{dx}: {b[3]}. Pilih diagnosis penyakit sebagai diagnosis utama.")
        else:
            tambah(b[2], f"diagnosis utama {dx}: {b[3]}")
    if ada_prosedur:
        for p in icd9:
            b = _baris_icd9(p)
            if b is None:
                peringatan.append(f"Kode ICD-9-CM {p!r} tidak dikenali; format yang benar mis. 36.06.")
            else:
                tambah(b[2], f"prosedur {p}: {b[3]}")
    if 5 in groups:
        tambah("Q", "rawat jalan tanpa prosedur: kelompok Q berisi kunjungan rawat jalan umum")
    if not urut or SEMUA in alasan_cmg:
        alasan_semua = alasan_cmg.get(SEMUA, "diagnosis belum diisi: semua CMG dipertimbangkan")
        for c in sorted({r["cmg"] for r in cbg.values()}):
            if c not in alasan_cmg:
                alasan_cmg[c] = alasan_semua
                urut.append(c)
    urut = [c for c in urut if c != SEMUA]

    # petunjuk Lampiran I.A
    petunjuk = {}
    for d in trigger:
        if dx and dx in d["ICD10"] or set(icd9) & d["ICD9CM"]:
            for k in d["cbg"]:
                grup = k.rsplit("-", 1)[0]
                petunjuk.setdefault(grup, set()).add(d["kode_spesial"])

    # kumpulkan grup (kode tanpa severity) yang cocok
    grup = {}
    for k, r in cbg.items():
        if int(r["case_type"]) not in groups or r["cmg"] not in alasan_cmg:
            continue
        g = k.rsplit("-", 1)[0]
        e = grup.setdefault(g, {"grup": g, "cmg": r["cmg"], "case_group": int(r["case_type"]),
                                 "deskripsi": re.sub(r"\s*\((RINGAN|SEDANG|BERAT)\)$", "", r["deskripsi"]),
                                 "kode": {}, "alasan": alasan_cmg[r["cmg"]],
                                 "lampiran_ia": sorted(petunjuk.get(g, []))})
        e["kode"][r["kode_cbg"].rsplit("-", 1)[1]] = r["kode_cbg"]
    hasil = sorted(grup.values(), key=lambda e: (not e["lampiran_ia"], urut.index(e["cmg"]), e["grup"]))
    sev = severity if jr == "RI" else "0"
    for e in hasil:
        e["kode_terpilih"] = e["kode"].get(sev) if sev else None
    total = len(hasil)
    if total > maks:
        peringatan.append(f"{total} grup cocok; ditampilkan {maks}. Isi diagnosis utama atau prosedur agar lebih sempit.")
    return {
        "case_group": [{"kode": g, "deskripsi": CASE_GROUP[g]} for g in groups],
        "cmg": [{"kode": c, "alasan": alasan_cmg[c]} for c in urut],
        "kandidat": hasil[:maks], "jumlah_kandidat": total,
        "severity": {"dipilih": sev, "definisi": SEVERITY if jr == "RI" else {"0": "Rawat jalan"}},
        "peringatan": peringatan, "disclaimer": DISCLAIMER_PENUNTUN,
    }
