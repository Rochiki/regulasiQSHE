#!/usr/bin/env python3
"""Robot pengecek regulasi — Radar Regulasi QHSE.

Dijalankan GitHub Actions (terjadwal tiap Senin atau manual). Tugasnya:
  1. membaca daftar terbaru di JDIH (scripts/sumber.json),
  2. menyaring yang terkait operasional (scripts/relevansi.json),
  3. menulis temuan ke kandidat.json untuk ditelaah di aplikasi,
  4. mengecek ulang status baris register yang punya tautan sumber resmi; bila sumber
     menyatakan Tidak Berlaku/Dicabut, status di register.json diubah (baris TIDAK dihapus —
     aplikasi memindahkannya ke arsip).

Uji tanpa internet:  python cek_regulasi.py --uji
"""
import json, re, sys, time, datetime, pathlib, urllib.parse

# Semua berkas (register.json, kandidat.json, sumber.json, dst.) berada satu folder dengan skrip ini,
# yaitu di akar repositori. Bila kelak dipindah ke folder data/ dan scripts/, baris di bawah menyesuaikan sendiri.
SINI = pathlib.Path(__file__).resolve().parent
AKAR = SINI.parent if SINI.name == "scripts" else SINI
DATA = AKAR / "data" if (AKAR / "data" / "register.json").exists() else AKAR
SKRIP = SINI
WIB = datetime.timezone(datetime.timedelta(hours=7))
HARI_INI = datetime.datetime.now(WIB).date().isoformat()
BULAN = {b: i + 1 for i, b in enumerate("januari februari maret april mei juni juli agustus september oktober november desember".split())}

JENIS = [  # (pola pada nama panjang, singkatan baku)
    (r"undang-undang", "UU"), (r"peraturan pemerintah", "PP"), (r"peraturan presiden", "Perpres"), (r"keputusan presiden", "Keppres"),
    (r"peraturan menteri ketenagakerjaan|peraturan menteri tenaga kerja", "Permenaker"), (r"keputusan menteri ketenagakerjaan|keputusan menteri tenaga kerja", "Kepmenaker"),
    (r"peraturan menteri lingkungan hidup", "Permen LH"), (r"keputusan menteri lingkungan hidup", "Kepmen LH"),
    (r"peraturan menteri energi", "Permen ESDM"), (r"keputusan menteri energi", "Kepmen ESDM"), (r"peraturan menteri kesehatan", "Permenkes"),
    (r"keputusan menteri kesehatan", "Kepmenkes"), (r"peraturan menteri perhubungan", "Permenhub"), (r"peraturan menteri pekerjaan umum", "Permen PU"),
    (r"peraturan menteri perindustrian", "Permenperin"), (r"peraturan menteri perdagangan", "Permendag"), (r"peraturan menteri", "Permen"),
    (r"keputusan menteri", "Kepmen"), (r"surat edaran", "SE"), (r"peraturan daerah|perda", "Perda"), (r"peraturan gubernur|pergub", "Pergub"),
    (r"keputusan gubernur", "Kepgub"), (r"instruksi gubernur", "Instruksi Gubernur"), (r"keputusan direktur jenderal|keputusan dirjen", "Kepdirjen"),
]
POLA = re.compile(
    r"(Undang-Undang|Peraturan Pemerintah|Peraturan Presiden|Keputusan Presiden|Peraturan Menteri[\w /.&-]*?|Keputusan Menteri[\w /.&-]*?|"
    r"Surat Edaran[\w /.&-]*?|Peraturan Daerah[\w .()-]*?|PERDA[\w .()-]*?|Peraturan Gubernur[\w .()-]*?|Keputusan Gubernur[\w .()-]*?|"
    r"Instruksi Gubernur[\w .()-]*?|Keputusan Direktur Jenderal[\w /.&-]*?|Keputusan Dirjen[\w /.&-]*?)"
    r"\s+(?:Nomor|No\.?)\s*([A-Za-z0-9./-]+)\s+Tahun\s+(\d{4})(?:\s+tentang\s+(.+))?", re.I | re.S)


def muat(p, bawaan):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return bawaan


