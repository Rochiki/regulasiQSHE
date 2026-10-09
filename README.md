# Radar Regulasi QHSE

Aplikasi web untuk memantau regulasi Quality, Safety, Health, dan Environment yang berlaku bagi
operasional nasional (kantor pusat, cabang, kantor perwakilan, dan site project di 30 provinsi),
lalu mengunduhnya sebagai **Daftar dan Evaluasi Perundangan yang Berlaku** berformat Excel, satu lembar per kategori.

Berjalan di GitHub Pages tanpa server. Tetap bisa dibuka tanpa sinyal setelah sekali dimuat.

## Isi repositori

| Berkas | Fungsi |
|---|---|
| `index.html` | Aplikasinya. Register dasar ikut tertanam, jadi langsung berisi saat dibuka. |
| `exceljs.min.js` | Pustaka penyusun Excel (lisensi MIT), supaya unduhan tidak bergantung internet. |
| `register.json` | Register yang dibaca tombol **Perbarui daftar**. Inilah daftar bersama tim. |
| `kandidat.json` | Temuan robot pengecek yang menunggu ditelaah. |
| `ditolak.json` | Kandidat yang sudah ditolak, supaya tidak diusulkan lagi. |
| `cek_regulasi.py` | Robot pengecek sumber JDIH. |
| `sumber.json` | Daftar sumber dan provinsi yang dibaca robot. |
| `relevansi.json` | Kata kunci dan ambang skor saringan relevansi. |
| `.github/workflows/cek-regulasi.yml` | Jadwal robot: setiap hari 06.00 WIB, atau dijalankan manual. |
| `sw.js`, `manifest.json`, `icon.svg` | Mode luring dan pemasangan sebagai aplikasi. |

## Pilihan bahasa

Tombol **ID | EN | 日本語** di kanan atas mengganti bahasa aplikasi dan unduhan Excel. Pilihan diingat di perangkat itu.

- Yang diterjemahkan: seluruh antarmuka, judul regulasi (judul asli tetap ditampilkan di bawahnya), jenis regulasi, dan saran tindak lanjut baku.
- Yang tetap berbahasa Indonesia: nomor regulasi dan naskah yang dibuka dari tautan.
- Terjemahan judul bersifat tidak resmi. Kamusnya ada di `src`-nya `index.html`: `KAMUS` untuk antarmuka dan `JUDUL_TJ` untuk judul. Judul regulasi baru yang belum ada di kamus tampil dalam Bahasa Indonesia.

## Memasang di GitHub (sekali saja)

1. Buat repositori baru, misalnya `radar-regulasi`. Boleh privat bila paket GitHub mendukung Pages privat.
2. **Add file → Upload files**, seret semua berkas di folder ini (tanpa subfolder; semuanya berada di akar repositori), lalu **Commit changes**.
   Jadwal robot adalah satu-satunya berkas yang harus berada di folder khusus. Buat langsung di GitHub:
   **Add file → Create new file**, ketik nama `.github/workflows/cek-regulasi.yml`, lalu tempel isinya.
3. **Settings → Pages → Build and deployment**: Source = *Deploy from a branch*, Branch = `main`, folder `/ (root)`, **Save**.
4. **Settings → Actions → General → Workflow permissions**: pilih *Read and write permissions*, **Save**.
   Tanpa ini robot tidak bisa menyimpan hasil pengecekan.
5. Tunggu satu sampai dua menit, lalu buka `https://<nama-akun>.github.io/radar-regulasi/`.

## Pembaruan otomatis dan manual

- **Otomatis:** robot membaca sumber setiap pagi. Aplikasi menarik hasilnya sendiri setiap kali dibuka, saat kembali ke tab, dan tiap enam jam selama terbuka. Bisa dimatikan di Pengaturan.
- **Manual:** tombol **Perbarui daftar** menarik hasil yang sama kapan saja dan menampilkan rinciannya.
- **Label BARU** diberikan pada regulasi yang tahun terbitnya sama dengan tahun pengecekan. Regulasi lama yang baru ditambahkan ke daftar tidak diberi label BARU.

```
JDIH pusat & daerah ──► robot (GitHub Actions) ──► kandidat.json ──┐
                              │                                         ├─► tombol Perbarui ──► register di perangkat
                              └─► status dicabut ─► register.json ─┘
```

- **Regulasi baru** di `register.json` ditambahkan ke daftar.
- **Baris yang isinya diperbarui** ditandai BERUBAH.
- **Regulasi yang dicabut** pindah ke tab Arsip tidak berlaku. Tidak ada baris yang dihapus.
- **Baris lama** yang tidak ada di repositori tetap dipertahankan.
- **Temuan robot** tidak langsung masuk register. Temuan muncul di tab Kandidat baru untuk diterima atau ditolak,
  karena kecocokan kata kunci belum tentu berarti mengikat operasional.

Bila `register.json` tidak terjangkau (misalnya berkas dibuka langsung dari komputer), tombol memakai
paket pembaruan yang tertanam di `index.html`.

## Membagikan perubahan ke seluruh tim

Perubahan di aplikasi (menerima kandidat, menambah regulasi, mengubah baris) tersimpan di peramban perangkat itu.
Ada dua cara menjadikannya daftar bersama:

