# CLAUDE.md — Kalkulator Tarif INA-CBG

## Tujuan proyek

Membangun **kalkulator tarif INA-CBG** (sistem paket tarif klaim JKN/BPJS Kesehatan di FKRTL) berbasis Python, bersumber dari **Permenkes No. 3 Tahun 2023** (standar tarif).

Ruang lingkup yang realistis:

| Kemampuan | Status | Catatan |
|---|---|---|
| **Kode CBG → tarif** (per regional, kelas RS, kepemilikan, kelas rawat) | ✅ Akurat | Data resmi lampiran PMK 3/2023 sudah diekstrak |
| **Top-up Special CMG** (obat, prosthesis, prosedur, investigasi) | ✅ Akurat bila pemicunya diketahui | Besaran sudah ada; mapping pemicu (ICD) perlu diekstrak dari hal. 32–39 |
| **Kasus sub-akut & kronis** (LOS > 42 hari) | ✅ Rumus resmi | Hardcode dari hal. 84 |
| **Selisih biaya naik kelas** | ✅ Aturan resmi | Hardcode dari hal. 26–27 |
| **ICD-10 / ICD-9-CM → kode CBG** | ⚠️ Hanya estimasi | Logika grouper resmi tertutup (lihat "Batasan") |

> Selalu tampilkan disclaimer di output: **angka final klaim ditentukan oleh grouper resmi E-Klaim INA-CBG (Kemenkes).** Kalkulator ini estimasi/simulasi.

---

## Konteks domain (wajib dipahami sebelum coding)

### Apa itu INA-CBG
- **INA-CBG (Indonesian Case Based Groups)** = sistem pembayaran paket per episode perawatan dari BPJS Kesehatan ke rumah sakit. Bukan tarif per tindakan.
- Alur resmi: koder RS memasukkan **diagnosis (ICD-10 versi WHO 2010)** + **prosedur (ICD-9-CM versi 2010)** + data administratif (umur, jenis kelamin, LOS, cara pulang, berat lahir neonatus, kelas rawat) ke aplikasi **E-Klaim** → grouper mengeluarkan **kode CBG + tarif** → diverifikasi BPJS lewat **V-Klaim**.
- Total ada **1.075 grup** CBG: **786 rawat inap + 289 rawat jalan** (terverifikasi dari data).

### Regulasi acuan
| Regulasi | Isi | Dipakai untuk |
|---|---|---|
| **Permenkes 3/2023** | Standar tarif pelayanan JKN (tarif INA-CBG, top-up, Non INA-CBG, selisih biaya) | Sumber utama data & aturan kalkulator |
| **Permenkes 26/2021** | Pedoman INA-CBG (grouping, struktur kode, severity, kaidah koding) | Validasi struktur kode, definisi case type & severity |
| ICD-10 WHO 2010, ICD-9-CM 2010 | Standar koding | Referensi kode diagnosis/prosedur |

### Status iDRG (per November 2026)
- **iDRG (Indonesian Diagnosis Related Groups)** adalah penerus INA-CBG, masih **tahap uji coba/transisi bertahap**. **Tarif klaim JKN yang berlaku tetap INA-CBG** (PMK 3/2023 + PMK 26/2021).
- Perbedaan utama: INA-CBG kode 4 komponen alfanumerik (mis. `K-1-13-I`), 3 severity (I/II/III), tabel tarif per CBG. iDRG kode numerik 7 digit, Complexity Level 0–4, tarif = Cost Weight × National Base Rate × Adjustment.
- **Implikasi desain:** buat skema & modul yang bisa diganti engine-nya (abstraksi `TariffEngine`), supaya nanti bisa ditambah `IDRGEngine` tanpa membongkar semuanya.

---

## Batasan penting (hasil riset)

