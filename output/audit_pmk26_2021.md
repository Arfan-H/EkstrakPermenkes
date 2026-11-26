# Audit Permenkes 26/2021 terhadap kalkulator dan penuntun kode

Dicek 26 Nov 2026. Seluruh 56 halaman `Permenkes Nomor 26 Tahun 2021.pdf` dibaca dari lapisan teksnya (PDF dibuat dari Word, semua halaman punya teks, tidak perlu OCR). Setiap aturan dicocokkan dengan data dan kode program.

Status:
- **Sesuai**: isi PDF sama dengan data atau program.
- **Diterapkan**: aturan ditambahkan ke program karena audit ini.
- **Ambigu**: teks PDF bisa dibaca lebih dari satu cara; pilihan yang dipakai disebutkan.
- **Di luar cakupan**: aturan administrasi klaim atau koding yang tidak bisa dihitung dari input kalkulator.

## Ringkasan

| Bagian | Hasil |
|---|---|
| Tabel 1 CMG (hal. 11) | Sesuai, 29 dari 29 baris kata per kata |
| Tabel 2 Case Group (hal. 12) | Sesuai, 10 dari 10 baris |
| Definisi severity (hal. 12) | Sesuai |
| Tabel 3 contoh kode (hal. 13) | Sesuai dengan Lampiran III PMK 3/2023 |
| Tabel 4 Special CMG (hal. 14 sampai 20) | Sesuai: 32 baris, 260 kode, dicek dengan dua metode, 0 beda |
| Sub akut dan kronis (hal. 20 sampai 22) | Sesuai; satu bagian ambigu (LOS lebih dari 180 hari) |
| Contoh kode karakter ke-5 (hal. 31) | Diterapkan: 278 kode 5 karakter ditambahkan ke daftar ICD-10 |
| Dagger dan asterisk (hal. 43 sampai 44) | Diterapkan: 82 kategori asterisk ditandai, penuntun memberi peringatan |
| Kode persalinan O80 sampai O84 (hal. 39) | Diterapkan: peringatan di penuntun |
| Kode gejala R sebagai diagnosis utama rawat inap (hal. 23, 29) | Diterapkan: peringatan di penuntun |
| Aturan koding lain, episode, readmisi, fragmentasi (hal. 23 sampai 55) | Di luar cakupan, dicatat di bawah |

## Rincian per halaman