- **Tanpa token:** Pengaturan → *Unduh register.json*, lalu unggah berkas itu ke folder `` di repositori (timpa yang lama).
- **Dengan token:** Pengaturan → isi sambungan GitHub → *Simpan register ke GitHub*.
  Buat token di GitHub: **Settings → Developer settings → Fine-grained tokens**, batasi ke repositori ini saja,
  izin **Contents: Read and write** dan **Actions: Read and write**. Token hanya disimpan di peramban itu.

Dengan token, tombol *Jalankan pengecekan sumber sekarang* juga aktif. Tanpa token, robot dijalankan dari tab
**Actions → Cek regulasi → Run workflow**.

## Unduhan Excel

Nama berkas `01_Daftar_dan_Evaluasi_Peraturan_Terbaru_<Bulan>_<Tahun>.xlsx`, berbentuk daftar sederhana.
Ada empat lembar: `Q-Regulation list`, `S-Regulation list`, `H-Regulation list`, `E-Regulation list`.

Kolom tiap lembar: **No | Jenis Regulasi | Nomor Regulasi | JUDUL | TAUTAN REGULASI | Saran Tindak Lanjut**. Satu baris per regulasi; pasal tidak dicantumkan.

Kolom tautan berisi **Buka naskah resmi** (tautan langsung ke JDIH) bila alamat naskahnya sudah tercatat, atau **Cari naskah** (pencarian nomor dan judul di JDIH BPK dan peraturan.go.id) bila belum. Tautan langsung bisa ditambahkan lewat tombol *ubah* pada baris itu, kolom Tautan sumber resmi. Robot pengecek juga melengkapinya sendiri: tiap kali jalan ia mencari naskah resmi untuk 40 baris yang belum bertautan (JDIH Kemnaker untuk Permenaker/Kepmenaker, JDIH BPK untuk lainnya) dan hanya mengisi bila jenis, nomor, tahun, dan instansinya cocok.

Kode warna:

- Sel **Jenis Regulasi** berwarna menurut jenisnya (UU, PP, Perpres, Permen, Kepmen, SE, Perda, Pergub, Standar). Legenda ada di baris 3.
- Tab lembar dan pita kategori: Quality biru, Safety jingga, Health toska, Environment hijau.
- Regulasi yang terbit pada tahun pengecekan: kolom No berlabel **BARU** berwarna jingga dan barisnya krem. Baris yang diperbarui berlabel **BERUBAH**.

Baris diurutkan dari tahun regulasi terbaru ke terlama (tahun regulasi induk bila ada "jo."), lalu menurut jenis regulasi. Hanya regulasi yang berlaku yang diunduh. Yang dicabut tetap tersimpan di tab Arsip pada aplikasi. Nama perusahaan tidak dicantumkan.

## Menyetel robot pengecek

- **Terlalu banyak kandidat tidak relevan:** naikkan `min_skor` atau tambah kata pada `tolak` di `relevansi.json`.
- **Ada regulasi relevan yang terlewat:** tambah kata kunci beserta bobotnya pada kategori yang sesuai.
- **Menambah sumber:** tambah entri di `sumber.json`. Adapter `generik` membaca tautan apa pun yang teksnya
  berpola "Peraturan ... Nomor ... Tahun ...".
- **Sumber gagal dibaca:** lihat `sumber_gagal` di `kandidat.json` atau log pada tab Actions.
  Beberapa situs pemerintah menolak akses dari server luar negeri; sumber seperti itu perlu dicek manual.
- Peraturan daerah dicek bergilir, enam provinsi tiap hari, sehingga 30 provinsi selesai dalam lima hari.

Uji robot tanpa internet: `python cek_regulasi.py --uji`

## Batasan

- Aplikasi ini alat bantu penelusuran, bukan pendapat hukum. Status akhir dikonfirmasi ke JDIH instansi penerbit.
- Hanya peraturan yang sudah terbit dan ada naskah resminya yang masuk daftar. Yang belum pasti ditaruh di tab Kandidat baru; rancangan dicatat di kolom Saran Tindak Lanjut pada regulasi yang akan digantikannya.
- Peraturan daerah baru tercatat untuk sebagian provinsi. Tab Cakupan wilayah menunjukkan provinsi yang masih kosong.
- Pasal untuk peraturan daerah yang baru masuk masih berupa ringkasan dan perlu dirinci dari naskah resminya.

## Menampilkan di Google Sites

1. Pastikan GitHub Pages aktif (Settings → Pages → Deploy from a branch → `main` / root).
2. Di Google Sites buka halaman tujuan, pilih **Sisipkan → Sematkan → Menurut URL**, lalu tempel alamat Pages,
   misalnya `https://namaakun.github.io/radar-regulasi/`.
3. Tarik kotak sematan selebar halaman dan setinggi 900 px atau lebih, lalu **Publikasikan**.

Google Sites hanya menjadi bingkai. Isi, robot pengecek, dan pembaruan tetap berjalan dari repositori ini.

## Kandidat masuk otomatis

Temuan robot di `kandidat.json` yang nomor dan judulnya jelas langsung masuk ke daftar saat aplikasi dibuka,
tanpa perlu disetujui satu per satu. Temuan yang masih bertanda "perlu dicek" tetap menunggu di tab Kandidat baru.
Untuk membuang temuan yang tidak terkait, catat `kid`-nya di `ditolak.json` atau tambahkan kata kuncinya
ke daftar `tolak` di `relevansi.json`.
