# EkstrakPermenkes

Ekstraksi tabel tarif dari Permenkes Nomor 3 Tahun 2023 ke Excel.

- `Permenkes_3_2023_hal40-akhir.pdf`: PDF asli yang dipotong, berisi halaman 40 sampai 721.
- `output/Tarif_INA-CBG_Permenkes_3_2023.xlsx`: hasil ekstraksi dengan sheet `Top Up`, `Tarif INA-CBG`, dan `Gabungan`.
- `output/laporan_validasi.txt`: catatan baris yang terpotong antarhalaman, deskripsi multi-baris yang digabung, dan hasil validasi.

Halaman 84 (rumus) dan 85-91 (Kriteria Pelayanan) sengaja tidak diambil.

## Menjalankan ulang

```bash
python3 scripts/ekstrak_raw.py Permenkes_3_2023_hal40-akhir.pdf raw.pkl
python3 scripts/bangun_excel.py raw.pkl output/Tarif_INA-CBG_Permenkes_3_2023.xlsx output/laporan_validasi.txt
```