1. **Tidak ada API / library publik grouper INA-CBG** yang bisa dipakai pribadi.
2. **E-Klaim** (aplikasi resmi Kemenkes) dipasang lokal di RS (XAMPP, `localhost/eklaim/`), disetel per faskes (kode RS, kelas, regional). Web service-nya hanya untuk integrasi SIMRS di RS, datanya terenkripsi (symmetric key dari menu Setup → Integrasi → SIMRS).
3. **Tidak ditemukan grouper open source.** Daftar CC/MCC per grup dan aturan grouping lengkap ICD → CBG **tidak dipublikasikan utuh**.
4. Referensi yang ada:
   - **SIMRS-Khanza** (GitHub `mas-elkhanza/SIMRS-Khanza`, folder `webapps/inacbg`) — contoh kode *bridging* ke web service E-Klaim (memanggil grouper, menyimpan kode CBG, deskripsi, tarif). Bukan implementasi grouper.
   - **KoderMedis (kodermedis.id)** — pihak ketiga: cari ICD-10, iDRG explorer, simulasi tarif INA-CBG dari lampiran PMK 3/2023. Benchmark UI/fitur, bukan sumber logika grouper.
   - Penelitian terkait (untuk opsi ML ICD → CBG):
     - Telkom University — web + SVM untuk klasifikasi ICD dan prediksi kode & tarif INA-CBG dari data rekam medis/klaim.
     - Unsri (JSI) — prediksi kode ICD untuk klaim BPJS dengan machine learning.
     - Unilak — rekomendasi ICD-10/ICD-9 dengan NLP (sentence embeddings + cosine similarity).
     - Esa Unggul — decision tree & neural network untuk prediksi severity level (kasus hipertensi).
5. Kode referensi ICD bisa diambil dari **WHO ICD API** (icd.who.int, perlu registrasi, mendukung ICD-10) dan **ICD-9-CM dari CMS (AS)**.

---

## Sumber data

### File yang sudah ada
- `output/Tarif_INA-CBG_Permenkes_3_2023.xlsx` — hasil ekstraksi dari PDF (halaman PDF 40–83 dan 92–721), sudah diverifikasi sel per sel dengan metode independen (`scripts/verifikasi.py`, 0 beda).
- `Permenkes Nomor 3 Tahun 2023 1.pdf` — 721 halaman, teks bisa diekstrak, **kecuali hal. 31 (gambar scan, tanpa lapisan teks)**.
- `data/processed/` — tabel bersih untuk kalkulator (dibuat `python -m inacbg.etl` dan `scripts/ekstrak_lampiran_ia.py`).

### Peta halaman PDF (nomor halaman **PDF**, bukan nomor cetak)
| Halaman PDF | Isi | Status |
|---|---|---|
| 1–30 | Batang tubuh (pasal-pasal) — FKTP (kapitasi/non-kapitasi), FKRTL, regional, Non INA-CBG, selisih biaya | Aturan → **hardcode** (lihat bawah) |
| **31–39** | **Lampiran I.A — Daftar Special CMG**: kode special CMG ↔ kode group INA-CBG ↔ **ICD-10** ↔ **ICD-9-CM** pemicu top-up. Hal. 31 berupa **gambar scan** (item 1–5), ditranskrip manual | ✅ `data/processed/special_cmg_trigger.csv` (37 kombinasi, 87 pasangan kode spesial–CBG, cocok 100% dengan sheet Top Up) |
| 40–83 | Lampiran I.B — Besaran top-up Special CMG per regional & kelas RS | ✅ Sheet `Top Up` |
| 84 | Rumus tarif sub-akut & kronis | Hardcode |
| **85–91** | **Lampiran II — Kriteria pelayanan & kompetensi** (11 baris: 9 kode special CMG + kemoterapi + hemodialisis) | ✅ Ditranskrip ke `src/inacbg/kriteria.py` |
| 92–721 | Lampiran III — Besaran tarif INA-CBG | ✅ Sheet `Tarif INA-CBG` |

Catatan PDF: tabel di hal. 32–39 dan 85–91 memiliki sel ICD multi-baris (satu sel berisi daftar kode dipisah koma dan line break, mis. `A22.7, A39.1, ...`). Parser harus menggabungkan baris lanjutan sampai muncul nomor/kode special CMG baru, lalu memecah kode jadi satu baris per kode (long format). Rentang kode (mis. `A40.0-A40.9`) bila ada perlu diekspansi atau disimpan sebagai range.

