# EkstrakPermenkes

Isi repo ini: ekstraksi tabel tarif dari Permenkes Nomor 3 Tahun 2023 ke Excel, dan **kalkulator tarif INA-CBG** yang dibangun dari data tersebut. Konteks domain dan aturan ada di `CLAUDE.md`.

> Hasil kalkulator adalah estimasi atau simulasi. Angka final klaim ditentukan oleh grouper resmi E-Klaim INA-CBG (Kemenkes) dan verifikasi BPJS Kesehatan.

## Kalkulator

```bash
pip install -e .            # atau jalankan dengan PYTHONPATH=src
inacbg hitung --kode I-1-40-I --provinsi "Jawa Barat" --kelas-rs B --kepemilikan swasta --kelas-rawat 1 --icd9 36.06
inacbg hitung --kode M-1-04-I --provinsi jabar --kelas-rs B --kepemilikan swasta --kelas-rawat 2 \
    --icd9 81.51 --kode-spesial "RR-04-III:Hip Implant" --naik-kelas VIP
inacbg hitung --kode A-4-10-I --rs-khusus-nasional RSCM --kelas-rawat 3 --json
inacbg cari "pacu jantung"
inacbg tebak --icd10 I21.0 --icd9 36.06 --severity I      # penuntun kode CBG (estimasi)
inacbg tebak --icd10 "serangan jantung" --icd9 "pasang ring" --severity I   # nama penyakit/tindakan juga bisa
inacbg tebak --icd10 J06.9 --rawat RJ
inacbg icd tifoid                     # cari kode ICD-10 dari nama penyakit
inacbg icd --prosedur "operasi sesar" # cari kode ICD-9-CM dari nama tindakan
inacbg provinsi
```

Fitur yang tersedia:
- **Tarif dasar CBG**: dihitung per regional, kelas RS, kepemilikan, dan kelas rawat. Untuk 5 RS khusus nasional dipakai tarif nasional. Tarif "-" di PDF ditampilkan sebagai "tidak tersedia", bukan 0.
- **Top-up Special CMG**:
  - Special procedure dan investigation (YY, II) ditambahkan otomatis bila ICD-9-CM-nya cocok dengan Lampiran I.A.
  - Special drug dan prosthesis (DD, RR) muncul sebagai kandidat, lalu ditambahkan lewat `--kode-spesial`.
  - Kriteria RS di Lampiran II ikut dicek, misalnya Contegra hanya di RS khusus jantung kelas A pemerintah, dan Hip/Knee Implant tidak boleh di kelas D.
- **Sub-akut dan kronis** (LOS lebih dari 42 hari) memakai rumus PMK 3/2023 hal. 84, hanya untuk kasus psikiatri dan kusta dengan skor WHODAS 2.0 12 sampai 60 (PMK 26/2021 hal. 20 sampai 21).
- **Selisih biaya naik kelas** dihitung sesuai Pasal 48, termasuk pengecualian peserta PBI, kelas 3, dan lainnya.
- **Aturan lain**: regional dari provinsi (38 provinsi), RS khusus yang melayani di luar kekhususannya turun satu tingkat, klinik utama memakai tarif kelas D (rawat inap 70–100%), dan hemodialisis re-use dibayar 85%.

- **Penuntun kode CBG (estimasi)** di `src/inacbg/penuntun.py`, perintah `inacbg tebak`, dan panel "Belum tahu kodenya?" di web:
  - **Case group** (digit 2) mengikuti Tabel 2 PMK 26/2021, ditentukan dari jenis rawat, kategori (umum/kebidanan/neonatal), dan ada tidaknya prosedur.
  - **CMG** (digit 1) ditebak dari bab ICD-10 diagnosis utama dan blok ICD-9-CM prosedur. Tabel pemetaannya disusun sendiri dari struktur bab ICD dan nama CMG, **bukan tabel resmi**.
  - Kombinasi diagnosis/prosedur yang tercantum di Lampiran I.A PMK 3/2023 dinaikkan ke urutan teratas sebagai petunjuk kuat.
  - **Severity** (I/II/III) dipilih pengguna, karena daftar komplikasi/komorbiditas (CC/MCC) grouper tidak dipublikasikan.
  - Keluarannya daftar grup kandidat yang memang ada di Lampiran III, bukan satu kode pasti, urut kode (bukan peringkat kemungkinan). Kode final tetap dari grouper E-Klaim.
