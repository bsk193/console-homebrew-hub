var CACHE = 'chh-v5';

/* Determine the base path from the SW's own URL so paths work on both
   GitHub Pages (/console-homebrew-hub/) and a local server (/). */
var _swBase = self.location.pathname.replace(/\/sw\.js$/, '') || '';

var PRECACHE_REL = [
  '/', '/index.html',
  '/console-nav.js',
  '/ps5/', '/ps5/index.html',
  '/ps5/browser/', '/ps5/browser/index.html',
  '/ps5/payloads/', '/ps5/payloads/index.html',
  '/ps5/exploits/slopkit/', '/ps5/exploits/slopkit/index.html',
  '/ps5/exploits/umtx/', '/ps5/exploits/umtx/index.html',
  '/ps5/exploits/ipv6/', '/ps5/exploits/ipv6/index.html',
  '/ps4/', '/ps3/', '/vita/', '/switch/', '/switch2/',
  /* Exploit core entry points — needed for offline shortcut use */
  '/ps5/exploits/umtx/core/document/en/ps5/index.html',
  '/ps5/exploits/ipv6/core/document/en/ps5/index.html',
  '/ps5/exploits/slopkit/core/slopkit/poops.html',
  /* ELF payloads — chh-installer.elf omitted: served by the embedded ELF server,
     not cached here (large file would pressure memory during exploit) */
  '/pldmgrx.elf',
];

var PRECACHE = PRECACHE_REL.map(function(p) { return _swBase + p; });

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return Promise.allSettled(PRECACHE.map(function (u) {
        return c.add(u).catch(function () {});
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

/* Cache-warm on demand: pages send this after install success */
self.addEventListener('message', function (e) {
  if (!e.data || e.data.type !== 'CACHE_URLS') return;
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return Promise.allSettled((e.data.urls || []).map(function (u) {
        /* Normalise relative paths against the SW base */
        var url = (u.charAt(0) === '/') ? _swBase + u : u;
        return fetch(url).then(function (r) { return c.put(url, r); }).catch(function () {});
      }));
    })
  );
});

self.addEventListener('fetch', function (e) {
  var url = e.request.url;
  /* Cache-first for ELFs, bins, and exploit core resources */
  var cacheFirst = /\.(elf|bin)$|\?v=|\/offsets\/|\/core\//.test(url);
  if (cacheFirst) {
    e.respondWith(caches.match(e.request).then(function (r) {
      return r || fetch(e.request).then(function (res) {
        var clone = res.clone();
        caches.open(CACHE).then(function (c) { c.put(e.request, clone); });
        return res;
      });
    }));
    return;
  }
  /* Network-first for HTML and everything else */
  e.respondWith(
    fetch(e.request).then(function (res) {
      var clone = res.clone();
      caches.open(CACHE).then(function (c) { c.put(e.request, clone); });
      return res;
    }).catch(function () { return caches.match(e.request); })
  );
});