### Struktur workbook `Tarif_INA-CBG_Permenkes_3_2023.xlsx`
Tiga sheet, kolom sama (13 kolom):
`halaman, judul, regional, jenis_tabel, jenis_rawat, no, kode_spesial, deskripsi_spesial_cmg, kode_ina_cbg, deskripsi_kode_ina_cbg, jenis_rs, kelas_harga, tarif`

| Sheet | Baris | Isi |
|---|---|---|
| `Tarif INA-CBG` | 119.115 | Tarif dasar CBG (hal. 92–721) |
| `Top Up` | 11.070 | Top-up special CMG (hal. 40–83) |
| `Gabungan` | 130.185 | Union dua sheet di atas |

**Hasil profiling `Tarif INA-CBG`:**
- 1.075 kode CBG unik (786 RI + 289 RJ). Setiap kode RI punya 135 baris (5 regional × 8 kelas RS × 3 kelas rawat + 5 RS khusus × 3), setiap kode RJ 45 baris.
- `jenis_rs`: `A/B/C/D` × `PEMERINTAH/SWASTA` (8 kelompok) + 5 RS khusus nasional: `RSCM`, `RSJP-HK`, `RSK DHARMAIS`, `RSAB-HK`, `RSPON`.
- `regional`: `REGIONAL 1`–`REGIONAL 5`; **kosong (NaN) untuk 5 RS khusus nasional** (13.235 baris) — wajar, tarifnya nasional.
- `kelas_harga`: `KELAS 1/2/3` untuk rawat inap; **kosong untuk rawat jalan** (13.005 baris) — wajar, RJ satu tarif.
- CMG (huruf pertama kode) yang ada: A B C D E F G H I J K L M N O P Q S T U V W Z.
- Case type (digit kedua) yang ada: 1, 2, 3, 4, 5, 6, 7, 8, 9.
- Severity: `I`, `II`, `III` (RI), `0` (RJ).
- Tidak ada duplikat pada key `(regional, jenis_rs, kode_ina_cbg, kelas_harga)`.
- Konsistensi: untuk semua baris RI, tarif kelas 1 ≥ kelas 2 ≥ kelas 3 (0 anomali).
- Rentang tarif numerik: Rp78.800 – Rp458.181.300.
- **3.980 baris tarif bernilai string `"-"`** (layanan tidak tersedia di kelas RS tsb.): D (1.180+1.180), C (720+720), B (90+90); 80 kode CBG, mayoritas rawat inap.

**Hasil profiling `Top Up`:**
- 36 kode special CMG unik, menempel ke 69 kode CBG.
- Prefix kode special: `DD` = special drug, `RR` = special prosthesis, `YY` = special procedure, `II` = special investigation. (Sub-akut & kronis tidak berupa tabel — pakai rumus hal. 84.)
- Regional 1 punya 3.198 baris (termasuk 5 RS khusus × 246), regional 2–5 masing-masing 1.968.
- `kelas_harga` tersimpan sebagai teks `"1"/"2"/"3"` (pandas membacanya jadi float `1.0` kecuali `dtype=str`; beda format dengan sheet Tarif); **540 baris kosong** = top-up untuk grup rawat jalan (mis. `Q-5-44-0`, `Z-3-17-0`, `H-2-36-0`, `J-3-15-0`, `B-3-11-0`).
- `jenis_rawat` dan `deskripsi_kode_ina_cbg` **kosong semua** → isi via join ke sheet Tarif.
- **2.543 baris `"-"`** (top-up tidak dijamin di kelas RS tsb.), terbanyak `RR-02-II` (Contegra), `RR-05-III`, `RR-01-II`, `RR-04-III`, `YY-05/07/08/15-III`.
- **Satu deskripsi bisa punya dua kode berbeda** (RI vs RJ), mis. Deferiprone = `DD-02-II` dan `DD-07-II` (yang kedua untuk `Q-5-44-0`). **Jangan dedupe berdasarkan deskripsi.**