| Hal. | Isi PDF | Di program | Status |
|---|---|---|---|
| 1 sampai 5 | Batang tubuh. Pasal 3: klaim bayi baru lahir dengan kode P03.0 sampai P03.6 yang dispute di masa PMK 76/2016 dibayar menurut PMK 76/2016. Pasal 4 mencabut PMK 76/2016 | Tidak dipakai (aturan peralihan) | Di luar cakupan |
| 6 sampai 9 | Pengertian; tugas dokter, koder, verifikator. Koding memakai ICD-10 versi 2010 dan ICD-9-CM versi 2010 | Daftar ICD memakai ICD-10 WHO 2019 ditambah kode 2010 yang berubah (ditandai), dan ICD-9-CM CMS v32 (2014) | Sesuai sebagian: versi berkas sumber berbeda dari versi resmi, lihat "Batasan" |
| 10 | 1.075 grup: 786 rawat inap, 289 rawat jalan. Struktur kode 4 digit | `cbg_group.csv` berisi 1.075 kode (786 RI, 289 RJ) | Sesuai |
| 11 | Tabel 1: 29 CMG | `data/processed/cmg.csv`, termasuk salah ketik asli ("Deleiveries", "proceduress", "investigationss") | Sesuai |
| 12 | Tabel 2: case group 1 sampai 9 dan 0. Severity 0 (RJ), I tanpa komplikasi/komorbiditi, II mild, III major | `case_group.csv`, `penuntun.CASE_GROUP`, `penuntun.SEVERITY` | Sesuai |
| 13 | Tabel 3: I-4-10-I/II/III "Infark Miocard Akut", Q-5-18-0 "Konsultasi atau pemeriksaan lain-lain", Q-5-35-0 "Infeksi Akut". Ringan, sedang, berat menggambarkan severity, bukan kondisi klinis | Lampiran III: "INFARK MYOKARD AKUT", "KONSULTASI ATAU PEMERIKSAAN LAIN-LAIN", "INFEKSI AKUT" | Sesuai (beda ejaan Miocard/Myokard saja) |
| 13 sampai 14 | Enam jenis special CMG. Special investigation hanya rawat jalan, special prosthesis hanya rawat inap, special procedure dan drug keduanya | Data Lampiran I.A: II hanya ke CBG RJ, RR hanya ke CBG RI, DD dan YY ke keduanya | Sesuai |
| 14 sampai 20 | Tabel 4: 32 baris special CMG, kode CBG, ICD-10, ICD-9-CM | Parser pdfplumber (`scripts/ekstrak_pmk26.py`) dan hitungan token dari `pdftotext -layout` sama-sama mendapat 260 kode, 0 beda. Dibanding Lampiran I.A PMK 3/2023: 28 kode identik; PMK 3/2023 menambah YY-13 sampai YY-17, mengubah DD-06-II, RR-02-II (Cote Graft 35.81 menjadi Contegra 35.92), YY-08-III. Kalkulator memakai PMK 3/2023 karena lebih baru | Sesuai |
| 20 sampai 22 | Sub akut dan kronis hanya untuk psikiatri dan kusta; fase akut 1 sampai 42, sub akut 43 sampai 103, kronis 104 sampai 180 hari; lebih dari 180 hari diklaim satu episode fase kronis; berlaku di semua FKRTL dengan pelayanan psikiatri dan kusta; rumus akut, akut + sub akut, akut + sub akut + kronis; WHODAS 2.0, 12 variabel skala 1 sampai 5, maksimal 60; dinilai hari ke-43 dan ke-104; diinput di kolom ADL | `rules.py` (`los_fase`, `topup_subakut_kronis`, ADL 12 sampai 60), `engine.py` (`kasus_psikiatri_kusta`) | Sesuai. Skor minimal 12 adalah turunan (12 variabel x skor 1), tidak tertulis langsung |
| 21 dengan PMK 3/2023 hal. 84 | Lebih dari 180 hari "diklaimkan satu episode dengan fase kronis"; hal. 84 memberi LOS kronis = LOS - 103 tanpa batas atas | Program menghitung hari kronis LOS - 103 tanpa batas dan memberi peringatan | Ambigu: tidak jelas apakah hari kronis dibatasi 77 hari (sampai hari ke-180) |
| 23 sampai 24 | Diagnosis utama (sumber daya terbanyak), diagnosis sekunder (komorbiditas, komplikasi); bila tidak ada diagnosis pasti, gejala boleh jadi diagnosis utama | Penuntun hanya membaca diagnosis utama yang diisi pengguna | Di luar cakupan; peringatan kode R ditambahkan (lihat hal. 29) |
| 24 sampai 29 | Rule MB1 sampai MB5 (reseleksi diagnosis utama) | Tidak diterapkan: butuh diagnosis sekunder, spesialisasi, dan isi rekam medis | Di luar cakupan |
| 29 sampai 30 | Kode R (Bab XVIII) dan Z (Bab XXI) sebagai diagnosis utama rawat inap hanya bila tidak ada diagnosis yang lebih spesifik; Z03.- untuk suspek; D37 sampai D48 untuk neoplasma tak pasti | Penuntun memberi peringatan bila diagnosis utama rawat inap berkode R | Diterapkan (kode R). Kode Z tidak diperingatkan karena banyak kode Z sah sebagai diagnosis utama (Z51.1, Z51.0, Z09.8, Z30.2, Z53) |
| 30 sampai 31 | Kondisi multipel (HIV, cedera, fraktur multipel). Contoh memakai kode 5 karakter S72.71, S72.31, S72.41, T02.40, S42.30, S52.30 | Daftar ICD-10 WHO 2019 tidak memuat subdivisi karakter ke-5 | Diterapkan: subdivisi karakter ke-5 WHO ditambahkan untuk fraktur (S02, S12, S22, S32, S42, S52, S62, S72, S82, S92, T02, T14.2: 0 tertutup, 1 terbuka) dan cedera rongga (S06, S26, S27, S36, S37: 0 tanpa, 1 dengan luka terbuka), total 278 kode |
| 32 sampai 33 | Kategori kombinasi (I12.0, H40.4, K40.3, E10.3 + H28.0); sekuele (B90 sampai B94, E64, E68, G09, I69, O97, T90 sampai T98, Y85 sampai Y89) | Semua kode contoh ada di daftar ICD | Di luar cakupan (aturan koding) |
| 34 | Kondisi akut dan kronis | Tidak diterapkan | Di luar cakupan |
| 35 | Komplikasi pasca prosedur (T80 sampai T88, E89.0, Y83 sampai Y84) | Tidak diterapkan | Di luar cakupan |
| 36 sampai 37 | HIV memakai 4 karakter B20 sampai B23; .7 untuk penyakit multipel | Kode B20.x sampai B23.x ada di daftar | Di luar cakupan |
| 37 sampai 38 | Neoplasma; riwayat Z85.-, riwayat keluarga Z80.- | Kode ada di daftar | Di luar cakupan |
| 38 sampai 39 | Karakter ke-4 diabetes E10 sampai E14 | Kode ada di daftar | Di luar cakupan |
| 39 sampai 41 | O80 sampai O84 jadi diagnosis sekunder bila ada penyulit, jadi diagnosis utama bila tidak ada penyulit; Z37.- sekunder | Penuntun memberi peringatan bila diagnosis utama O80 sampai O84 | Diterapkan |
| 41 sampai 42 | ICD-9-CM volume 3; konvensi see, omit code, code also, exclude, includes | Semua kode contoh (36.09, 39.93, 38.91, 01.24, 54.19, 54.11, 03.09, 42.69, 43.19, 40.2, 40.11, 35.2) ada di daftar ICD-9-CM v32 | Di luar cakupan (konvensi indeks) |
| 43 | "Use additional code" jadi diagnosis sekunder bila ditatalaksana | Tidak diterapkan | Di luar cakupan |
| 43 sampai 44 | Dagger dan asterisk: kode dagger jadi diagnosis utama, asterisk jadi sekunder; simbol tidak diinput | 82 kategori asterisk ditandai (`penuntun.KATEGORI_ASTERISK`); kolom `asterisk` di `icd10.csv`; tanda * di web; peringatan penuntun bila diagnosis utama asterisk. Kode disimpan tanpa simbol | Diterapkan |
| 44 | Bayi sehat lahir dengan tindakan persalinan dibayar dalam paket ibu; bayi sakit diklaim terpisah | Tidak diterapkan | Di luar cakupan |
| 44 sampai 45 | Kontrol ulang rawat jalan: Z09.8 diagnosis utama; bayi kurang dari 7 hari: P96.8 | Z09.8 punya istilah "kontrol ulang" di pencarian | Di luar cakupan (aturan koding) |
| 45 sampai 47 | Terapi berulang rawat jalan memakai kode Z; kemoterapi oral Z51.1 tanpa kode neoplasma; kemoterapi injeksi Z51.1 + neoplasma + 99.25; radioterapi Z51.0; paliatif Z51.5 hanya bila ditulis dokter | Kode dan istilahnya ada di pencarian | Di luar cakupan (aturan koding) |
| 47 | Tubektomi interval setelah persalinan di FKTP: Z30.2 | Kode ada di daftar | Di luar cakupan |
| 48 | Talasemia mayor D56.1; kontrol dengan obat kelasi besi diinput rawat jalan dengan D56.1 diagnosis utama | Top up DD-07-II, DD-08-II, DD-09-II pada Q-5-44-0 dipicu D56.1 (Lampiran I.A) | Sesuai |
| 48 | Tindakan yang tidak selesai dikode sesuai yang dilakukan | Tidak diterapkan | Di luar cakupan |
| 48 sampai 54 | Episode rawat jalan dan rawat inap: penunjang beda hari, IGD kurang dari 6 jam = rawat jalan, IGD lebih dari 6 jam diklaim rawat inap kelas 3, rawat inap kurang dari 6 jam lalu dirujuk = rawat jalan, batal operasi (Z53.0, Z53.1 sampai Z53.9) | Kalkulator menghitung satu episode yang jenis rawat dan kelasnya sudah ditentukan pengguna | Di luar cakupan |
| 55 | Readmisi (rawat inap ulang dengan diagnosis utama sama dalam 30 hari) dan fragmentasi (rawat jalan ulang dalam 7 hari), beserta pengecualiannya | Tidak diterapkan | Di luar cakupan |
| 56 | Penutup: tarif berlaku subsidi silang antargrup | - | - |

## Batasan yang tersisa

- **Versi ICD.** PMK 26/2021 mewajibkan ICD-10 versi 2010 dan ICD-9-CM versi 2010. Berkas yang tersedia bebas adalah ICD-10 WHO 2019 dan ICD-9-CM v32 (2014).
  - Kode ICD-10 2010 yang diketahui berubah ditambahkan dan ditandai: dengue A90/A91, hemoroid I84, I48, K35.0/K35.1/K35.9, B18.1, K58.0/K58.9. Kode penggantinya di versi 2019 juga ditandai.
  - Perubahan lain antara 2010 dan 2019 belum terdeteksi.
  - Kode ICD-9-CM yang baru muncul setelah 2010 tidak ditandai.
- **Daftar asterisk.** Disusun dari daftar kategori asterisk WHO dan divalidasi dengan judul resmi; semua 82 judul berbentuk "... in diseases classified elsewhere" atau setara (M07: artropati psoriatik dan enteropatik).
- **Grouper resmi.** Aturan pengelompokan ICD ke CBG dan daftar CC/MCC tidak ada di PMK 26/2021, jadi penuntun tetap estimasi.
