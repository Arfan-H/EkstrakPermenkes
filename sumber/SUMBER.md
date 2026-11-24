# Sumber dokumen

| File | Peraturan | Diunduh dari | Status di JDIH Kemenkes (dicek 24 Nov 2026) | SHA-256 |
|---|---|---|---|---|
| `Permenkes Nomor 3 Tahun 2023 1.pdf` | Permenkes No. 3 Tahun 2023 tentang Standar Tarif Pelayanan Kesehatan dalam Penyelenggaraan Program Jaminan Kesehatan (721 hal.) | diberikan pemilik proyek | Berlaku; mencabut Permenkes 52/2016 | 9ad3c8ce7e6de0de246c294267502712354e958e835b9030ca9234754f389ee7 |
| `Permenkes Nomor 26 Tahun 2021.pdf` | Permenkes No. 26 Tahun 2021 tentang Pedoman Indonesian Case Base Groups (INA-CBG) dalam Pelaksanaan Jaminan Kesehatan (56 hal.) | https://jdih.kemkes.go.id/storage/documents/pdfs/2021permenkes026.pdf (halaman: https://jdih.kemkes.go.id/documents/peraturan-menteri-kesehatan-nomor-26-tahun-2021), diunduh 24 Nov 2026 | Berlaku; mencabut Permenkes 76/2016 | 37a97d4a183b7aabb41a49bb6fd2b6069cd209ddeca2dbebd05e3df389efb140 |

## Daftar kode ICD (untuk pencarian nama penyakit dan tindakan)

| File | Isi | Asal | Lisensi | SHA-256 |
|---|---|---|---|---|
| `sumber/icd/icd_10_v2019.xml` | ICD-10 WHO versi 2019 (bab, blok, kategori, subkategori, judul bahasa Inggris) | paket PyPI `simple_icd_10` 2.1.1 (`simple_icd_10/data/icd_10_v2019.xml`), diunduh 24 Nov 2026 | CC0 1.0 (paket); klasifikasi milik WHO | c51a701421abfb12cdc06ec387168762eeb9839b01d8b5f458b86808814ab4f6 |
| `sumber/icd/CMS32_DESC_LONG_SG.txt` | ICD-9-CM volume 3 (prosedur) versi 32, judul panjang | CMS (cms.gov), lewat paket PyPI `icd-mappings` 0.6.2 (`icdmappings/data_files/ICD_9_CM_v32_master_descriptions/`), diunduh 24 Nov 2026 | domain publik pemerintah AS | 6e2b5ae376afecee0872bc71df89d8e1acf1ce8ea09332037fe8c5e47ad77722 |
| `data/manual/istilah_icd.csv` | 365 istilah diagnosis + 100 istilah tindakan dalam bahasa Indonesia/awam (mis. tifus, DBD, usus buntu, sesar, pasang ring) dipetakan ke kode | disusun sendiri; setiap kode dicek ada di dua daftar di atas oleh `scripts/bangun_icd.py` | - | - |

Catatan versi: E-Klaim memakai ICD-10 2010 dan ICD-9-CM 2010. Pembaruan WHO 2016 sampai 2019 mengubah beberapa kode (mis. dengue A90/A91 menjadi A97, hemoroid I84 menjadi K64, fibrilasi atrium I48 dipecah, apendisitis K35.9 menjadi K35.8). Kode 2010 yang terdampak ditambahkan di `scripts/bangun_icd.py` (`KODE_2010`) dan kode penggantinya ditandai. ICD-9-CM v32 (2014) hampir sama dengan versi 2010; perbedaannya tidak ditandai.