Daftar 36 kode special CMG: DD-01-I Streptokinase; DD-02-II/DD-07-II Deferiprone; DD-03-II/DD-08-II Deferoksamin; DD-04-II/DD-09-II Deferasirox; DD-05-II Human Albumin for Septicaemia; DD-06-II/DD-10-II Anti Hemofilia Factor; DD-11-II Human Albumin for Burn; RR-01-II Subdural Grid Electrode; RR-02-II Contegra; RR-03-III TMJ Prothesis; RR-04-III Hip Implant / Knee Implant; RR-05-III Prostesis EVAR/TEVAR; YY-01-II Hip/Knee Replacement; YY-02-III PCI; YY-03-III Keratoplasty; YY-04-III Pancreatectomy; YY-05-III Repair of Septal Defect with Prosthesis; YY-06-III Stereotactic Surgery & Radiotherapy; YY-07-III Torakotomi; YY-08-III Lobektomi/Bilobektomi/Pneumonectomi; YY-09-III Vitrectomy; YY-10-III Phacoemulsification; YY-11-III Microlaringoscopy; YY-12-III Cholangiograph; YY-13-III Coil; YY-14-III Trombektomi; YY-15-III Percutaneous Endoscopy Gastrostomy; YY-16-III Odontektomi; YY-17-III Brakiterapi; II-01-III Nuclear Medicine; II-02-III MRI; II-03-III Diagnostic & Imaging Procedure of Eye.

---

## Pembersihan data (langkah normalisasi wajib)

Simpan raw apa adanya di `data/raw/`; hasil bersih di `data/processed/`.

1. `tarif == "-"` → `tarif = NULL`, tambah kolom `tersedia = False` (bukan 0!). Kolom `tarif` jadi integer nullable.
2. Samakan `kelas_harga` → integer `1/2/3`, `NULL` untuk rawat jalan (sheet Tarif: `"KELAS 3"` → 3; sheet Top Up: `1.0` → 1).
3. `regional` kosong untuk RS khusus → isi `"NASIONAL"` (atau kode 0) agar join tidak gagal.
4. Top Up: isi `deskripsi_kode_ina_cbg` & `jenis_rawat` dari sheet Tarif via `kode_ina_cbg`.
5. Pecah `jenis_rs` menjadi `kelas_rs` (`A/B/C/D/KHUSUS_NASIONAL`) + `kepemilikan` (`PEMERINTAH/SWASTA/NULL`) + `nama_rs_khusus` bila ada.
6. Parse `kode_ina_cbg` → `cmg`, `case_type`, `nomor_cbg`, `severity` (regex `^([A-Z])-(\d)-(\d{2})-(I|II|III|0)$`). Validasi semua baris lolos regex.
7. Parse `kode_spesial` → `jenis_spesial` (`DD/RR/YY/II`), `nomor`, `level`.

### Skema tabel target (cocok untuk Postgres/Supabase)
```
cbg_group(kode_cbg PK, deskripsi, cmg, case_type, nomor_cbg, severity, jenis_rawat)
tarif_cbg(kode_cbg FK, regional, kelas_rs, kepemilikan, nama_rs_khusus, kelas_rawat, tarif, tersedia, sumber_halaman)
special_cmg(kode_spesial PK, deskripsi, jenis_spesial)
tarif_topup(kode_spesial FK, kode_cbg FK, regional, kelas_rs, kepemilikan, nama_rs_khusus, kelas_rawat, tarif, tersedia, sumber_halaman)
special_cmg_trigger(kode_spesial FK, kode_cbg FK, tipe_kode ['ICD10'|'ICD9CM'], kode, sumber_halaman)   -- dari hal. 32–39
special_cmg_kriteria(kode_spesial FK, kode_cbg, kode_icd10, kode_icd9cm, ketentuan_text, rs_diizinkan, rs_dilarang)  -- dari hal. 85–91
regional_provinsi(provinsi PK, regional)
```
Selalu simpan `sumber_halaman` agar setiap angka bisa ditelusuri ke PDF.

---

## Aturan bisnis yang di-hardcode (dari batang tubuh PMK 3/2023)

