"""Lampiran II PMK 3/2023 (hal. PDF 85-91): Kriteria pelayanan dan kompetensi
untuk pelayanan kesehatan tertentu di FKRTL.

Tabel ini pendek (11 baris), jadi ditranskrip langsung ke struktur data:
- `syarat_rs`  : fungsi yang bisa dicek otomatis dari profil RS
- `jenis_rawat`: batas jenis rawat bila ada
- `catatan`    : syarat lain yang tidak bisa dicek kalkulator (ditampilkan
                 sebagai pengingat ke pengguna)
Teks ketentuan disalin dari PDF.
"""

KHUSUS_NASIONAL_UMUM = {"RSCM"}            # RSUPN, RS umum kelas A
KHUSUS_NASIONAL_JANTUNG = {"RSJP-HK"}      # RS khusus jantung kelas A pemerintah


def _kelas_efektif(rs):
    """Kelas RS untuk keperluan kriteria; RS khusus nasional dianggap kelas A."""
    return "A" if rs["kelas_rs"] == "KHUSUS_NASIONAL" else rs["kelas_rs"]


def _bukan_kelas(*kelas):
    def cek(rs):
        return _kelas_efektif(rs) not in kelas
    return cek


def _contegra(rs):
    if rs["kelas_rs"] == "KHUSUS_NASIONAL":
        return rs["nama_rs_khusus"] in KHUSUS_NASIONAL_JANTUNG
    return rs["kelas_rs"] == "A" and rs["kepemilikan"] == "PEMERINTAH" and rs["tipe_rs"] == "khusus_jantung"


def _evar(rs):
    if rs["kelas_rs"] == "KHUSUS_NASIONAL":
        return rs["nama_rs_khusus"] in KHUSUS_NASIONAL_UMUM | KHUSUS_NASIONAL_JANTUNG
    return rs["kelas_rs"] == "A" and rs["tipe_rs"] in ("umum", "khusus_jantung")


