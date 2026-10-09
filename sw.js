/* Radar Regulasi QHSE — service worker.
   Menyimpan cangkang aplikasi agar tetap bisa dibuka tanpa sinyal.
   Berkas register.json dan kandidat.json selalu diambil dari jaringan (tombol Perbarui), tidak disimpan di sini.
   Naikkan angka versi CACHE setiap kali index.html diganti. */
const CACHE = "radar-regulasi-v11";
const SHELL = ["./", "./index.html", "./exceljs.min.js", "./manifest.json", "./icon.svg"];
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== CACHE).map(x => caches.delete(x)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || /\/(register|kandidat|ditolak)\.json$/.test(u.pathname)) return;
  e.respondWith(fetch(e.request).then(r => { const s = r.clone(); caches.open(CACHE).then(c => c.put(e.request, s)).catch(() => {}); return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match("./index.html"))));
});