### Regional per provinsi (Pasal 28 ayat 2, hal. 18–19)
- **Regional 1:** DI Yogyakarta, Jawa Barat, Jawa Tengah, Jawa Timur, DKI Jakarta.
- **Regional 2:** Nusa Tenggara Barat, Bengkulu, Sulawesi Tengah, Kalimantan Barat, Lampung, Banten, Sumatera Barat, Bali, Sumatera Utara.
- **Regional 3:** Sulawesi Tenggara, Jambi, Sulawesi Barat, Gorontalo.
- **Regional 4:** Kalimantan Selatan, Riau, Kalimantan Tengah, Kalimantan Timur, Kalimantan Utara, Kepulauan Riau, Sumatera Selatan.
- **Regional 5:** Sulawesi Selatan, Papua Barat, Papua Selatan, Papua Tengah, Papua Pegunungan, Papua, Papua Barat Daya, Aceh, Kepulauan Bangka Belitung, Sulawesi Utara, Nusa Tenggara Timur, Maluku, Maluku Utara.

### Kelompok tarif (Pasal 28 ayat 1)
5 kelompok: (a) RSUPN Dr. Cipto Mangunkusumo + RS khusus nasional (RSJP Harapan Kita, RS Kanker Dharmais, RSAB Harapan Kita, RS Pusat Otak Nasional); (b) kelas A; (c) kelas B; (d) kelas C; (e) kelas D — masing-masing pemerintah & swasta. Rawat inap: kelas 1, 2, 3.

### RS khusus (Pasal 29–30)
- Pelayanan **sesuai kekhususan** → tarif kelas RS yang ditetapkan.
- Pelayanan **di luar kekhususan** → tarif **satu tingkat lebih rendah** dari kelas RS yang ditetapkan. (Kalkulator perlu input flag `sesuai_kekhususan`.)

### Klinik utama / setara (Pasal 31)
- Rawat jalan → tarif kelompok **RS kelas D**.
- Rawat inap → **70%–100%** dari tarif INA-CBG RS kelas D (besaran sesuai kesepakatan BPJS & asosiasi) → jadikan parameter, default tampilkan rentang.

### Top-up Special CMG (Pasal 27)
Special CMG: special procedure, special drugs, special investigation, special prosthesis, subacute cases, chronic cases. Top-up diberikan **di atas** tarif CBG dasar hanya bila kriteria terpenuhi (pemicu ICD hal. 32–39 + kriteria RS hal. 85–91).

Contoh kriteria (hal. 85+):
- `RR-02-II` Contegra (I-1-03-I/II/III, ICD-9-CM 35.92) → **hanya di RS Khusus Jantung kelas A milik pemerintah**.
- `RR-04-III` Hip/Knee Implant (M-1-04-I/II/III, ICD-9-CM 81.51–81.55) → **tidak bisa di RS kelas D**, operator sesuai kewenangan, alat tersedia.

### Sub-akut & kronis (hal. 84)
```
UC (unit cost) = Rp879.103
RIW            = skor ADL / 60
Fase akut      : hari 1–42  → tarif hasil grouping (tarif CBG dasar)
Sub-akut       : LOS 43–103 → Total = Tarif akut + 0,375 × RIW_subakut × UC × LOS_subakut
Kronis         : LOS 104–180 → Total = Tarif akut + top-up sub-akut + 0,25 × RIW_kronis × UC × LOS_kronis
LOS_subakut    = LOS − max(LOS − 103, 0) − 42   (bila LOS ≤ 42 → 0)
LOS_kronis     = max(LOS − 103, 0)
```
Catatan: teks PDF untuk rumus LOS sub-akut agak ambigu ("Bila (LOS-103) hasilnya 0 atau negatif maka LOS = LOS-42"); interpretasi di atas = jumlah hari yang jatuh di rentang 43–103. Tulis unit test untuk LOS 42, 43, 103, 104, 180 dan cek ulang ke PDF hal. 84.