KRITERIA = {
    "RR-02-II": {
        "layanan": "Contegra", "halaman": 85,
        "syarat_rs": _contegra,
        "syarat_rs_teks": "hanya RS Khusus Jantung Kelas A milik Pemerintah",
        "ketentuan": "Penjaminan top up hanya dilakukan di RS Khusus Jantung Kelas A Milik Pemerintah.",
        "catatan": [],
    },
    "RR-04-III": {
        "layanan": "Hip Implant/Knee Implant", "halaman": 85,
        "syarat_rs": _bukan_kelas("D"), "syarat_rs_teks": "tidak dapat di RS kelas D",
        "ketentuan": "1. Penjaminan tidak dapat dilakukan di RS kelas D; 2. Layanan dilakukan oleh "
                     "operator sesuai dengan kewenangan klinis dan kompetensinya; 3. Adanya "
                     "ketersediaan alat untuk pelaksanaan operasi Hip/Knee Implant.",
        "catatan": ["operator sesuai kewenangan klinis dan kompetensinya",
                    "alat untuk operasi Hip/Knee Implant tersedia"],
    },
    "RR-05-III": {
        "layanan": "Prostesis Evar/Tevar", "halaman": 85,
        "syarat_rs": _evar, "syarat_rs_teks": "hanya RS Kelas A Umum atau RS Khusus Jantung Kelas A",
        "ketentuan": "1. Tarif layanan yang mendapatkan top up hanya berlaku untuk: RS Kelas A Umum; "
                     "RS Khusus Jantung Kelas A. 2. Tarif layanan berlaku hanya untuk 1 kali "
                     "penjaminan untuk setiap jenis prosedur yang menggunakan prosthesis Evar/Tevar; "
                     "3. Layanan dilakukan oleh dokter sesuai dengan kewenangan klinis dan kompetensinya.",
        "catatan": ["hanya 1 kali penjaminan untuk setiap jenis prosedur dengan prosthesis Evar/Tevar",
                    "dokter sesuai kewenangan klinis dan kompetensinya"],
    },
    "YY-13-III": {
        "layanan": "Coil", "halaman": 86,
        "syarat_rs": _bukan_kelas("D"), "syarat_rs_teks": "tidak dapat di RS kelas D",
        "ketentuan": "1. Penjaminan tidak dapat dilakukan di RS kelas D; 2. Kriteria pendukung: "
                     "a. Hasil CT Scan Kepala minimal 64 Slice yang dilakukan pada saat pasien datang "
                     "ke RS; b. Pasien dirawat diruang ICU neurologi/ICU atau HCU neurologi/HCU setelah "
                     "tindakan Coiling; c. Layanan dilakukan oleh operator sesuai dengan kewenangan "
                     "klinis dan kompetensi.",
        "catatan": ["CT Scan kepala minimal 64 slice saat pasien datang",
                    "dirawat di ICU/HCU (neurologi) setelah coiling",
                    "operator sesuai kewenangan klinis dan kompetensi"],
    },
    "YY-14-III": {
        "layanan": "Trombektomi", "halaman": 87,
        "syarat_rs": _bukan_kelas("D"), "syarat_rs_teks": "tidak dapat di RS kelas D",
        "ketentuan": "1. Penjaminan tidak dapat dilakukan di RS kelas D; 2. Kriteria pendukung: "
                     "a. Hasil CT Scan Kepala minimal 64 Slice yang dilakukan pada saat pasien datang "
                     "ke RS; b. Pasien dirawat diruang ICU neurologi/ICU atau HCU neurologi/HCU setelah "
                     "tindakan Trombektomi; c. Layanan dilakukan oleh operator sesuai dengan kewenangan "
                     "klinis dan kompetensinya.",
        "catatan": ["CT Scan kepala minimal 64 slice saat pasien datang",
                    "dirawat di ICU/HCU (neurologi) setelah trombektomi",
                    "operator sesuai kewenangan klinis dan kompetensinya"],
    },
    "YY-15-III": {
        "layanan": "Percutaneous Endoscopy Gastrostomy", "halaman": 88,
        "syarat_rs": _bukan_kelas("C", "D"), "syarat_rs_teks": "tidak dapat di RS kelas C dan D",
        "jenis_rawat": "RI",
        "ketentuan": "1. Penjaminan tidak dapat dilakukan di RS kelas C dan D; 2. Tarif top up untuk "
                     "Percutaneous Endoscopy Gastrostomy hanya untuk rawat inap; 3. Standar kriteria "
                     "sarana prasarana dan kewenangan klinis RS yang berkompetensi melakukan "
                     "Percutaneous Endoscopy Gastrostomy; 4. Tindakan Percutaneous Endoscopy "
                     "Gastrostomy hanya untuk indikasi terapeutik.",
        "catatan": ["sarana prasarana dan kewenangan klinis RS memenuhi standar",
                    "hanya untuk indikasi terapeutik"],
    },
    "YY-10-III": {
        "layanan": "Phacoemulsification", "halaman": 89,
        "syarat_rs": None, "syarat_rs_teks": None,
        "ketentuan": "1. Kriteria penjaminan untuk tindakan Phacoemulsification sesuai dengan Peraturan "
                     "BPJS Kesehatan; 2. Untuk menghindari potensi moral hazard dilakukan kesepakatan "
                     "kapasitas antara BPJS Kesehatan dengan FKRTL untuk tindakan Phacoemulsification elektif.",
        "catatan": ["kriteria penjaminan sesuai Peraturan BPJS Kesehatan",
                    "tindakan elektif mengikuti kesepakatan kapasitas BPJS Kesehatan dengan FKRTL"],
    },
    "YY-16-III": {
        "layanan": "Odontektomi", "halaman": 89,
        "syarat_rs": None, "syarat_rs_teks": None, "jenis_rawat": "RJ",
        "ketentuan": "1. Tarif top up Odontektomi hanya berlaku di rawat jalan; 2. Tindakan odontektomi "
                     "dilakukan oleh dokter gigi spesialis/subspesialis sesuai dengan kewenangan klinis "
                     "dan kompetensinya; 3. Pencabutan gigi yang dilakukan odontektomi disebabkan oleh "
                     "kelainan patologis, bukan semata mata karena posisi anatomi; 4. Dalam hal "
                     "ketiadaan Sp.BM/Sp.BMMF/dokter gigi spesialis sesuai kewenangan klinisnya di "
                     "faskes maka tindakan elektif di rujuk ke faskes terdekat yang memiliki "
                     "Sp.BM/Sp.BMMF/dokter gigi spesialis sesuai kewenangan klinisnya.",
        "catatan": ["dokter gigi spesialis/subspesialis sesuai kewenangan klinis",
                    "disebabkan kelainan patologis, bukan semata posisi anatomi"],
    },
    "YY-17-III": {
        "layanan": "Brakiterapi", "halaman": 90,
        "syarat_rs": _bukan_kelas("D"), "syarat_rs_teks": "tidak dapat di RS kelas D",
        "ketentuan": "1. Penjaminan tidak dapat dilakukan di RS kelas D; 2. Pelayanan Radioterapi "
                     "diberikan sesuai dengan PNPK atau PPK yang berlaku di fasyankes dan/atau "
                     "keputusan Tumor Board sesuai dengan ketentuan perundangan yang berlaku.",
        "catatan": ["sesuai PNPK/PPK dan/atau keputusan Tumor Board"],
    },
}

# Baris Lampiran II tanpa kode special CMG (berlaku untuk tarif dasar CBG)
KRITERIA_CBG = {
    "KEMOTERAPI": {
        "kode_cbg": ["C-4-13-I", "C-4-13-II", "C-4-13-III", "C-3-23-0"], "halaman": 91,
        "catatan": ["kemoterapi sesuai PNPK/PPK, formularium nasional, dan ketentuan yang berlaku",
                    "dilakukan oleh dokter berkompetensi di bidang onkologi"],
    },
    "HEMODIALISIS": {
        "kode_cbg": ["N-3-15-0"], "halaman": 91,
        "persen_reuse": 85,
        "catatan": ["alat dan BMHP hemodialisis digunakan single use; bila re-use tarif dibayar 85%"],
    },
}