- **Cari kode ICD dari nama** (`src/inacbg/icd.py`, `inacbg icd`): diagnosis dan tindakan bisa dicari dengan nama Indonesia/awam (tifus, DBD, usus buntu, sesar, pasang ring), istilah Inggris (typhoid, appendectomy), atau kode. Daftar ICD-10 WHO 2019 (ditambah kode 2010 yang berubah) dan ICD-9-CM v32 dibangun oleh `scripts/bangun_icd.py`; istilah Indonesia di `data/manual/istilah_icd.csv` disusun sendiri, bukan terjemahan resmi. Sumber dan lisensi di `sumber/SUMBER.md`.

Belum tersedia: tarif Non INA-CBG.

## Versi web

`web/index.html` adalah kalkulator yang sama dalam bentuk halaman HTML, dengan dua menu: **Kalkulator Tarif** dan **Cari Kode CBG** (alamat `#cari-kode`). Di menu Cari Kode CBG, diagnosis dan tindakan diketik dengan nama atau kode, lalu tombol I/II/III atau "Pakai" membuka kalkulator dengan kode dan ICD terisi. Datanya diambil dari `web/data/kalkulator.json` (dibuat `python3 scripts/bangun_data_web.py`) dan `web/data/icd.json` (dibuat `python3 scripts/bangun_icd.py`, dimuat saat menu Cari Kode CBG dibuka). Halaman ini butuh server HTTP karena datanya dimuat dengan `fetch` (contoh: `cd web && python3 -m http.server`). Logika hitungnya diuji identik dengan engine Python pada 600 kasus acak, penuntun kodenya pada 400 kasus acak (`tests/test_web_engine.py`), dan pencarian ICD-nya pada 120 kueri (`tests/test_icd.py`).

### Online (GitHub Pages)

Workflow `.github/workflows/pages.yml` men-deploy kalkulator ke `https://arfan-h.github.io/EkstrakPermenkes/` setiap kali ada push ke `main` yang mengubah `web/`. Workflow ini menjalankan `scripts/bangun_situs.py`, yang membungkus `web/index.html` menjadi dokumen HTML lengkap.

Pengaturan awal cukup dilakukan sekali: buka **Settings → Pages → Build and deployment → Source**, lalu pilih **GitHub Actions**.

## Data

| File | Isi |
|---|---|
| `Permenkes Nomor 26 Tahun 2021.pdf` | Pedoman INA-CBG dari JDIH Kemenkes (asal-usul dan SHA-256 di `sumber/SUMBER.md`) |
| `data/processed/cmg.csv`, `case_group.csv` | Tabel CMG dan Case Group resmi (PMK 26/2021 hal. 11 sampai 12), dibuat `scripts/ekstrak_pmk26.py` |
| `output/banding_special_cmg_pmk26_vs_pmk3.txt` | Perbandingan Special CMG PMK 26/2021 dengan PMK 3/2023 |
| `Permenkes_3_2023_hal40-akhir.pdf` | PDF asli, halaman 40 sampai akhir |
| `output/Tarif_INA-CBG_Permenkes_3_2023.xlsx` | Hasil ekstraksi dengan sheet `Top Up`, `Tarif INA-CBG`, dan `Gabungan` |
| `output/laporan_verifikasi_independen.txt` | Hasil cek ulang setiap sel dengan metode kedua (`scripts/verifikasi.py`): 0 beda |
| `output/laporan_validasi.txt` | Catatan baris terpotong antarhalaman dan deskripsi multi-baris |
| `data/processed/*.csv` | Tabel bersih untuk kalkulator, termasuk `special_cmg_trigger.csv` (Lampiran I.A) |

Halaman 84 (rumus) dan Lampiran II (hal. 85–91) dimasukkan ke kode di `src/inacbg/rules.py` dan `src/inacbg/kriteria.py`.

## Menjalankan ulang

```bash
python3 scripts/ekstrak_raw.py Permenkes_3_2023_hal40-akhir.pdf raw.pkl
python3 scripts/bangun_excel.py raw.pkl output/Tarif_INA-CBG_Permenkes_3_2023.xlsx output/laporan_validasi.txt
python3 scripts/verifikasi.py Permenkes_3_2023_hal40-akhir.pdf output/Tarif_INA-CBG_Permenkes_3_2023.xlsx output/laporan_verifikasi_independen.txt
PYTHONPATH=src python3 -m inacbg.etl
python3 scripts/bangun_icd.py
python3 scripts/ekstrak_lampiran_ia.py "Permenkes Nomor 3 Tahun 2023 1.pdf" data/processed/special_cmg_trigger.csv
python3 -m pytest
```