### Selisih biaya naik kelas (hal. 26–27)
| Kasus | Ketentuan selisih |
|---|---|
| Rawat jalan eksekutif | paling banyak **Rp400.000** per episode |
| Hak kelas 2 → kelas 1 | tarif INA-CBG kelas 1 − tarif kelas 2 |
| Hak kelas 1 → di atas kelas 1 (VIP) | paling banyak **75% × tarif INA-CBG kelas 1** |
| Hak kelas 2 → di atas kelas 1 | (tarif kelas 1 − kelas 2) + paling banyak **75% × tarif kelas 1** |

- Ketentuan naik ke atas kelas 1 **tidak berlaku** bila biaya rawat inap di FKRTL tidak melebihi tarif INA-CBG sesuai hak peserta.
- Selisih bisa dibayar **peserta, pemberi kerja, dan/atau asuransi kesehatan tambahan**; bila dibayar pemberi kerja/asuransi tambahan → sesuai kesepakatan dengan FKRTL. Relevan bila kalkulator dipakai dari sisi asuransi (koordinasi manfaat).
- Pengecualian (tidak boleh naik kelas dengan selisih): peserta PBI, PBPU kelas 3, Bukan Pekerja kelas 3, peserta yang didaftarkan Pemda, dll. — **baca ulang daftar lengkap di hal. 26–27** sebelum implementasi.

### Non INA-CBG (hal. 20–25) — fase lanjutan
Diklaim terpisah dari INA-CBG: mis. PET Scan rawat jalan **Rp10.000.000**, obat penyakit kronis di FKRTL (30 hari), alat kesehatan (protesa, kacamata, dll. dengan ketentuan periode), kantong darah, ambulans (sesuai tarif Pemda). Ekstrak tabelnya bila kalkulator perlu mencakup ini.

---

## Desain kalkulator

### Input
- `kode_cbg` (wajib di fase 1) **atau** daftar ICD-10 + ICD-9-CM (fase estimasi)
- `provinsi` (→ regional) atau `regional` langsung
- `kelas_rs` (A/B/C/D) + `kepemilikan` (pemerintah/swasta), atau `rs_khusus_nasional`
- `jenis_rawat` (RI/RJ), `kelas_rawat` (1/2/3) untuk RI
- opsional: `kode_spesial[]` atau ICD pemicu top-up, `los`, `skor_adl`, `kelas_naik` (untuk selisih), `sesuai_kekhususan`, `is_klinik_utama`

### Alur
1. Validasi format kode CBG (regex) + cek kombinasi ada di `tarif_cbg`.
2. Resolve regional dari provinsi; resolve kelompok tarif (RS khusus di luar kekhususan → turun satu tingkat; klinik utama → kelas D / 70–100%).
3. Ambil tarif dasar. Bila `tersedia = False` → kembalikan pesan "layanan tidak tersedia/dijamin di kelas RS ini", bukan 0.
4. Tentukan top-up: dari `kode_spesial` eksplisit, atau dari ICD via `special_cmg_trigger`; validasi `special_cmg_kriteria` (RS yang diizinkan). Jumlahkan.
5. Bila LOS > 42 → hitung top-up sub-akut/kronis.
6. Bila naik kelas → hitung selisih biaya (dan cek pengecualian).
7. Output terstruktur: `tarif_dasar`, `topup[]` (kode, deskripsi, nilai, sumber_halaman), `topup_subakut_kronis`, `total_klaim_inacbg`, `selisih_biaya`, `peringatan[]`, `disclaimer`.

### Fase ICD → CBG (estimasi, opsional)
- **Rule-based kasar:** diagnosis utama → CMG (berdasarkan bab ICD-10/body system), ada/tidaknya prosedur signifikan → case type, jumlah diagnosis sekunder → severity. Hanya untuk demo; beri label "ESTIMASI" yang jelas.
- **ML:** hanya bila tersedia data klaim historis berisi pasangan (ICD-10, ICD-9-CM, data administratif) → kode CBG hasil E-Klaim. Target bisa dipecah: CMG, case type, nomor CBG, severity. Waspadai leakage dan pastikan split per waktu.
- Jangan pernah mengklaim hasil ini setara grouper resmi.

---

## Mengapa top-up wajib (insight angka)