def simpan(p, isi):
    pathlib.Path(p).write_text(json.dumps(isi, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def norm(s):
    s = re.sub(r"nomor|no\.|tahun|th\b", "", str(s or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)


KELAS = [(r"undang-undang|\buu\b", "uu"), (r"peraturan pemerintah|\bpp\b", "pp"), (r"peraturan presiden|perpres|per pres", "perpres"), (r"keputusan presiden|keppres", "keppres"),
         (r"peraturan daerah|perda|qanun", "perda"), (r"peraturan gubernur|pergub|per gub", "pergub"), (r"keputusan gubernur|kepgub", "kepgub"), (r"surat edaran|\bse\b", "se"),
         (r"keputusan dir|kepdir", "kepdirjen"), (r"keputusan menteri|kepmen|kep\.?\s*men", "kepmen"), (r"peraturan menteri|permen|per\.?\s*men", "permen")]
INST = [(r"naker|tenaga ?kerja", "naker"), (r"lhk|lingkungan|\blh\b|bplh", "lh"), (r"esdm|energi", "esdm"), (r"kes\b|menteri kesehatan|menkes", "kes"), (r"hub\b|perhubungan", "hub"),
        (r"pupr|\bpu\b|pekerjaan umum", "pu"), (r"perin\b|perindustrian", "perin"), (r"dag\b|perdagangan", "dag"), (r"tan\b|pertanian", "tan")]
DAERAH = ["aceh", "sumatera utara", "sumatera barat", "riau", "jambi", "sumatera selatan", "bangka belitung", "lampung", "banten", "dki", "jakarta", "jawa barat", "jawa tengah",
          "jawa timur", "kalimantan barat", "kalimantan tengah", "kalimantan selatan", "kalimantan timur", "kalimantan utara", "sulawesi utara", "gorontalo", "sulawesi tengah",
          "sulawesi selatan", "sulawesi tenggara", "nusa tenggara barat", "nusa tenggara timur", "maluku utara", "maluku", "papua selatan", "papua barat daya", "papua"]


def kelas_inst(teks):
    """('permen', 'naker') dsb. Instansi kosong berarti tidak dikenali (dianggap cocok dengan instansi apa pun)."""
    t = str(teks).lower()
    kelas = next((k for p, k in KELAS if re.search(p, t)), "lain")
    if kelas in ("perda", "pergub", "kepgub"):
        inst = next((d.replace("jakarta", "dki") for d in DAERAH if d in t), "")
    else:
        inst = next((k for p, k in INST if re.search(p, t)), "")
    return kelas, inst


def sudah_ada(punya, kelas, inst, nomor, tahun):
    k = f"{str(nomor).lstrip('0').lower()}|{tahun}"
    return any(k in punya.get((kelas, i), ()) for i in ({inst, ""} if inst else {i2 for (k2, i2) in punya if k2 == kelas}))


def kunci_register(baris):
    """Ambil semua pasangan nomor/tahun dari kolom Nomor Regulasi register (format bebas)."""
    hasil = set()
    teks = f"{baris.get('hier', '')} {baris.get('nomor', '')}"
    for no, th in re.findall(r"(\d+[A-Za-z]?)\s*(?:/|\s+tahun\s+|\s+th\.?\s+)\s*(\d{4})", teks, re.I):
        hasil.add(f"{no.lstrip('0').lower()}|{th}")
    return hasil


def singkat_jenis(nama):
    n = nama.lower()
    for pola, s in JENIS:
        if re.search(pola, n):
            return s
    return nama.strip().title()[:30]


def tanggal_iso(teks):
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", teks or "")
    if not m or m.group(2).lower() not in BULAN:
        return ""
    return f"{m.group(3)}-{BULAN[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def nilai(judul, aturan):
    """Skor relevansi -> (skor, kategori, kata yang cocok, alasan tolak)."""
    t = " " + re.sub(r"\s+", " ", judul.lower()) + " "
    for kata in aturan["tolak"]:
        if kata in t:
            return 0, "", [], kata
    terbaik = (0, "", [])
    for kat, kamus in aturan["kategori"].items():
        cocok = [k for k in kamus if k in t]
        skor = sum(kamus[k] for k in cocok)
        if skor > terbaik[0]:
            terbaik = (skor, kat, cocok)
    return terbaik[0], terbaik[1], terbaik[2], ""


# ---------------------------------------------------------------- pembaca halaman
def ambil(url, sesi):
    for coba in range(3):
        try:
            r = sesi.get(url, timeout=40)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text
            galat = f"HTTP {r.status_code}"
        except Exception as e:  # jaringan, TLS, batas waktu
            galat = type(e).__name__
        time.sleep(2 + coba * 3)
    raise RuntimeError(galat)


def blok_teks(a, minimal=25):
    """Naik dari tautan ke pembungkus terdekat yang memuat keterangan tambahan."""
    simpul, dasar = a, a.get_text(" ", strip=True)
    for _ in range(5):
        if simpul.parent is None:
            break
        simpul = simpul.parent
        t = simpul.get_text("\n", strip=True)
        if len(t) > len(dasar) + minimal:
            return t if len(t) < 1500 else dasar
    return dasar


def baca_kemnaker(html, url):
    from bs4 import BeautifulSoup
    sup, hasil = BeautifulSoup(html, "html.parser"), []
    for a in sup.select('a[href*="/peraturan/detail/"]'):
        nama = a.get_text(" ", strip=True)
        m = POLA.search(nama)
        if not m:
            continue
        baris = [b.strip() for b in blok_teks(a).split("\n") if b.strip()]
        lain = [b for b in baris if b != nama and not re.match(r"(Ditetapkan|Diundangkan|Diunduh)\b", b) and b not in ("Berlaku", "Tidak Berlaku") and not re.fullmatch(r"[A-Z0-9 ,&/().-]+( - [A-Z0-9 ,&/().-]+)+", b)]
        judul = max(lain, key=len) if lain else ""
        tgl = next((tanggal_iso(b) for b in baris if b.startswith("Ditetapkan")), "")
        hasil.append(dict(jenis=m.group(1).strip(), nomor=m.group(2), tahun=m.group(3), judul=judul, tgl=tgl,
                          status="Dicabut / Tidak Berlaku" if "Tidak Berlaku" in baris else "Berlaku", src=urllib.parse.urljoin(url, a["href"])))
    return hasil


def baca_generik(html, url, pola_href=None):
    from bs4 import BeautifulSoup
    sup, hasil, lihat = BeautifulSoup(html, "html.parser"), [], set()
    for a in sup.find_all("a", href=True):
        if pola_href and not re.search(pola_href, a["href"]):
            continue
        teks = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        m = POLA.search(teks)
        blok = ""
        if not m or not m.group(4):
            blok = re.sub(r"[ \t]+", " ", blok_teks(a))
            m2 = POLA.search(blok.replace("\n", " tentang ", 1) if m and "tentang" not in blok.lower() else blok)
            m = m2 or m
        if not m:
            continue
        judul = (m.group(4) or "").strip()
        if not judul and blok:
            sisa = [b.strip() for b in blok.split("\n") if b.strip() and not POLA.search(b)]
            judul = max(sisa, key=len) if sisa else ""
        judul = re.split(r"\s{2,}|\n", judul)[0][:300]
        k = (m.group(2), m.group(3), m.group(1).lower()[:12])
        if k in lihat:
            continue
        lihat.add(k)
        hasil.append(dict(jenis=m.group(1).strip(), nomor=m.group(2), tahun=m.group(3), judul=judul, tgl=tanggal_iso(blok),
                          status="Dicabut / Tidak Berlaku" if re.search(r"Tidak Berlaku|Dicabut dengan", blok) else "Berlaku", src=urllib.parse.urljoin(url, a["href"])))
    return hasil


def status_dari_halaman(html):
    """Baca status pada halaman detail resmi. Kembalikan (status, bukti) atau (None, '')."""
    from bs4 import BeautifulSoup
    t = re.sub(r"[ \t]+", " ", BeautifulSoup(html, "html.parser").get_text("\n", strip=True))
    m = re.search(r"Dicabut dengan\s*:?\s*\n?(.{5,160})", t)
    if m:
        return "Dicabut / Tidak Berlaku", "Dicabut dengan " + m.group(1).split("\n")[0].strip()
    if re.search(r"Status\s*\|?\s*:?\s*\n?\s*Tidak Berlaku", t):
        return "Dicabut / Tidak Berlaku", "Status pada sumber: Tidak Berlaku"
    if re.search(r"Status\s*\|?\s*:?\s*\n?\s*Berlaku", t):
        return "Berlaku", "Status pada sumber: Berlaku"
    return None, ""


# ---------------------------------------------------------------- pelengkap tautan naskah resmi
def nomor_tahun_pertama(baris):
    m = re.search(r"(\d+[A-Za-z]?)\s*(?:/|\s+tahun\s+|\s+th\.?\s+)\s*(\d{4})", f"{baris.get('nomor', '')}", re.I)
    return (m.group(1).lstrip("0").lower(), m.group(2)) if m else (None, None)


def pilih_tautan(temuan, kelas, inst, no, th):
    """Ambil tautan hanya bila jenis, instansi/provinsi, nomor, dan tahun semuanya cocok."""
    for x in temuan:
        k, i = kelas_inst(x["jenis"])
        if x["nomor"].lstrip("0").lower() == no and x["tahun"] == th and k == kelas and (not inst or not i or i == inst):
            return x["src"]
    return ""


def cari_tautan(baris, sesi):
    """Cari halaman naskah resmi untuk satu baris register. Kembalikan URL atau ''."""
    kelas, inst = kelas_inst(baris.get("nomor", "") + " " + baris.get("hier", ""))
    no, th = nomor_tahun_pertama(baris)
    if not no or kelas in ("lain", "se"):
        return ""
    if inst == "naker" and kelas in ("permen", "kepmen"):
        url = f"https://jdih.kemnaker.go.id/peraturan?keyword=&nomor={no}&tahun={th}&status=&terjemahan=&per_page=15&sort=terbaru"
        return pilih_tautan(baca_kemnaker(ambil(url, sesi), url), kelas, inst, no, th)
    kata = urllib.parse.quote_plus(" ".join(str(baris.get("judul", "")).split()[:5]))
    url = f"https://peraturan.bpk.go.id/Search?keywords={kata}&tentang=&nomor={no}&tahun={th}"
    return pilih_tautan(baca_generik(ambil(url, sesi), url, r"/Details/\d+"), kelas, inst, no, th)


# ---------------------------------------------------------------- alur utama
def susun_kandidat(temuan, sumber, wil, aturan, tahun_min, punya, tolak_kid, ada_kid):
    usul, saring = [], []
    for x in temuan:
        if int(x["tahun"]) < tahun_min:
            continue
        s = singkat_jenis(x["jenis"])
        daerah = re.search(r"(?:Provinsi|Kabupaten|Kota)\s+[A-Z][\w ]+", x["jenis"])
        nomor = f"{s} {daerah.group(0).strip() + ' ' if daerah else ''}{x['nomor']}/{x['tahun']}"
        kid = f"{sumber['id']}-{norm(nomor)}"
        if sudah_ada(punya, *kelas_inst(x["jenis"]), x["nomor"], x["tahun"]) or kid in tolak_kid or kid in ada_kid:
            continue
        skor, kat, kata, alasan_tolak = nilai(f"{x['jenis']} {x['judul']}", aturan)
        if alasan_tolak or skor < aturan["min_skor"]:
            saring.append(dict(nomor=nomor, judul=x["judul"], alasan=f"memuat '{alasan_tolak}'" if alasan_tolak else f"skor relevansi {skor} di bawah ambang"))
            continue
        usul.append(dict(kid=kid, hier=s, nomor=nomor, judul=x["judul"], tgl=x["tgl"], status=x["status"], wil=wil, kat=kat, skor=skor,
                         alasan="Kata kunci: " + ", ".join(kata) + ". Telaah apakah mengikat operasional sebelum diterima.", src=x["src"], sumber=sumber["nama"], ditemukan=HARI_INI))
        ada_kid.add(kid)
    return usul, saring


def jalankan():
    import requests
    cfg, aturan = muat(SKRIP / "sumber.json", {}), muat(SKRIP / "relevansi.json", {})
    reg = muat(DATA / "register.json", {"versi": HARI_INI, "baris": []})
    lama = muat(DATA / "kandidat.json", {})
    tolak_kid = {d["kid"] for d in muat(DATA / "ditolak.json", {}).get("ditolak", [])}
    punya = {}
    for b in reg["baris"]:
        punya.setdefault(kelas_inst(b.get("nomor", "") + " " + b.get("hier", "")), set()).update(kunci_register(b))
    sesi = requests.Session()
    sesi.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) RadarRegulasiQHSE/1.0 (pengecekan berkala register kepatuhan)", "Accept-Language": "id,en;q=0.8"})
    tahun_ini = int(HARI_INI[:4])
    tahun_min, jeda = tahun_ini - int(aturan.get("tahun_mundur", 1)), float(cfg.get("jeda_detik", 1.5))
    semua_prov = cfg.get("provinsi", [])
    n = int(cfg.get("provinsi_per_jalan", 6))
    geser = (datetime.date.fromisoformat(HARI_INI).toordinal() * n) % max(1, len(semua_prov))
    prov_kini = (semua_prov + semua_prov)[geser:geser + n]
    ada_kid = {k["kid"] for k in lama.get("kandidat", []) if k["kid"] not in tolak_kid}
    kandidat = [k for k in lama.get("kandidat", []) if k["kid"] not in tolak_kid]
    disaring, ok, gagal = [], [], []
    for s in cfg.get("sumber", []):
        if not s.get("aktif", True):
            continue
        daftar = []
        for pola in s["url"]:
            for th in ({tahun_ini, tahun_min} if "{tahun}" in pola else {""}):
                for kata in (s.get("kata") or [""]):
                    for pv in (prov_kini if s.get("per_provinsi") else [""]):
                        daftar.append((pola.replace("{tahun}", str(th)).replace("{kata}", urllib.parse.quote_plus(kata)).replace("{provinsi}", urllib.parse.quote_plus(pv)), pv or s.get("wil", "Nasional")))
        berhasil = 0
        for url, wil in daftar:
            try:
                html = ambil(url, sesi)
                temuan = baca_kemnaker(html, url) if s["adapter"] == "kemnaker" else baca_generik(html, url, s.get("pola_href"))
                u, d = susun_kandidat(temuan, s, wil, aturan, tahun_min, punya, tolak_kid, ada_kid)
                kandidat += u
                disaring += d
                berhasil += 1
            except Exception as e:
                gagal.append(dict(id=s["id"], url=url, galat=str(e)))
            time.sleep(jeda)
        if berhasil:
            ok.append(f"{s['nama']} ({berhasil}/{len(daftar)} halaman)")
    # cek ulang status baris yang punya tautan sumber resmi
    berubah, bisa = [], [b for b in reg["baris"] if re.search(r"jdih\.kemnaker\.go\.id/peraturan/detail/|peraturan\.bpk\.go\.id/(Home/)?Details/", b.get("src", "")) and b["status"] not in ("Dicabut / Tidak Berlaku", "Kedaluwarsa")]
    bisa.sort(key=lambda b: b.get("cek", ""))
    for b in bisa[: int(cfg.get("cek_status_per_jalan", 60))]:
        try:
            st, bukti = status_dari_halaman(ambil(b["src"], sesi))
            if st == "Dicabut / Tidak Berlaku":
                berubah.append(dict(id=b["id"], nomor=b["nomor"], dari=b["status"], ke=st, bukti=bukti, src=b["src"]))
                b["status"] = st
                b["cat"] = f"{bukti} (sumber resmi, dicek {HARI_INI[8:]}-{HARI_INI[5:7]}-{HARI_INI[:4]}). Ganti rujukan di prosedur/IK."
            if st:
                b["cek"] = HARI_INI
        except Exception as e:
            gagal.append(dict(id="cek-status", url=b["src"], galat=str(e)))
        time.sleep(jeda)
    # lengkapi tautan naskah resmi untuk baris yang belum punya (bertahap tiap kali jalan)
    terisi, tanpa = 0, [b for b in reg["baris"] if not b.get("src") and b["status"] not in ("Dicabut / Tidak Berlaku", "Kedaluwarsa")]
    tanpa.sort(key=lambda b: b.get("tautan_dicoba", ""))
    sudah = {}
    for b in tanpa[: int(cfg.get("tautan_per_jalan", 40))]:
        kunci_b = norm(b.get("nomor", ""))
        try:
            if kunci_b not in sudah:
                sudah[kunci_b] = cari_tautan(b, sesi)
                time.sleep(jeda)
            if sudah[kunci_b]:
                b["src"] = sudah[kunci_b]
                terisi += 1
        except Exception as e:
            gagal.append(dict(id="tautan", url=b.get("nomor", ""), galat=str(e)))
        b["tautan_dicoba"] = HARI_INI
    for b in reg["baris"]:   # baris lain dari regulasi yang sama ikut terisi
        if not b.get("src") and sudah.get(norm(b.get("nomor", ""))):
            b["src"] = sudah[norm(b.get("nomor", ""))]
    print(f"Tautan naskah resmi terisi: {terisi}; masih tanpa tautan: {sum(1 for b in reg['baris'] if not b.get('src'))}.")
    if terisi or tanpa or berubah or any(b.get("cek") == HARI_INI for b in bisa):
        reg["versi"] = HARI_INI
        simpan(DATA / "register.json", reg)
    simpan(DATA / "kandidat.json", dict(diperbarui=HARI_INI, sumber_ok=ok, sumber_gagal=gagal[:80], provinsi_dicek=prov_kini, kandidat=kandidat[:200], perubahan_status=berubah, disaring=disaring[:60]))
    print(f"Selesai {HARI_INI}: {len(kandidat)} kandidat, {len(berubah)} perubahan status, {len(ok)} sumber terbaca, {len(gagal)} halaman gagal.")
    for g in gagal[:15]:
        print("  gagal:", g["id"], g["galat"], g["url"][:90])


CONTOH_KEMNAKER = """<div class="card"><div class="card-body"><span>SKKNI - INDUSTRI - ALAT BERAT</span>
<h5><a href="https://jdih.kemnaker.go.id/peraturan/detail/3072/keputusan-menteri-ketenagakerjaan-nomor-199-tahun-2026">Keputusan Menteri Ketenagakerjaan Nomor 199 Tahun 2026</a></h5>
<span class="badge">Berlaku</span><p>Penetapan Standar Kompetensi Kerja Nasional Indonesia Kategori Industri Golongan Pokok Industri Mesin dan Perlengkapan Bidang Industri Alat Berat</p>
<small>Ditetapkan: 14 Juli 2026</small><small>Diundangkan: -</small><small>Diunduh: 222 kali</small></div></div>
<div class="card"><div class="card-body"><span>ORGANISASI - TATA KERJA</span>
<h5><a href="/peraturan/detail/3099/peraturan-menteri-ketenagakerjaan-nomor-14-tahun-2026">Peraturan Menteri Ketenagakerjaan Nomor 14 Tahun 2026</a></h5>
<span class="badge">Berlaku</span><p>Organisasi dan Tata Kerja Kementerian Ketenagakerjaan</p><small>Ditetapkan: 24 September 2026</small></div></div>
<div class="card"><div class="card-body"><h5><a href="/peraturan/detail/3070/x">Peraturan Menteri Ketenagakerjaan Nomor 11 Tahun 2026</a></h5>
<span class="badge">Berlaku</span><p>Tata Cara Pengawasan Ketenagakerjaan</p><small>Ditetapkan: 29 Juni 2026</small></div></div>"""
CONTOH_GENERIK = """<ul><li><a href="/Details/999001/perda-prov-x-no-3-tahun-2026">Peraturan Daerah (PERDA) Provinsi Kalimantan Barat Nomor 3 Tahun 2026 tentang Pengelolaan Limbah Bahan Berbahaya dan Beracun</a></li>
<li><div><a href="/Details/999002/pergub">Peraturan Gubernur Riau Nomor 12 Tahun 2026</a><p>Pajak Daerah dan Retribusi Daerah</p></div></li>
<li><a href="/tentang">Tentang kami</a></li></ul>"""


def uji():
    aturan = muat(SKRIP / "relevansi.json", {})
    a = baca_kemnaker(CONTOH_KEMNAKER, "https://jdih.kemnaker.go.id/peraturan")
    assert len(a) == 3 and a[0]["nomor"] == "199" and a[0]["tgl"] == "2026-07-14" and "Alat Berat" in a[0]["judul"], a
    b = baca_generik(CONTOH_GENERIK, "https://peraturan.bpk.go.id/Search", r"/Details/\d+")
    assert len(b) == 2 and b[0]["nomor"] == "3" and "Limbah" in b[0]["judul"] and b[1]["judul"].startswith("Pajak"), b
    reg = muat(DATA / "register.json", {"baris": []})
    punya = {}
    for r in reg["baris"]:
        punya.setdefault(kelas_inst(r.get("nomor", "") + " " + r.get("hier", "")), set()).update(kunci_register(r))
    assert sudah_ada(punya, "permen", "naker", "11", "2026") and sudah_ada(punya, "permen", "lh", "6", "2026") and sudah_ada(punya, "pp", "", "28", "2025")
    assert not sudah_ada(punya, "permen", "lh", "11", "2026"), "Permen LH 11/2026 tidak boleh dianggap sama dengan Permenaker 11/2026"
    assert sudah_ada(punya, "perda", "sumatera selatan", "8", "2016") and not sudah_ada(punya, "perda", "riau", "8", "2016")
    punya_kosong = {}
    u, d = susun_kandidat(a, dict(id="kemnaker", nama="JDIH Kemnaker"), "Nasional", aturan, 2025, {("permen", "naker"): {"11|2026"}}, set(), set())
    assert [x["nomor"] for x in u] == ["Kepmenaker 199/2026"], (u, d)          # 14/2026 ditolak (tata kerja), 11/2026 sudah ada di register
    assert not susun_kandidat(a, dict(id="kemnaker", nama="JDIH Kemnaker"), "Nasional", aturan, 2025, punya, set(), set())[0], "199/2026 & 11/2026 sudah ada di register"
    assert d and "tata kerja" in d[0]["alasan"], d
    u2, d2 = susun_kandidat(b, dict(id="bpk-daerah", nama="JDIH BPK"), "Kalimantan Barat", aturan, 2025, {}, set(), set())
    assert len(u2) == 1 and u2[0]["kat"] == "Environment" and "Provinsi Kalimantan Barat" in u2[0]["nomor"] and len(d2) == 1, (u2, d2)
    assert status_dari_halaman("<table><tr><td>Status</td><td>Tidak Berlaku</td></tr></table>")[0] == "Dicabut / Tidak Berlaku"
    assert status_dari_halaman("<div>Dicabut dengan :</div><div>Permenaker No. 11 Tahun 2026</div>")[0] == "Dicabut / Tidak Berlaku"
    assert status_dari_halaman("<p>Status</p><p>Berlaku</p>")[0] == "Berlaku"
    hasil_cari = baca_kemnaker(CONTOH_KEMNAKER, "https://jdih.kemnaker.go.id/peraturan")
    assert pilih_tautan(hasil_cari, "permen", "naker", "11", "2026").endswith("/peraturan/detail/3070/x")
    assert pilih_tautan(hasil_cari, "kepmen", "naker", "199", "2026").endswith("nomor-199-tahun-2026")
    assert pilih_tautan(hasil_cari, "permen", "lh", "11", "2026") == "" and pilih_tautan(hasil_cari, "permen", "naker", "12", "2026") == ""
    assert pilih_tautan(b, "perda", "kalimantan barat", "3", "2026").endswith("/Details/999001/perda-prov-x-no-3-tahun-2026") and pilih_tautan(b, "perda", "riau", "3", "2026") == ""
    assert nomor_tahun_pertama(dict(nomor="UU 13/2003 jo. UU 6/2023")) == ("13", "2003") and nomor_tahun_pertama(dict(nomor="Permenaker No. 05 Tahun 2018")) == ("5", "2018")
    print("UJI LULUS:", u[0]["nomor"], "| skor", u[0]["skor"], "|", u2[0]["nomor"], "| disaring:", d[0]["nomor"], "&", d2[0]["nomor"])


if __name__ == "__main__":
    uji() if "--uji" in sys.argv else jalankan()