Tanpa mapping pemicu (hal. 32–39), kalkulator **underestimate** justru pada kasus termahal. Contoh dari data (RS kelas B swasta, Regional 1, RI kelas 1):
- **PCI:** tarif dasar `I-1-40-I` Rp17.127.100 + top-up `YY-02-III` Rp10.725.900 = **Rp27.853.000** (tanpa top-up kurang ±38%).
- **Hip replacement:** tarif dasar `M-1-04-I` Rp21.048.500 + `RR-04-III` Hip Implant Rp18.000.000 + `YY-01-II` Rp5.782.600 = **Rp44.831.100** (tanpa top-up hanya <½ nilai sebenarnya).

---

## Test case (golden values — verifikasi ke PDF)

| Kode | Regional | RS | Kelas | Expected |
|---|---|---|---|---|
| A-4-10-I | 1 | A Pemerintah | 3 / 2 / 1 | 3.702.300 / 4.313.200 / 4.924.100 (PDF hal. 92) |
| A-4-10-II | 1 | A Pemerintah | 3 / 2 / 1 | 6.323.900 / 7.367.300 / 8.410.800 |
| A-4-10-III | 1 | A Pemerintah | 3 / 2 / 1 | 8.526.600 / 9.933.500 / 11.340.400 |
| I-1-40-I | 1 | B Swasta | 1 | 17.127.100 (+ YY-02-III 10.725.900) |
| M-1-04-I | 1 | B Swasta | 1 | 21.048.500 (+ RR-04-III Hip 18.000.000, Knee 13.000.000; + YY-01-II 5.782.600) |
| DD-01-I @ I-4-10-I | 1 | A Pemerintah | 1 | top-up 4.850.700 |

Tambahan test:
- Semua 1.075 kode lolos regex; jumlah baris per kode RI = 135, RJ = 45.
- Tarif kelas 1 ≥ kelas 2 ≥ kelas 3.
- Kombinasi bertarif `"-"` mengembalikan `tersedia=False`, bukan 0.
- Contegra di RS selain RS Khusus Jantung kelas A pemerintah → top-up ditolak.
- Hip implant di RS kelas D → top-up ditolak.

---

## Roadmap

Status (24 Nov 2026): fase 1–4 sudah diimplementasikan di `src/inacbg/` (CLI `python -m inacbg`), test di `tests/`.


1. **Fase 1 — Data bersih + lookup CBG → tarif** (dari xlsx yang ada) + unit test golden values.
2. **Fase 2 — Ekstrak hal. 32–39** → `special_cmg_trigger` (long format: satu baris per kode ICD), lalu top-up otomatis dari ICD. **Prioritas tertinggi setelah fase 1.**
3. **Fase 3 — Ekstrak hal. 85–91** → `special_cmg_kriteria` + validasi kelayakan RS.
4. **Fase 4 — Aturan hardcode:** regional per provinsi, RS khusus, klinik utama, sub-akut/kronis, selisih naik kelas.
5. **Fase 5 — Antarmuka** (CLI / FastAPI / web sederhana) + export hasil.
6. **Fase 6 (opsional) — Estimasi ICD → CBG** (rule-based / ML) dan Non INA-CBG.
7. **Siapkan iDRG:** engine terpisah, skema tidak terkunci ke format kode INA-CBG.

---

## Konvensi kerja

- Python 3, pandas; parsing PDF dengan `pdfplumber`/`pdftotext -layout` (PDF berbasis teks, tidak perlu OCR).
- Jangan ubah file di `data/raw/`; semua transformasi reproducible lewat script (`scripts/` atau `src/etl/`).
- Setiap tabel hasil ekstraksi menyimpan `sumber_halaman` (halaman PDF).
- Nilai uang disimpan sebagai integer rupiah (tanpa desimal).
- Validasi hasil parsing terhadap PDF dengan spot-check acak, dan laporkan jumlah baris per halaman.
- Pesan/label UI dalam Bahasa Indonesia.
- Setiap output kalkulator wajib menyertakan disclaimer: estimasi; angka final mengikuti grouper E-Klaim & verifikasi BPJS.
